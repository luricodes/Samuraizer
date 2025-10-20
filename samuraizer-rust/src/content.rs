use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::path::Path;

use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;
use encoding_rs::Encoding;
use serde_json::{json, Value};

use crate::errors::NativeError;
use crate::mime;

const STREAM_CHUNK_SIZE: usize = 256 * 1024;
const MAX_BINARY_CONTENT_BYTES: usize = 3 * 1024 * 1024;
const MAX_TEXT_CONTENT_BYTES: usize = 5 * 1024 * 1024;
const ENCODING_SAMPLE_BYTES: usize = 512 * 1024;

pub fn classify_binary(path: &Path) -> Result<bool, NativeError> {
    mime::is_binary(path)
}

pub fn read_binary_preview(path: &Path, max_preview_bytes: usize) -> Result<Value, NativeError> {
    let metadata = path.metadata()?;
    let file_size = metadata.len() as usize;

    if file_size > max_preview_bytes {
        return Ok(json!({
            "type": "excluded",
            "reason": "binary_too_large",
            "size": file_size,
        }));
    }

    let read_limit = std::cmp::min(max_preview_bytes, MAX_BINARY_CONTENT_BYTES);
    let preview_size = std::cmp::min(file_size, read_limit);

    let mut file = File::open(path)?;
    let mut buffer = Vec::with_capacity(preview_size.min(STREAM_CHUNK_SIZE));
    let mut total_read = 0usize;
    while total_read < preview_size {
        let mut chunk = vec![0u8; std::cmp::min(STREAM_CHUNK_SIZE, preview_size - total_read)];
        let read = file.read(&mut chunk)?;
        if read == 0 {
            break;
        }
        total_read += read;
        buffer.extend_from_slice(&chunk[..read]);
    }

    let encoded = BASE64.encode(&buffer);
    let mut result = json!({
        "type": "binary",
        "content": encoded,
        "encoding": "base64",
        "preview_bytes": total_read,
    });

    if file_size > total_read {
        result
            .as_object_mut()
            .unwrap()
            .insert("truncated".to_string(), Value::Bool(true));
    }
    Ok(result)
}

fn detect_encoding(sample: &[u8], provided: Option<&str>) -> (&'static Encoding, String) {
    if let Some(label) = provided {
        if let Some(enc) = Encoding::for_label(label.as_bytes()) {
            return (enc, enc.name().to_string());
        }
    }
    if let Some((enc, _)) = Encoding::for_bom(sample) {
        return (enc, enc.name().to_string());
    }
    if std::str::from_utf8(sample).is_ok() {
        return (encoding_rs::UTF_8, "utf-8".to_string());
    }
    (encoding_rs::WINDOWS_1252, "windows-1252".to_string())
}

pub fn read_text_preview(
    path: &Path,
    max_preview_bytes: usize,
    encoding: Option<&str>,
) -> Result<Value, NativeError> {
    let metadata = path.metadata()?;
    let file_size = metadata.len() as usize;
    let read_limit = std::cmp::min(max_preview_bytes, MAX_TEXT_CONTENT_BYTES);

    let mut file = File::open(path)?;
    let mut sample = Vec::new();
    let mut sample_reader = file.by_ref().take(ENCODING_SAMPLE_BYTES as u64);
    sample_reader.read_to_end(&mut sample)?;
    file.seek(SeekFrom::Start(0))?;

    let (encoding_impl, encoding_name) = detect_encoding(&sample, encoding);

    let mut buffer = Vec::with_capacity(read_limit.min(STREAM_CHUNK_SIZE));
    let mut total_read = 0usize;
    let mut chunk_buf = vec![0u8; STREAM_CHUNK_SIZE];

    while total_read < read_limit {
        let to_read = std::cmp::min(STREAM_CHUNK_SIZE, read_limit - total_read);
        let read = file.read(&mut chunk_buf[..to_read])?;
        if read == 0 {
            break;
        }
        total_read += read;
        buffer.extend_from_slice(&chunk_buf[..read]);
    }

    let (decoded, _, _) = encoding_impl.decode(&buffer);
    let mut result = json!({
        "type": "text",
        "encoding": encoding_name,
        "content": decoded.into_owned(),
        "preview_bytes": total_read,
    });

    if file_size > read_limit {
        result
            .as_object_mut()
            .unwrap()
            .insert("truncated".to_string(), Value::Bool(true));
    }
    Ok(result)
}
