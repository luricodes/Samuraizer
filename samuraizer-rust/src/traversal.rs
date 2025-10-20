use std::collections::HashSet;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::thread;

use crossbeam_channel::{bounded, Receiver, Sender};
use globset::{Glob, GlobMatcher};
use pyo3::types::{PyDict, PyList};
use pyo3::{exceptions::PyValueError, prelude::*};
use rayon::prelude::*;
use regex::Regex;
use serde_json::{json, Value};
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
        })
    }
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

fn gather_files(options: &TraversalOptions) -> PyResult<(Vec<PathBuf>, usize, usize, bool)> {
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

    Ok((files, included, excluded, cancelled))
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

    let info = if binary {
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

    #[cfg(unix)]
    let mode_value = {
        use std::os::unix::fs::PermissionsExt;
        metadata.permissions().mode()
    };
    #[cfg(not(unix))]
    let mode_value = 0u32;

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
                    let _ = error_sender.send(TraversalMessage::Error(err));
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
    let (files, included, excluded, cancelled) =
        gather_files(&options).map_err(|err| NativeError::Other(err.to_string()))?;
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(options.threads)
        .build()
        .map_err(|err| NativeError::Other(err.to_string()))?;

    let (entry_tx, entry_rx) = bounded::<Value>(options.threads.max(1) * 4);
    let aggregate_options = options.clone();
    let aggregate_sender = sender.clone();

    let aggregator_handle = thread::spawn(move || {
        aggregate_entries(
            entry_rx,
            aggregate_sender,
            aggregate_options,
            included,
            excluded,
            cancelled,
        )
    });

    let process_options = options.clone();

    let processing_result = pool.install(|| {
        files.par_iter().try_for_each(|path| {
            let entry = process_path(path, &process_options);
            entry_tx.send(entry).map_err(|_| NativeError::Cancelled)
        })
    });
    drop(entry_tx);

    if let Err(err) = processing_result {
        // wait for aggregator to drain existing entries before returning
        let _ = aggregator_handle.join();
        return Err(err);
    }

    match aggregator_handle.join() {
        Ok(result) => result?,
        Err(_) => {
            return Err(NativeError::Other(
                "Traversal aggregator panicked".to_string(),
            ))
        }
    }

    Ok(())
}

fn aggregate_entries(
    entry_rx: Receiver<Value>,
    sender: Sender<TraversalMessage>,
    options: TraversalOptions,
    included: usize,
    excluded: usize,
    cancelled: bool,
) -> Result<(), NativeError> {
    let mut chunk = Vec::with_capacity(options.chunk_size);
    let mut processed = 0usize;
    let mut excluded_files = excluded;
    let mut included_files = 0usize;
    let mut failed_files = Vec::new();

    for entry in entry_rx.iter() {
        processed += 1;
        if let Some(info) = entry.get("info") {
            if let Some(info_type) = info.get("type").and_then(|t| t.as_str()) {
                match info_type {
                    "excluded" => {
                        excluded_files += 1;
                    }
                    "error" => {
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
                    _ => {
                        included_files += 1;
                    }
                }
            }
        }

        chunk.push(entry);
        if chunk.len() >= options.chunk_size {
            let to_send = std::mem::take(&mut chunk);
            if sender.send(TraversalMessage::Entries(to_send)).is_err() {
                return Err(NativeError::Cancelled);
            }
            chunk = Vec::with_capacity(options.chunk_size);
        }
    }

    if !chunk.is_empty() {
        if sender.send(TraversalMessage::Entries(chunk)).is_err() {
            return Err(NativeError::Cancelled);
        }
    }

    let total_files = included + excluded_files;
    let excluded_percentage = if total_files == 0 {
        0.0
    } else {
        (excluded_files as f64 / total_files as f64) * 100.0
    };

    let mut summary = json!({
        "total_files": total_files,
        "excluded_files": excluded_files,
        "included_files": included_files,
        "excluded_percentage": excluded_percentage,
        "failed_files": failed_files,
        "stopped_early": cancelled,
        "processed_files": processed,
    });

    if options.hashing_enabled {
        summary.as_object_mut().unwrap().insert(
            "hash_algorithm".to_string(),
            Value::String("xxhash".to_string()),
        );
    }

    sender
        .send(TraversalMessage::Summary(summary))
        .map_err(|_| NativeError::Cancelled)?;

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
