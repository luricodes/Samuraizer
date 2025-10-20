use pyo3::{exceptions::PyRuntimeError, PyErr};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum NativeError {
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Encoding error: {0}")]
    Encoding(String),
    #[error("Hashing error: {0}")]
    Hashing(String),
    #[error("Traversal aborted")]
    Cancelled,
    #[error("Unexpected error: {0}")]
    Other(String),
}

impl NativeError {
    pub fn to_pyerr(&self) -> PyErr {
        PyRuntimeError::new_err(self.to_string())
    }
}
