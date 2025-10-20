use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyFloat, PyInt, PyList, PyString, PyTuple};
use serde_json::{Map, Number, Value};

pub fn value_to_py(py: Python<'_>, value: &Value) -> PyResult<PyObject> {
    Ok(match value {
        Value::Null => py.None(),
        Value::Bool(v) => v.into_py(py),
        Value::Number(num) => {
            if let Some(i) = num.as_i64() {
                i.into_py(py)
            } else if let Some(u) = num.as_u64() {
                u.into_py(py)
            } else if let Some(f) = num.as_f64() {
                f.into_py(py)
            } else {
                py.None()
            }
        }
        Value::String(s) => s.into_py(py),
        Value::Array(arr) => {
            let list = PyList::empty(py);
            for item in arr {
                list.append(value_to_py(py, item)?)?;
            }
            list.into_py(py)
        }
        Value::Object(map) => {
            let dict = PyDict::new(py);
            for (key, value) in map {
                dict.set_item(key, value_to_py(py, value)?)?;
            }
            dict.into_py(py)
        }
    })
}

pub fn py_to_value(py: Python<'_>, obj: &PyAny) -> PyResult<Value> {
    if obj.is_none() {
        return Ok(Value::Null);
    }
    if let Ok(boolean) = obj.downcast::<PyBool>() {
        return Ok(Value::Bool(boolean.is_true()));
    }
    if let Ok(int_obj) = obj.downcast::<PyInt>() {
        if let Ok(value) = int_obj.extract::<i64>() {
            return Ok(Value::Number(Number::from(value)));
        }
        if let Ok(value) = int_obj.extract::<u64>() {
            return Ok(Value::Number(Number::from(value)));
        }
    }
    if let Ok(float_obj) = obj.downcast::<PyFloat>() {
        return Ok(Value::Number(
            Number::from_f64(float_obj.value()).unwrap_or(Number::from(0)),
        ));
    }
    if let Ok(string_obj) = obj.downcast::<PyString>() {
        return Ok(Value::String(string_obj.to_str()?.to_string()));
    }
    if let Ok(list_obj) = obj.downcast::<PyList>() {
        let mut arr = Vec::with_capacity(list_obj.len());
        for item in list_obj.iter() {
            arr.push(py_to_value(py, item)?);
        }
        return Ok(Value::Array(arr));
    }
    if let Ok(tuple_obj) = obj.downcast::<PyTuple>() {
        let mut arr = Vec::with_capacity(tuple_obj.len());
        for item in tuple_obj.iter() {
            arr.push(py_to_value(py, item)?);
        }
        return Ok(Value::Array(arr));
    }
    if let Ok(dict_obj) = obj.downcast::<PyDict>() {
        let mut map = Map::with_capacity(dict_obj.len());
        for (key, value) in dict_obj.iter() {
            let key_string = key.extract::<String>()?;
            map.insert(key_string, py_to_value(py, value)?);
        }
        return Ok(Value::Object(map));
    }
    if let Ok(bytes_obj) = obj.extract::<Vec<u8>>() {
        return Ok(Value::Array(
            bytes_obj
                .into_iter()
                .map(|b| Value::Number(Number::from(b)))
                .collect(),
        ));
    }

    Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
        "Unsupported type for conversion to JSON value",
    ))
}
