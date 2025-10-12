"""Progressive writers for materialising traversal results without buffering everything."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape as xml_escape

import yaml

from .formatters.csv.csv_output import output_to_csv_stream
from .formatters.jsonl.jsonl_output import output_to_jsonl
from .formatters.msgpack.msgpack_output import output_to_msgpack_stream
from .formatters.dot.dot_output import sanitize_dot_id, sanitize_dot_label
from .formatters.sexp.s_expression_output import format_atom, format_file_entry

PathParts = List[str]
EntryIterator = Iterator[Tuple[PathParts, Dict[str, object]]]


@dataclass
class _Context:
    indent_level: int
    has_items: bool = False


def write_progressive_output(
    *,
    fmt: str,
    entries: EntryIterator,
    summary: Dict[str, object],
    output_file: str,
    config: Optional[Dict[str, object]] = None,
    include_summary: bool = True,
) -> None:
    """Dispatch to the appropriate progressive writer for ``fmt``."""

    fmt = fmt.lower()
    config = config or {}

    if fmt == "json":
        _write_json(entries, summary if include_summary else {}, output_file, config)
    elif fmt == "jsonl":
        _write_jsonl(entries, summary if include_summary else {}, output_file, config)
    elif fmt == "msgpack":
        _write_msgpack(entries, summary if include_summary else {}, output_file, config)
    elif fmt == "csv":
        _write_csv(entries, output_file, config)
    elif fmt == "yaml":
        _write_yaml(entries, summary if include_summary else {}, output_file, config)
    elif fmt == "xml":
        _write_xml(entries, summary if include_summary else {}, output_file, config)
    elif fmt == "dot":
        _write_dot(entries, summary if include_summary else {}, output_file, config)
    elif fmt == "sexp":
        _write_sexp(entries, summary if include_summary else {}, output_file, config)
    else:
        raise ValueError(f"Progressive output is not supported for format '{fmt}'.")


def _normalize_entry(parts: Sequence[str], info: Dict[str, object]) -> Tuple[str, str, str, Dict[str, object]]:
    parent = "/".join(parts[:-1])
    filename = parts[-1]
    path = parent + "/" + filename if parent else filename
    return parent, filename, path, info


def _iter_entry_records(entries: EntryIterator) -> Iterator[Dict[str, object]]:
    for parts, info in entries:
        if not parts:
            continue
        parent, filename, path, data = _normalize_entry(parts, info)
        yield {
            "parent": parent,
            "filename": filename,
            "path": path,
            "info": data,
        }


def _write_json(entries: EntryIterator, summary: Dict[str, object], output_file: str, config: Dict[str, object]) -> None:
    pretty = bool(config.get("pretty_print", True))
    indent_size = 4 if pretty else 0

    def _indent(level: int) -> str:
        return " " * (indent_size * level) if pretty else ""

    def _prepare(ctx: _Context, fh) -> None:
        if ctx.has_items:
            fh.write(",")
        if pretty:
            fh.write("\n")
            fh.write(_indent(ctx.indent_level))
        ctx.has_items = True

    def _write_value(fh, ctx: _Context, key: str, value: object) -> None:
        _prepare(ctx, fh)
        fh.write(json.dumps(key))
        fh.write(": ")
        if pretty and indent_size:
            text = json.dumps(value, ensure_ascii=False, indent=indent_size)
            lines = text.splitlines()
            if len(lines) == 1:
                fh.write(lines[0])
            else:
                fh.write(lines[0])
                for line in lines[1:]:
                    fh.write("\n")
                    fh.write(_indent(ctx.indent_level + 1))
                    fh.write(line)
        else:
            fh.write(json.dumps(value, ensure_ascii=False))

    with open(output_file, "w", encoding="utf-8") as fh:
        fh.write("{")
        contexts: List[_Context] = [_Context(indent_level=1, has_items=False)]

        _prepare(contexts[-1], fh)
        fh.write('"structure": ')
        fh.write("{")
        contexts.append(_Context(indent_level=contexts[-1].indent_level + 1, has_items=False))

        stack: List[str] = []

        def _close_directory() -> None:
            contexts.pop()
            stack.pop()
            if pretty:
                fh.write("\n")
                fh.write(_indent(contexts[-1].indent_level))
            fh.write("}")

        for parts, info in entries:
            if not parts:
                continue
            directory_parts = parts[:-1]
            filename = parts[-1]

            while len(stack) > len(directory_parts):
                _close_directory()

            for idx in range(len(stack), len(directory_parts)):
                dir_name = directory_parts[idx]
                parent_ctx = contexts[-1]
                _prepare(parent_ctx, fh)
                fh.write(json.dumps(dir_name))
                fh.write(": ")
                fh.write("{")
                contexts.append(_Context(indent_level=parent_ctx.indent_level + 1, has_items=False))
                stack.append(dir_name)

            current_ctx = contexts[-1]
            _write_value(current_ctx, filename, info)

        while stack:
            _close_directory()

        contexts.pop()
        if pretty:
            fh.write("\n")
            fh.write(_indent(contexts[-1].indent_level))
        fh.write("}")

        if summary:
            _write_value(contexts[-1], "summary", summary)

        if pretty:
            fh.write("\n")
        fh.write("}")


def _write_jsonl(entries: EntryIterator, summary: Dict[str, object], output_file: str, config: Dict[str, object]) -> None:
    def _generator() -> Iterator[Dict[str, object]]:
        yield from _iter_entry_records(entries)
        if summary:
            yield {"summary": summary}

    output_to_jsonl(_generator(), output_file, config)


def _write_msgpack(entries: EntryIterator, summary: Dict[str, object], output_file: str, config: Dict[str, object]) -> None:
    def _generator() -> Iterator[Dict[str, object]]:
        yield from _iter_entry_records(entries)
        if summary:
            yield {"summary": summary}

    output_to_msgpack_stream(_generator(), output_file, config)


def _write_csv(entries: EntryIterator, output_file: str, config: Dict[str, object]) -> None:
    output_to_csv_stream(_iter_entry_records(entries), output_file, config)


def _write_yaml(entries: EntryIterator, summary: Dict[str, object], output_file: str, config: Dict[str, object]) -> None:
    indent = int(config.get("indent", 2)) if config.get("indent") is not None else 2
    if indent <= 0:
        indent = 2

    def _indent(level: int) -> str:
        return " " * (indent * level)

    with open(output_file, "w", encoding="utf-8") as fh:
        fh.write("structure:\n")
        stack: List[str] = []

        for parts, info in entries:
            if not parts:
                continue
            directories = parts[:-1]
            filename = parts[-1]

            while len(stack) > len(directories):
                stack.pop()

            for idx in range(len(stack), len(directories)):
                dir_name = directories[idx]
                fh.write(f"{_indent(idx + 1)}{dir_name}:\n")
                stack.append(dir_name)

            fh.write(f"{_indent(len(directories) + 1)}{filename}:\n")
            dumped = yaml.safe_dump(info, allow_unicode=True, sort_keys=False).splitlines()
            for line in dumped:
                fh.write(f"{_indent(len(directories) + 2)}{line}\n")

        if summary:
            fh.write("summary:\n")
            dumped = yaml.safe_dump(summary, allow_unicode=True, sort_keys=False).splitlines()
            for line in dumped:
                fh.write(f"{_indent(1)}{line}\n")


def _write_xml(entries: EntryIterator, summary: Dict[str, object], output_file: str, config: Dict[str, object]) -> None:
    pretty = bool(config.get("pretty_print", True))
    indent_size = 2 if pretty else 0

    def _indent(level: int) -> str:
        return " " * (indent_size * level) if pretty else ""

    with open(output_file, "w", encoding="utf-8") as fh:
        fh.write("<repository>\n" if pretty else "<repository>")
        stack: List[str] = []

        def _open_directory(name: str, level: int) -> None:
            if pretty:
                fh.write(f"{_indent(level)}<directory name=\"{xml_escape(name)}\">\n")
            else:
                fh.write(f"<directory name=\"{xml_escape(name)}\">")
            stack.append(name)

        def _close_directory(level: int) -> None:
            if pretty:
                fh.write(f"{_indent(level)}</directory>\n")
            else:
                fh.write("</directory>")
            stack.pop()

        for parts, info in entries:
            if not parts:
                continue
            directories = parts[:-1]
            filename = parts[-1]

            while len(stack) > len(directories):
                _close_directory(len(stack))

            for idx in range(len(stack), len(directories)):
                _open_directory(directories[idx], idx + 1)

            if pretty:
                fh.write(f"{_indent(len(directories) + 1)}<file name=\"{xml_escape(filename)}\">\n")
            else:
                fh.write(f"<file name=\"{xml_escape(filename)}\">")
            for key, value in info.items():
                text = value
                if isinstance(value, str):
                    text = xml_escape(value)
                if pretty:
                    fh.write(f"{_indent(len(directories) + 2)}<{key}>{text}</{key}>\n")
                else:
                    fh.write(f"<{key}>{text}</{key}>")
            if pretty:
                fh.write(f"{_indent(len(directories) + 1)}</file>\n")
            else:
                fh.write("</file>")

        while stack:
            _close_directory(len(stack))

        if summary:
            if pretty:
                fh.write(f"{_indent(1)}<summary>\n")
                for key, value in summary.items():
                    fh.write(f"{_indent(2)}<{key}>{xml_escape(str(value))}</{key}>\n")
                fh.write(f"{_indent(1)}</summary>\n")
                fh.write("</repository>\n")
            else:
                fh.write("<summary>")
                for key, value in summary.items():
                    fh.write(f"<{key}>{xml_escape(str(value))}</{key}>")
                fh.write("</summary></repository>")
        else:
            fh.write("</repository>\n" if pretty else "</repository>")


def _write_dot(entries: EntryIterator, summary: Dict[str, object], output_file: str, config: Dict[str, object]) -> None:
    dir_color = config.get("dir_color", "#FFA500")
    file_color = config.get("file_color", "#90EE90")
    summary_color = config.get("summary_color", "#D3D3D3")
    include_content = config.get("include_content", False)
    rankdir = config.get("rankdir", "LR")

    created_dirs: set[str] = set()

    with open(output_file, "w", encoding="utf-8") as fh:
        fh.write("digraph RepositoryStructure {\n")
        fh.write('    node [shape=box, style=filled, color="#ADD8E6"];\n')
        fh.write(f"    rankdir={rankdir};\n")

        for parts, info in entries:
            if not parts:
                continue
            path = Path(*parts)
            directories = parts[:-1]
            filename = parts[-1]

            parent_id = None
            running_path = Path()
            for directory in directories:
                running_path = running_path / directory
                node_id = sanitize_dot_id(str(running_path))
                if node_id not in created_dirs:
                    created_dirs.add(node_id)
                    fh.write(
                        f'    "{node_id}" [label="{directory}", shape=folder, color="{dir_color}"];\n'
                    )
                if parent_id and parent_id != node_id:
                    fh.write(f'    "{parent_id}" -> "{node_id}";\n')
                parent_id = node_id

            file_id = sanitize_dot_id(str(path))
            label = filename.replace('"', '\\"')
            if include_content and isinstance(info.get("content"), str):
                content = sanitize_dot_label(info["content"][:1024])
                label += f"\\nContent: {content}"
            fh.write(f'    "{file_id}" [label="{label}", shape=note, color="{file_color}"];\n')
            if parent_id:
                fh.write(f'    "{parent_id}" -> "{file_id}";\n')

        if summary:
            summary_id = sanitize_dot_id("summary")
            fh.write("\n    subgraph cluster_summary {\n")
            fh.write('        label="Summary";\n')
            fh.write("        color=lightgrey;\n")
            for key, value in summary.items():
                node_id = f"{summary_id}_{sanitize_dot_id(key)}"
                fh.write(
                    f'        "{node_id}" [label="{key}: {value}", shape=note, color="{summary_color}"];\n'
                )
            fh.write("    }\n")
        fh.write("}\n")


def _write_sexp(entries: EntryIterator, summary: Dict[str, object], output_file: str, config: Dict[str, object]) -> None:
    include_content = config.get("include_content", True)
    with open(output_file, "w", encoding="utf-8") as fh:
        fh.write("(repository\n")
        stack: List[str] = []

        def _indent(level: int) -> str:
            return "  " * level

        for parts, info in entries:
            if not parts:
                continue
            directories = parts[:-1]
            filename = parts[-1]

            while len(stack) > len(directories):
                fh.write(f"{_indent(len(stack))})\n")
                stack.pop()

            for idx in range(len(stack), len(directories)):
                dir_name = directories[idx]
                fh.write(f"{_indent(idx + 1)}(directory {format_atom(dir_name, 'name')}\n")
                stack.append(dir_name)

            fh.write(format_file_entry(filename, info, _indent(len(directories) + 1), include_content))
            fh.write("\n")

        while stack:
            fh.write(f"{_indent(len(stack))})\n")
            stack.pop()

        if summary:
            fh.write("  (summary\n")
            for key, value in summary.items():
                fh.write(f"    ({format_atom(key)} {format_atom(value)})\n")
            fh.write("  )\n")
        fh.write(")\n")
