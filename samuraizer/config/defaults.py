from __future__ import annotations

from typing import Any, Dict

from .compat import tomllib

DEFAULT_CONFIG_TOML = """\
# Version tracking for migrations
config_version = "1.0"

[analysis]
# Default analysis settings
default_format = "json"
max_file_size_mb = 50
threads = 4
follow_symlinks = false
include_binary = false
encoding = "auto"
cache_enabled = true
include_summary = true

[cache]
path = "~/.cache/samurai"
size_limit_mb = 1000
cleanup_days = 30

[exclusions.folders]
exclude = ["node_modules", ".git", "__pycache__", ".venv", "dist", "build"]

[exclusions.files]
exclude = ["*.tmp", "config.json", ".repo_structure_cache", "package-lock.json", "favicon.ico"]

[exclusions.patterns]
exclude = ["*.pyc", "*.pyo", "*.pyd", ".DS_Store", "Thumbs.db"]

[exclusions.image_extensions]
include = [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".ico"]

[output]
compression = false
streaming = false  # auto-enabled for jsonl, msgpack
pretty_print = true
path = ""

[theme]
name = "dark"  # only applies to gui mode

[timezone]
use_utc = false

[profiles.work]
inherit = "default"
cache_enabled = false
threads = 8

[profiles.work.exclusions]
additional_folders = ["dist", "build", ".next"]

[profiles.portable]
inherit = "default"
cache_enabled = false
max_file_size_mb = 10

[profiles.portable.output]
compression = true
"""

DEFAULT_CONFIG: Dict[str, Any] = tomllib.loads(DEFAULT_CONFIG_TOML)

CONFIG_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "config_version": {"type": "string"},
        "analysis": {
            "type": "object",
            "properties": {
                "default_format": {"type": "string"},
                "max_file_size_mb": {"type": "integer", "minimum": 0},
                "threads": {"type": "integer", "minimum": 1},
                "follow_symlinks": {"type": "boolean"},
                "include_binary": {"type": "boolean"},
                "encoding": {"type": "string"},
                "cache_enabled": {"type": "boolean"},
                "include_summary": {"type": "boolean"},
            },
            "required": [
                "default_format",
                "max_file_size_mb",
                "threads",
                "follow_symlinks",
                "include_binary",
                "encoding",
                "cache_enabled",
                "include_summary",
            ],
            "additionalProperties": True,
        },
        "cache": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "size_limit_mb": {"type": "integer", "minimum": 0},
                "cleanup_days": {"type": "integer", "minimum": 0},
            },
            "required": ["path", "size_limit_mb", "cleanup_days"],
            "additionalProperties": True,
        },
        "exclusions": {
            "type": "object",
            "properties": {
                "folders": {
                    "type": "object",
                    "properties": {
                        "exclude": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["exclude"],
                },
                "files": {
                    "type": "object",
                    "properties": {
                        "exclude": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["exclude"],
                },
                "patterns": {
                    "type": "object",
                    "properties": {
                        "exclude": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["exclude"],
                },
                "image_extensions": {
                    "type": "object",
                    "properties": {
                        "include": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["include"],
                },
            },
            "required": ["folders", "files", "patterns", "image_extensions"],
            "additionalProperties": True,
        },
        "output": {
            "type": "object",
            "properties": {
                "compression": {"type": "boolean"},
                "streaming": {"type": "boolean"},
                "pretty_print": {"type": "boolean"},
                "path": {"type": "string"},
            },
            "required": ["compression", "streaming", "pretty_print"],
            "additionalProperties": True,
        },
        "theme": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
        "timezone": {
            "type": "object",
            "properties": {
                "use_utc": {"type": "boolean"},
                "repository_timezone": {"type": "string", "minLength": 1},
            },
            "required": ["use_utc"],
        },
        "profiles": {"type": "object"},
    },
    "required": [
        "config_version",
        "analysis",
        "cache",
        "exclusions",
        "output",
        "theme",
        "timezone",
    ],
    "additionalProperties": True,
}

__all__ = ["DEFAULT_CONFIG_TOML", "DEFAULT_CONFIG", "CONFIG_SCHEMA"]
