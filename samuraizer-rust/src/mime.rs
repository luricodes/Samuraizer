use std::fs::File;
use std::io::Read;
use std::num::NonZeroUsize;
use std::path::{Path, PathBuf};
use std::time::UNIX_EPOCH;

use infer;
use lru::LruCache;
use mime_guess::MimeGuess;
use once_cell::sync::Lazy;
use parking_lot::Mutex;
use serde::Serialize;

use crate::errors::NativeError;

const HEURISTIC_SAMPLE_SIZE: usize = 8192;
const SAFE_CONTROL: [u8; 4] = [9, 10, 12, 13];
const TEXTUAL_MIME_PREFIXES: &[&str] = &[
    "text/",
    "application/json",
    "application/xml",
    "application/javascript",
    "application/x-javascript",
    "application/x-sh",
];
const TEXTUAL_MIME_TYPES: &[&str] = &["application/x-empty", "inode/x-empty"];

static TEXTUAL_EXTENSIONS: Lazy<std::collections::HashSet<&'static str>> = Lazy::new(|| {
    [
        ".c",
        ".cc",
        ".cfg",
        ".cmake",
        ".conf",
        ".cpp",
        ".cs",
        ".css",
        ".csv",
        ".dart",
        ".env",
        ".go",
        ".gradle",
        ".h",
        ".hpp",
        ".html",
        ".ini",
        ".java",
        ".js",
        ".json",
        ".jsx",
        ".kt",
        ".less",
        ".lock",
        ".lua",
        ".m",
        ".md",
        ".php",
        ".pl",
        ".properties",
        ".ps1",
        ".py",
        ".pyi",
        ".r",
        ".rb",
        ".rs",
        ".rst",
        ".sass",
        ".scala",
        ".scss",
        ".sh",
        ".sql",
        ".swift",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".vue",
        ".yaml",
        ".yml",
    ]
    .into_iter()
    .collect()
});

static BINARY_EXTENSIONS: Lazy<std::collections::HashSet<&'static str>> = Lazy::new(|| {
    [
        ".7z", ".apng", ".avi", ".bmp", ".class", ".dll", ".dylib", ".exe", ".gif", ".gz", ".ico",
        ".iso", ".jar", ".jpeg", ".jpg", ".lz", ".mkv", ".mov", ".mp3", ".mp4", ".ogg", ".otf",
        ".pdf", ".png", ".psd", ".pyd", ".rar", ".so", ".svgz", ".tar", ".tgz", ".ttf", ".wav",
        ".webm", ".webp", ".woff", ".woff2", ".xz", ".zip",
    ]
    .into_iter()
    .collect()
});

static MIME_CACHE: Lazy<Mutex<LruCache<(PathBuf, u64, u128), bool>>> =
    Lazy::new(|| Mutex::new(LruCache::new(NonZeroUsize::new(4096).unwrap())));

#[derive(Default, Debug, Clone, Copy, Serialize)]
pub struct StatKey {
    pub size: u64,
    pub mtime_ns: u128,
}

fn classify_by_extension(path: &Path) -> Option<bool> {
    let suffix = path
        .extension()
        .and_then(|s| s.to_str())
        .map(|s| format!(".{}", s.to_lowercase()))?;
    if TEXTUAL_EXTENSIONS.contains(suffix.as_str()) {
        return Some(false);
    }
    if BINARY_EXTENSIONS.contains(suffix.as_str()) {
        return Some(true);
    }
    None
}

fn mime_implies_text(mime_type: &str) -> bool {
    if TEXTUAL_MIME_TYPES.contains(&mime_type) {
        return true;
    }
    TEXTUAL_MIME_PREFIXES
        .iter()
        .any(|prefix| mime_type.starts_with(prefix))
}

fn classify_mime_type(mime_type: &str) -> Option<bool> {
    if mime_implies_text(mime_type) {
        return Some(false);
    }
    if mime_type == "application/octet-stream" {
        return None;
    }
    Some(true)
}

fn detect_with_infer(sample: &[u8]) -> Option<bool> {
    infer::get(sample).and_then(|kind| classify_mime_type(kind.mime_type()))
}

fn detect_with_mime_guess(path: &Path) -> Option<bool> {
    let guess = MimeGuess::from_path(path).first_raw()?;
    classify_mime_type(guess)
}

