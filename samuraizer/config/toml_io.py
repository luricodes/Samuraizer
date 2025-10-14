from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _format_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, str):
        return f'"{_toml_escape(value)}"'
    if isinstance(value, list):
        return "[" + ", ".join(_format_toml_value(v) for v in value) + "]"
    if value is None:
        return "null"
    raise TypeError(f"Unsupported value type for TOML serialization: {type(value)!r}")


def _iter_dict_items(data: Dict[str, Any]) -> Iterable[Tuple[str, Any]]:
    for key, value in data.items():
        yield key, value


def _toml_dumps(data: Dict[str, Any]) -> str:
    lines: List[str] = []

    def write_table(prefix: str, table: Dict[str, Any]) -> None:
        scalar_items: List[Tuple[str, Any]] = []
        sub_tables: List[Tuple[str, Dict[str, Any]]] = []

        for key, value in _iter_dict_items(table):
            if isinstance(value, dict):
                sub_tables.append((key, value))
            else:
                scalar_items.append((key, value))

        if prefix:
            lines.append(f"[{prefix}]")

        for key, value in scalar_items:
            lines.append(f"{key} = {_format_toml_value(value)}")

        if scalar_items and sub_tables:
            lines.append("")

        for key, value in sub_tables:
            new_prefix = f"{prefix}.{key}" if prefix else key
            write_table(new_prefix, value)

    write_table("", data)
    return "\n".join(lines) + "\n"


__all__ = ["_toml_escape", "_format_toml_value", "_toml_dumps"]
