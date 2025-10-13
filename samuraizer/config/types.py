# samuraizer/config/types.py

from typing import List, Optional, TypedDict


class ExclusionListConfig(TypedDict):
    exclude: List[str]


class ImageExtensionConfig(TypedDict):
    include: List[str]


class ExclusionsConfig(TypedDict):
    folders: ExclusionListConfig
    files: ExclusionListConfig
    patterns: ExclusionListConfig
    image_extensions: ImageExtensionConfig


class AnalysisConfig(TypedDict, total=False):
    default_format: str
    max_file_size_mb: int
    threads: int
    follow_symlinks: bool
    include_binary: bool
    encoding: str
    hash_algorithm: str
    cache_enabled: bool
    include_summary: bool


class CacheConfig(TypedDict, total=False):
    path: str
    size_limit_mb: int
    cleanup_days: int


class OutputConfig(TypedDict, total=False):
    compression: bool
    streaming: bool
    pretty_print: bool


class ThemeConfig(TypedDict, total=False):
    name: str


class TimezoneConfig(TypedDict, total=False):
    use_utc: bool
    repository_timezone: Optional[str]


class ConfigurationData(TypedDict, total=False):
    config_version: str
    analysis: AnalysisConfig
    cache: CacheConfig
    exclusions: ExclusionsConfig
    output: OutputConfig
    theme: ThemeConfig
    timezone: TimezoneConfig
