use std::collections::{BTreeMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;

use chrono::{DateTime, Local, NaiveDateTime, SecondsFormat, TimeZone, Utc};
use chrono_tz::Tz;
use crossbeam_channel::{bounded, Receiver, Sender};
use globset::{Glob, GlobMatcher};
use pyo3::types::{PyDict, PyList};
use pyo3::{exceptions::PyValueError, prelude::*};
use rayon::prelude::*;
use regex::Regex;
use serde_json::{json, Number, Value};
use std::convert::TryFrom;
use walkdir::WalkDir;

use crate::content;
use crate::errors::NativeError;
use crate::ffi::value_to_py;
use crate::hashing;

#[derive(Debug)]
pub enum TraversalMessage {
    Entries(Vec<Value>),
    Summary(Value),
    Error(NativeError),
}

#[derive(Clone)]
pub struct TraversalOptions {
    pub root: PathBuf,
    pub max_file_size: u64,
    pub include_binary: bool,
    pub image_extensions: HashSet<String>,
    pub excluded_folders: HashSet<String>,
    pub excluded_files: HashSet<String>,
    pub exclude_patterns: Vec<PatternMatcher>,
    pub follow_symlinks: bool,
    pub threads: usize,
    pub encoding: Option<String>,
    pub hashing_enabled: bool,
    pub chunk_size: usize,
    pub cancellation: Option<Py<PyAny>>,
    pub timezone: TimezoneInfo,
}

#[derive(Clone)]
pub enum PatternMatcher {
    Glob(GlobMatcher),
    Regex(Arc<Regex>),
}

impl PatternMatcher {
    fn is_match(&self, name: &str) -> bool {
        match self {
            PatternMatcher::Glob(matcher) => matcher.is_match(name),
            PatternMatcher::Regex(regex) => regex.is_match(name),
        }
    }
}

impl TraversalOptions {
    pub fn from_py(_py: Python<'_>, options: &PyAny) -> PyResult<Self> {
        let dict: &PyDict = options.downcast()?;
        let root: PathBuf = dict
            .get_item("root")?
            .ok_or_else(|| PyValueError::new_err("Missing 'root' in traversal options"))?
            .extract()?;
        let max_file_size: u64 = dict
            .get_item("max_file_size")?
            .map(|v| v.extract::<u64>())
            .transpose()?
            .unwrap_or(usize::MAX as u64);
        let include_binary: bool = dict
            .get_item("include_binary")?
            .map(|v| v.extract::<bool>())
            .transpose()?
            .unwrap_or(true);
        let follow_symlinks: bool = dict
            .get_item("follow_symlinks")?
            .map(|v| v.extract::<bool>())
            .transpose()?
            .unwrap_or(false);
        let threads: usize = dict
            .get_item("threads")?
            .map(|v| v.extract::<usize>())
            .transpose()?
            .unwrap_or_else(|| num_cpus::get().max(1));
        let encoding: Option<String> = dict
            .get_item("encoding")?
            .map(|v| v.extract::<String>())
            .transpose()?;
        let hashing_enabled: bool = dict
            .get_item("hashing_enabled")?
            .map(|v| v.extract::<bool>())
            .transpose()?
            .unwrap_or(true);
        let chunk_size: usize = dict
            .get_item("chunk_size")?
            .map(|v| v.extract::<usize>())
            .transpose()?
            .unwrap_or(256);
        let use_utc: bool = dict
            .get_item("use_utc")?
            .map(|v| v.extract::<bool>())
            .transpose()?
            .unwrap_or(false);
        let timezone_name: Option<String> = dict
            .get_item("timezone")?
            .map(|v| v.extract::<String>())
            .transpose()?;

        let image_extensions: HashSet<String> = dict
            .get_item("image_extensions")?
            .map(|v| v.extract::<HashSet<String>>())
            .transpose()?
            .unwrap_or_default();
        let image_extensions = image_extensions
            .into_iter()
            .map(|ext: String| ext.to_lowercase())
            .collect();

        let excluded_folders: HashSet<String> = dict
            .get_item("excluded_folders")?
            .map(|v| v.extract::<HashSet<String>>())
            .transpose()?
            .unwrap_or_default();
        let excluded_files: HashSet<String> = dict
            .get_item("excluded_files")?
            .map(|v| v.extract::<HashSet<String>>())
            .transpose()?
            .unwrap_or_default();
        let exclude_patterns: Vec<String> = dict
            .get_item("exclude_patterns")?
            .map(|v| v.extract::<Vec<String>>())
            .transpose()?
            .unwrap_or_default();

        let exclude_patterns = exclude_patterns
            .into_iter()
            .filter_map(|pattern| {
                if let Some(stripped) = pattern.strip_prefix("regex:") {
                    Regex::new(stripped)
                        .map(|re| PatternMatcher::Regex(Arc::new(re)))
                        .ok()
                } else {
                    match Glob::new(&pattern) {
                        Ok(glob) => Some(PatternMatcher::Glob(glob.compile_matcher())),
                        Err(_) => None,
                    }
                }
            })
            .collect();

        let cancellation = dict
            .get_item("cancellation")?
            .map(|obj| obj.extract::<Py<PyAny>>())
            .transpose()?;

        Ok(Self {
            root,
            max_file_size,
            include_binary,
            image_extensions,
            excluded_folders,
            excluded_files,
            exclude_patterns,
            follow_symlinks,
            threads: threads.max(1),
            encoding,
            hashing_enabled,
            chunk_size: chunk_size.max(1),
            cancellation,
            timezone: TimezoneInfo::new(use_utc, timezone_name),
        })
    }
}

#[derive(Clone)]
pub struct TimezoneInfo {
    use_utc: bool,
    timezone: Option<Tz>,
    label: String,
}

impl TimezoneInfo {
    fn new(use_utc: bool, timezone_name: Option<String>) -> Self {
        let timezone = timezone_name
            .as_ref()
            .and_then(|name| name.parse::<Tz>().ok());
        let label = if use_utc {
            "UTC".to_string()
        } else if let Some(name) = timezone_name {
            name
        } else {
            let now = Local::now();
            let display = now.format("%Z").to_string();
            if display.trim().is_empty() {
                now.offset().to_string()
            } else {
                display
            }
        };
        Self {
            use_utc,
            timezone,
            label,
        }
    }

    fn label(&self) -> &str {
        &self.label
    }

    fn format_system_time(&self, time: std::time::SystemTime) -> Option<String> {
        system_time_to_datetime(time).map(|dt| self.format_datetime(dt))
    }

    fn format_datetime(&self, datetime: DateTime<Utc>) -> String {
        if self.use_utc {
            datetime.to_rfc3339_opts(SecondsFormat::Millis, true)
        } else if let Some(tz) = &self.timezone {
            tz.from_utc_datetime(&datetime.naive_utc())
                .to_rfc3339_opts(SecondsFormat::Millis, true)
        } else {
            DateTime::<Local>::from(datetime).to_rfc3339_opts(SecondsFormat::Millis, true)
        }
    }
}

fn system_time_to_datetime(time: std::time::SystemTime) -> Option<DateTime<Utc>> {
    let duration = time.duration_since(std::time::UNIX_EPOCH).ok()?;
    let secs = duration.as_secs();
    let nanos = duration.subsec_nanos();
    let secs_i64 = i64::try_from(secs).ok()?;
    let naive = NaiveDateTime::from_timestamp_opt(secs_i64, nanos)?;
    Some(DateTime::<Utc>::from_utc(naive, Utc))
}

fn matches_patterns(name: &str, patterns: &[PatternMatcher]) -> bool {
    patterns.iter().any(|pattern| pattern.is_match(name))
}

fn relative_parent(root: &Path, path: &Path) -> String {
    path.parent()
        .and_then(|parent| parent.strip_prefix(root).ok())
        .map(|relative| {
            let s = relative.to_string_lossy().trim().to_string();
            if s == "." || s.is_empty() {
                String::new()
            } else {
                s.replace('\\', "/")
            }
        })
        .unwrap_or_else(|| String::new())
}

fn path_cancellation_requested(token: &Py<PyAny>) -> PyResult<bool> {
    Python::with_gil(|py| {
        let result = token.call_method0(py, "is_cancellation_requested")?;
        result.extract(py)
    })
}

struct GatherResult {
    files: Vec<PathBuf>,
    included: usize,
    excluded: usize,
    cancelled: bool,
}

fn gather_files(options: &TraversalOptions) -> PyResult<GatherResult> {
    let mut included = 0usize;
    let mut excluded = 0usize;
    let mut cancelled = false;
    let mut files = Vec::new();

    let mut walker = WalkDir::new(&options.root)
        .follow_links(options.follow_symlinks)
        .into_iter();

    while let Some(entry_result) = walker.next() {
        let entry = match entry_result {
            Ok(e) => e,
            Err(_) => continue,
        };
        if let Some(token) = &options.cancellation {
            if path_cancellation_requested(token)? {
                cancelled = true;
                break;
            }
        }

        if entry.file_type().is_dir() {
            if options
                .excluded_folders
                .contains(entry.file_name().to_string_lossy().as_ref())
                || matches_patterns(
                    entry.file_name().to_string_lossy().as_ref(),
                    &options.exclude_patterns,
                )
            {
                walker.skip_current_dir();
                continue;
            }
            continue;
        }

        if !entry.file_type().is_file() {
            continue;
        }

        let name = entry.file_name().to_string_lossy().to_string();
        if options.excluded_files.contains(&name)
            || matches_patterns(&name, &options.exclude_patterns)
        {
            excluded += 1;
            continue;
        }

        included += 1;
        files.push(entry.into_path());
    }

    Ok(GatherResult {
        files,
        included,
        excluded,
        cancelled,
    })
}

fn check_cancellation(options: &TraversalOptions) -> Result<bool, NativeError> {
    if let Some(token) = &options.cancellation {
        path_cancellation_requested(token).map_err(|err| NativeError::Other(err.to_string()))
    } else {
        Ok(false)
    }
}

fn process_path(path: &Path, options: &TraversalOptions) -> Value {
    let file_name = path
        .file_name()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_else(|| String::new());

    let metadata = match path.metadata() {
        Ok(m) => m,
        Err(err) => {
            return json!({
                "parent": relative_parent(&options.root, path),
                "filename": file_name,
                "info": {
                    "type": "error",
                    "content": format!("Failed to get file stats: {}", err),
                    "exception_type": "OSError",
                    "exception_message": err.to_string(),
                }
            });
        }
    };

    let size = metadata.len();
    if size > options.max_file_size {
        return json!({
            "parent": relative_parent(&options.root, path),
            "filename": file_name,
            "info": {
                "type": "excluded",
                "reason": "file_size",
                "size": size,
            }
        });
    }

    let extension = path
        .extension()
        .and_then(|ext| ext.to_str())
        .unwrap_or("")
        .to_lowercase();
    let is_image = options
        .image_extensions
        .contains(&format!(".{}", extension));

    let binary = match content::classify_binary(path) {
        Ok(result) => result,
        Err(err) => {
            return json!({
                "parent": relative_parent(&options.root, path),
                "filename": file_name,
                "info": {
                    "type": "error",
                    "content": format!("Failed to classify file: {}", err),
                    "exception_type": "NativeError",
                    "exception_message": err.to_string(),
                }
            });
        }
    };

    if (binary || is_image) && !options.include_binary {
        return json!({
            "parent": relative_parent(&options.root, path),
            "filename": file_name,
            "info": {
                "type": "excluded",
                "reason": "binary_or_image"
            }
        });
    }

    #[cfg(unix)]
    let mode_value = {
        use std::os::unix::fs::PermissionsExt;
        metadata.permissions().mode()
    };
    #[cfg(not(unix))]
    let mode_value = 0u32;

    let mut info = if binary {
        match content::read_binary_preview(path, options.max_file_size as usize) {
            Ok(info) => info,
            Err(err) => json!({
                "type": "error",
                "content": format!("Failed to read binary file: {}", err),
                "exception_type": "NativeError",
                "exception_message": err.to_string(),
            }),
        }
    } else {
        match content::read_text_preview(
            path,
            options.max_file_size as usize,
            options.encoding.as_deref(),
        ) {
            Ok(info) => info,
            Err(err) => json!({
                "type": "error",
                "content": format!("Failed to read text file: {}", err),
                "exception_type": "NativeError",
                "exception_message": err.to_string(),
            }),
        }
    };

    if let Value::Object(map) = &mut info {
        map.insert("size".to_string(), Value::Number(Number::from(size)));
        let permissions = format!("{:#o}", mode_value);
        map.insert("permissions".to_string(), Value::String(permissions));
        let modified_iso = metadata
            .modified()
            .ok()
            .and_then(|ts| options.timezone.format_system_time(ts));
        let created_iso = metadata
            .created()
            .ok()
            .and_then(|ts| options.timezone.format_system_time(ts));
        map.insert(
            "modified".to_string(),
            modified_iso.map(Value::String).unwrap_or(Value::Null),
        );
        map.insert(
            "created".to_string(),
            created_iso.map(Value::String).unwrap_or(Value::Null),
        );
        map.insert(
            "timezone".to_string(),
            Value::String(options.timezone.label().to_string()),
        );
    }

    let hash_value = if options.hashing_enabled {
        match hashing::compute_file_hash(path) {
            Ok(value) => value.map(Value::String).unwrap_or(Value::Null),
            Err(err) => Value::Object(
                [
                    ("type".to_string(), Value::String("error".to_string())),
                    (
                        "content".to_string(),
                        Value::String(format!("Failed to compute hash: {}", err)),
                    ),
                ]
                .into_iter()
                .collect(),
            ),
        }
    } else {
        Value::Null
    };

    let modified = metadata
        .modified()
        .ok()
        .and_then(|ts| ts.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|dur| dur.as_secs_f64())
        .unwrap_or(0.0);

    let created = metadata
        .created()
        .ok()
        .and_then(|ts| ts.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|dur| dur.as_secs_f64());

    let mut entry = json!({
        "parent": relative_parent(&options.root, path),
        "filename": file_name,
        "info": info,
        "stat": {
            "size": size,
            "mtime": modified,
            "ctime": created.unwrap_or(0.0),
            "mode": mode_value,
        }
    });

    if options.hashing_enabled {
        if let Some(obj) = entry.as_object_mut() {
            obj.insert("hash".to_string(), hash_value);
        }
    }

    entry
}

pub struct TraversalState {
    pub receiver: Receiver<TraversalMessage>,
}

pub fn run_traversal(py: Python<'_>, options: &TraversalOptions) -> PyResult<TraversalState> {
    let (sender, receiver) = bounded::<TraversalMessage>(options.chunk_size.max(1) * 4);

    py.allow_threads(|| -> Result<(), NativeError> {
        let worker_sender = sender.clone();
        let options_for_worker = options.clone();
        thread::Builder::new()
            .name("samuraizer-traversal".into())
            .spawn(move || {
                let error_sender = worker_sender.clone();
                if let Err(err) = traversal_worker(options_for_worker, worker_sender) {
                    if !matches!(err, NativeError::Cancelled) {
                        let _ = error_sender.send(TraversalMessage::Error(err));
                    }
                }
            })
            .map(|_| ())
            .map_err(|err| NativeError::Other(err.to_string()))
    })
    .map_err(|err| err.to_pyerr())?;

    drop(sender);

    Ok(TraversalState { receiver })
}

fn traversal_worker(
    options: TraversalOptions,
    sender: Sender<TraversalMessage>,
) -> Result<(), NativeError> {
    let gather = gather_files(&options).map_err(|err| NativeError::Other(err.to_string()))?;
    let cancellation_flag = Arc::new(AtomicBool::new(gather.cancelled));
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(options.threads)
        .build()
        .map_err(|err| NativeError::Other(err.to_string()))?;

    let (entry_tx, entry_rx) = bounded::<(usize, Value)>(options.threads.max(1) * 4);
    let aggregate_options = options.clone();
    let aggregate_sender = sender.clone();
    let aggregate_cancel = cancellation_flag.clone();
    let included = gather.included;
    let excluded = gather.excluded;

    let aggregator_handle = thread::spawn(move || {
        aggregate_entries(
            entry_rx,
            aggregate_sender,
            aggregate_options,
            included,
            excluded,
            aggregate_cancel,
        )
    });

    let process_options = options.clone();
    let process_cancel = cancellation_flag.clone();
    let files = gather.files;

    let processing_result = pool.install(|| {
        files.into_par_iter().enumerate().try_for_each_with(
            entry_tx.clone(),
            |tx, (index, path)| {
                if process_cancel.load(Ordering::Relaxed) {
                    return Err(NativeError::Cancelled);
                }
                if check_cancellation(&process_options)? {
                    process_cancel.store(true, Ordering::Relaxed);
                    return Err(NativeError::Cancelled);
                }

                let entry = process_path(&path, &process_options);
                if tx.send((index, entry)).is_err() {
                    process_cancel.store(true, Ordering::Relaxed);
                    return Err(NativeError::Cancelled);
                }
                Ok(())
            },
        )
    });
    drop(entry_tx);

    let worker_result = match processing_result {
        Ok(_) => Ok(()),
        Err(NativeError::Cancelled) => Ok(()),
        Err(err) => Err(err),
    };

    let aggregator_result = match aggregator_handle.join() {
        Ok(Ok(())) => Ok(()),
        Ok(Err(NativeError::Cancelled)) => Ok(()),
        Ok(Err(err)) => Err(err),
        Err(_) => Err(NativeError::Other(
            "Traversal aggregator panicked".to_string(),
        )),
    };

    worker_result?;
    aggregator_result?;

    Ok(())
}

fn aggregate_entries(
    entry_rx: Receiver<(usize, Value)>,
    sender: Sender<TraversalMessage>,
    options: TraversalOptions,
    included: usize,
    excluded: usize,
    cancellation_flag: Arc<AtomicBool>,
) -> Result<(), NativeError> {
    let mut chunk = Vec::with_capacity(options.chunk_size);
    let mut processed = 0usize;
    let mut pending: BTreeMap<usize, Value> = BTreeMap::new();
    let mut failed_files = Vec::new();
    let mut next_index = 0usize;

    for (index, entry) in entry_rx.iter() {
        processed += 1;

        if let Some(info) = entry.get("info").and_then(|i| i.as_object()) {
            if let Some(info_type) = info.get("type").and_then(|t| t.as_str()) {
                if info_type == "error" {
                    if let Some(filename) = entry.get("filename").and_then(|f| f.as_str()) {
                        let file_path = options.root.join(
                            entry
                                .get("parent")
                                .and_then(|p| p.as_str())
                                .filter(|s| !s.is_empty())
                                .map(|parent| Path::new(parent).join(filename))
                                .unwrap_or_else(|| PathBuf::from(filename)),
                        );
                        let error = info
                            .get("content")
                            .and_then(|c| c.as_str())
                            .unwrap_or("Unknown error")
                            .to_string();
                        failed_files.push(json!({
                            "file": file_path.to_string_lossy(),
                            "error": error,
                        }));
                    }
                }
            }
        }

        pending.insert(index, entry);

        while let Some(next_entry) = pending.remove(&next_index) {
            chunk.push(next_entry);
            next_index += 1;

            if chunk.len() >= options.chunk_size {
                let to_send = std::mem::take(&mut chunk);
                if sender.send(TraversalMessage::Entries(to_send)).is_err() {
                    cancellation_flag.store(true, Ordering::Relaxed);
                    return Err(NativeError::Cancelled);
                }
            }
        }
    }

    for (_idx, entry) in pending.into_iter() {
        chunk.push(entry);
        if chunk.len() >= options.chunk_size {
            let to_send = std::mem::take(&mut chunk);
            if sender.send(TraversalMessage::Entries(to_send)).is_err() {
                cancellation_flag.store(true, Ordering::Relaxed);
                return Err(NativeError::Cancelled);
            }
        }
    }

    if !chunk.is_empty() {
        if sender.send(TraversalMessage::Entries(chunk)).is_err() {
            cancellation_flag.store(true, Ordering::Relaxed);
            return Err(NativeError::Cancelled);
        }
    }

    let total_files = included + excluded;
    let excluded_percentage = if total_files == 0 {
        0.0
    } else {
        (excluded as f64 / total_files as f64) * 100.0
    };

    let mut summary = json!({
        "total_files": total_files,
        "excluded_files": excluded,
        "included_files": included,
        "excluded_percentage": excluded_percentage,
        "failed_files": failed_files,
        "stopped_early": cancellation_flag.load(Ordering::Relaxed),
        "processed_files": processed,
    });

    if options.hashing_enabled {
        summary.as_object_mut().unwrap().insert(
            "hash_algorithm".to_string(),
            Value::String("xxhash".to_string()),
        );
    }

    if sender.send(TraversalMessage::Summary(summary)).is_err() {
        cancellation_flag.store(true, Ordering::Relaxed);
        return Err(NativeError::Cancelled);
    }

    Ok(())
}

#[pyclass]
pub struct TraversalIterator {
    receiver: Option<Receiver<TraversalMessage>>,
}

#[pymethods]
impl TraversalIterator {
    pub fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    pub fn __next__(&mut self, py: Python<'_>) -> PyResult<Option<PyObject>> {
        let receiver = match &self.receiver {
            Some(receiver) => receiver,
            None => return Ok(None),
        };

        match receiver.recv() {
            Ok(TraversalMessage::Entries(entries)) => {
                let list = PyList::empty(py);
                for entry in &entries {
                    list.append(value_to_py(py, entry)?)?;
                }
                let dict = PyDict::new(py);
                dict.set_item("entries", list)?;
                Ok(Some(dict.into()))
            }
            Ok(TraversalMessage::Summary(summary)) => {
                self.receiver = None;
                let dict = PyDict::new(py);
                dict.set_item("summary", value_to_py(py, &summary)?)?;
                Ok(Some(dict.into()))
            }
            Ok(TraversalMessage::Error(err)) => Err(err.to_pyerr()),
            Err(_) => {
                self.receiver = None;
                Ok(None)
            }
        }
    }
}

impl TraversalIterator {
    pub fn new(state: TraversalState) -> Self {
        Self {
            receiver: Some(state.receiver),
        }
    }
}