fn read_file_sample(path: &Path, sample_size: usize) -> Result<Vec<u8>, NativeError> {
    let mut file = File::open(path)?;
    let mut buffer = vec![0u8; sample_size];
    let mut offset = 0usize;
    while offset < sample_size {
        let read = file.read(&mut buffer[offset..])?;
        if read == 0 {
            buffer.truncate(offset);
            break;
        }
        offset += read;
    }
    if offset == sample_size {
        Ok(buffer)
    } else {
        buffer.truncate(offset);
        Ok(buffer)
    }
}

fn printable_ratio(sample: &[u8]) -> (f64, f64, f64) {
    if sample.is_empty() {
        return (1.0, 0.0, 0.0);
    }
    let mut printable = 0usize;
    let mut control = 0usize;
    let mut nul = 0usize;
    for byte in sample.iter().copied() {
        if byte == 0 {
            nul += 1;
        }
        if byte < 32 && !SAFE_CONTROL.contains(&byte) {
            control += 1;
        }
        if (32..=126).contains(&byte) || SAFE_CONTROL.contains(&byte) {
            printable += 1;
        }
    }
    let total = sample.len() as f64;
    (
        printable as f64 / total,
        control as f64 / total,
        nul as f64 / total,
    )
}

fn analyse_sample(sample: &[u8]) -> Option<bool> {
    let (printable, control, nul) = printable_ratio(sample);
    if nul > 0.0 {
        if nul >= 0.001 || sample.windows(2).any(|w| w == [0, 0]) {
            return Some(true);
        }
    }
    if control > 0.10 && printable < 0.9 {
        return Some(true);
    }
    if printable >= 0.95 && control <= 0.02 {
        return Some(false);
    }
    if printable <= 0.60 {
        return Some(true);
    }
    None
}

#[cfg(feature = "libmagic")]
fn magic_detect(sample: &[u8]) -> Option<bool> {
    static MAGIC: Lazy<Mutex<Option<magic::Cookie>>> = Lazy::new(|| {
        let cookie = unsafe { magic::Cookie::open(magic::MagicFlags::MIME_TYPE) };
        Mutex::new(cookie.ok())
    });
    let mut guard = MAGIC.lock();
    let cookie = guard.as_mut()?;
    if unsafe { cookie.load(&[]) }.is_err() {
        return None;
    }
    let mime = unsafe { cookie.buffer(sample) }.ok()?;
    classify_mime_type(&mime)
}

#[cfg(not(feature = "libmagic"))]
fn magic_detect(_sample: &[u8]) -> Option<bool> {
    None
}

fn compute_stat_key(path: &Path) -> Option<(PathBuf, StatKey)> {
    let metadata = path.metadata().ok()?;
    let modified = metadata.modified().ok();
    let mtime_ns = modified
        .and_then(|mtime| mtime.duration_since(UNIX_EPOCH).ok())
        .map(|d| d.as_nanos())
        .unwrap_or_else(|| {
            metadata
                .modified()
                .ok()
                .and_then(|mtime| mtime.duration_since(UNIX_EPOCH).ok())
                .map(|d| d.as_nanos())
                .unwrap_or(0)
        });
    Some((
        path.to_path_buf(),
        StatKey {
            size: metadata.len(),
            mtime_ns,
        },
    ))
}

fn classify_uncached(path: &Path) -> Result<bool, NativeError> {
    if let Some(result) = classify_by_extension(path) {
        return Ok(result);
    }

    let sample = read_file_sample(path, HEURISTIC_SAMPLE_SIZE)?;
    if let Some(result) = analyse_sample(&sample) {
        return Ok(result);
    }
    if let Some(result) = detect_with_infer(&sample) {
        return Ok(result);
    }
    if let Some(result) = detect_with_mime_guess(path) {
        return Ok(result);
    }
    if let Some(result) = magic_detect(&sample) {
        return Ok(result);
    }
    Ok(false)
}

pub fn is_binary(path: &Path) -> Result<bool, NativeError> {
    if let Some((key, stat)) = compute_stat_key(path) {
        let mut cache = MIME_CACHE.lock();
        if let Some(result) = cache.get(&(key.clone(), stat.size, stat.mtime_ns)) {
            return Ok(*result);
        }
        drop(cache);
        let result = classify_uncached(path)?;
        let mut cache = MIME_CACHE.lock();
        cache.put((key, stat.size, stat.mtime_ns), result);
        Ok(result)
    } else {
        classify_uncached(path)
    }
}
