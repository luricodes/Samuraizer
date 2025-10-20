use std::path::Path;

use rusqlite::{params, Connection, OptionalExtension};
use serde_json::{json, Value};

use crate::errors::NativeError;

fn ensure_schema(conn: &Connection) -> Result<(), NativeError> {
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS cache (
            file_path TEXT PRIMARY KEY,
            file_hash TEXT,
            file_info TEXT NOT NULL,
            size INTEGER NOT NULL,
            mtime REAL NOT NULL
        )",
    )?;
    Ok(())
}

pub fn get_cached_entry(db_path: &Path, file_path: &str) -> Result<Option<Value>, NativeError> {
    let conn = Connection::open(db_path)?;
    ensure_schema(&conn)?;

    let mut stmt =
        conn.prepare("SELECT file_hash, file_info, size, mtime FROM cache WHERE file_path = ?1")?;

    let row = stmt
        .query_row([file_path], |row| {
            let hash: Option<String> = row.get(0)?;
            let info_json: String = row.get(1)?;
            let size: i64 = row.get(2)?;
            let mtime: f64 = row.get(3)?;

            let file_info: Value = serde_json::from_str(&info_json).map_err(|err| {
                rusqlite::Error::FromSqlConversionFailure(
                    info_json.len(),
                    rusqlite::types::Type::Text,
                    Box::new(err),
                )
            })?;

            Ok(json!({
                "file_hash": hash,
                "file_info": file_info,
                "size": size,
                "mtime": mtime,
            }))
        })
        .optional()?;

    Ok(row)
}

pub fn set_cached_entry(
    db_path: &Path,
    file_path: &str,
    file_hash: Option<&str>,
    file_info: Value,
    size: i64,
    mtime: f64,
    _synchronous: bool,
) -> Result<(), NativeError> {
    let conn = Connection::open(db_path)?;
    ensure_schema(&conn)?;

    let file_info_json = serde_json::to_string(&file_info)?;

    conn.execute(
        "INSERT INTO cache (file_path, file_hash, file_info, size, mtime)
         VALUES (?1, ?2, ?3, ?4, ?5)
         ON CONFLICT(file_path) DO UPDATE SET
            file_hash = excluded.file_hash,
            file_info = excluded.file_info,
            size = excluded.size,
            mtime = excluded.mtime",
        params![file_path, file_hash, file_info_json, size, mtime],
    )?;

    Ok(())
}
