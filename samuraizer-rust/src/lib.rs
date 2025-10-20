use std::path::PathBuf;

use pyo3::prelude::*;

mod cache;
mod content;
mod errors;
mod ffi;
mod hashing;
mod mime;
mod traversal;

fn extract_path(path: &PyAny) -> PyResult<PathBuf> {
    if let Ok(p) = path.extract::<PathBuf>() {
        Ok(p)
    } else if let Ok(s) = path.extract::<String>() {
        Ok(PathBuf::from(s))
    } else {
        Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
            "Expected str or Path",
        ))
    }
}

#[pyfunction]
fn compute_hash(path: &PyAny) -> PyResult<Option<String>> {
    let path = extract_path(path)?;
    hashing::compute_file_hash(&path).map_err(|err| err.to_pyerr())
}

#[pyfunction]
fn classify_binary(path: &PyAny) -> PyResult<bool> {
    let path = extract_path(path)?;
    mime::is_binary(&path).map_err(|err| err.to_pyerr())
}

#[pyfunction]
fn read_text_preview(path: &PyAny, max_bytes: usize, encoding: Option<&str>) -> PyResult<PyObject> {
    let path = extract_path(path)?;
    let value =
        content::read_text_preview(&path, max_bytes, encoding).map_err(|err| err.to_pyerr())?;
    Python::with_gil(|py| crate::ffi::value_to_py(py, &value))
}

#[pyfunction]
fn read_binary_preview(path: &PyAny, max_bytes: usize) -> PyResult<PyObject> {
    let path = extract_path(path)?;
    let value = content::read_binary_preview(&path, max_bytes).map_err(|err| err.to_pyerr())?;
    Python::with_gil(|py| crate::ffi::value_to_py(py, &value))
}

#[pyfunction]
fn cache_get_entry(py: Python<'_>, db_path: &PyAny, file_path: &str) -> PyResult<Option<PyObject>> {
    let db_path = extract_path(db_path)?;
    let result = cache::get_cached_entry(&db_path, file_path).map_err(|err| err.to_pyerr())?;
    if let Some(value) = result {
        Ok(Some(crate::ffi::value_to_py(py, &value)?))
    } else {
        Ok(None)
    }
}

#[pyfunction(signature = (db_path, file_path, file_hash, file_info, size, mtime, synchronous=None))]
fn cache_set_entry(
    py: Python<'_>,
    db_path: &PyAny,
    file_path: &str,
    file_hash: Option<&str>,
    file_info: &PyAny,
    size: i64,
    mtime: f64,
    synchronous: Option<bool>,
) -> PyResult<()> {
    let db_path = extract_path(db_path)?;
    let info = crate::ffi::py_to_value(py, file_info)?;
    let synchronous = synchronous.unwrap_or(false);
    cache::set_cached_entry(
        &db_path,
        file_path,
        file_hash,
        info,
        size,
        mtime,
        synchronous,
    )
    .map_err(|err| err.to_pyerr())
}

#[pyfunction]
fn traverse_and_process(
    py: Python<'_>,
    options: &PyAny,
) -> PyResult<Py<traversal::TraversalIterator>> {
    let opts = traversal::TraversalOptions::from_py(py, options)?;
    let state = traversal::run_traversal(py, &opts)?;
    Py::new(py, traversal::TraversalIterator::new(state))
}

#[pymodule]
fn _native(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compute_hash, m)?)?;
    m.add_function(wrap_pyfunction!(classify_binary, m)?)?;
    m.add_function(wrap_pyfunction!(read_text_preview, m)?)?;
    m.add_function(wrap_pyfunction!(read_binary_preview, m)?)?;
    m.add_function(wrap_pyfunction!(cache_get_entry, m)?)?;
    m.add_function(wrap_pyfunction!(cache_set_entry, m)?)?;
    m.add_function(wrap_pyfunction!(traverse_and_process, m)?)?;
    Ok(())
}
