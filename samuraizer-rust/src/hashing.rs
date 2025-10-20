use std::fs::File;
use std::io::{BufReader, Read};
use std::path::Path;

use xxhash_rust::xxh64::Xxh64;

use crate::errors::NativeError;

const HASH_CHUNK_SIZE: usize = 64 * 1024;

pub fn compute_file_hash(path: &Path) -> Result<Option<String>, NativeError> {
    let file = match File::open(path) {
        Ok(f) => f,
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(err) => return Err(NativeError::Io(err)),
    };

    let mut reader = BufReader::with_capacity(HASH_CHUNK_SIZE, file);
    let mut hasher = Xxh64::default();
    let mut buffer = [0u8; HASH_CHUNK_SIZE];

    loop {
        let read = reader.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }

    Ok(Some(format!("{:016x}", hasher.digest())))
}
