"""Dependency abstractions and helpers for the analysis manager."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Protocol, runtime_checkable, Sequence

from PyQt6.QtWidgets import QMessageBox

from samuraizer.config.unified import UnifiedConfigManager


class RepositoryValidationError(Exception):
    """Raised when a repository selection fails validation."""


@dataclass(frozen=True)
class RepositoryConfig:
    """Repository related configuration for an analysis run."""

    repository_path: str
    max_file_size: int = 50
    include_binary: bool = False
    follow_symlinks: bool = False
    encoding: Optional[str] = None
    hash_algorithm: str = "xxhash"
    thread_count: int = 4
    image_extensions: Sequence[str] = field(default_factory=tuple)
    cache_path: str = ".cache"


@dataclass(frozen=True)
class FiltersConfig:
    """Filtering rules used during analysis."""

    excluded_folders: Sequence[str] = field(default_factory=tuple)
    excluded_files: Sequence[str] = field(default_factory=tuple)
    exclude_patterns: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class OutputConfig:
    """Output configuration for reporting analysis results."""

    format: str = "json"
    output_path: str = ""
    streaming: bool = False
    include_summary: bool = True
    pretty_print: bool = True
    use_compression: bool = False


@dataclass(frozen=True)
class AnalysisConfig:
    """Complete configuration payload for the analyzer worker."""

    repository: RepositoryConfig
    filters: FiltersConfig
    output: OutputConfig

    def to_dict(self) -> Dict[str, object]:
        """Convert the dataclass hierarchy into a worker friendly dictionary."""

        repository_config: Dict[str, object] = {
            "repository_path": self.repository.repository_path,
            "max_file_size": self.repository.max_file_size,
            "include_binary": self.repository.include_binary,
            "follow_symlinks": self.repository.follow_symlinks,
            "encoding": self.repository.encoding,
            "hash_algorithm": self.repository.hash_algorithm,
            "thread_count": self.repository.thread_count,
            "image_extensions": list(self.repository.image_extensions),
            "cache_path": self.repository.cache_path,
        }

        filters_config: Dict[str, object] = {
            "excluded_folders": list(self.filters.excluded_folders),
            "excluded_files": list(self.filters.excluded_files),
            "exclude_patterns": list(self.filters.exclude_patterns),
        }

        output_config: Dict[str, object] = {
            "format": self.output.format,
            "output_path": self.output.output_path,
            "streaming": self.output.streaming,
            "include_summary": self.output.include_summary,
            "pretty_print": self.output.pretty_print,
            "use_compression": self.output.use_compression,
        }

        return {
            "repository": repository_config,
            "filters": filters_config,
            "output": output_config,
        }


@runtime_checkable
class RepositorySelector(Protocol):
    """Abstraction for browsing and selecting a repository path."""

    def select_repository(self) -> Optional[str]:
        """Prompt the user to select a repository and return the chosen path."""

    def notify_selection(self, repository_path: str) -> None:
        """Notify interested parties that a repository path has been selected."""


@runtime_checkable
class RepositoryValidator(Protocol):
    """Validates repository selections."""

    def validate(self, repository_path: str) -> None:
        """Validate a repository path or raise :class:`RepositoryValidationError`."""


@runtime_checkable
class AnalysisConfigCollector(Protocol):
    """Collects analysis configuration from an external source."""

    def collect(self) -> AnalysisConfig:
        """Collect and return an :class:`AnalysisConfig`."""


@runtime_checkable
class AnalysisDisplay(Protocol):
    """Display surface that renders analysis progress."""

    def set_configuration(self, config: Dict[str, object]) -> None:
        """Provide the configuration to the display surface."""

    def start_analysis(self, worker) -> None:  # pragma: no cover - Qt wiring
        """Start rendering an analysis run using the given worker."""

    def stop_analysis(self) -> None:  # pragma: no cover - Qt wiring
        """Stop rendering the current analysis run."""


@runtime_checkable
class AnalysisStateController(Protocol):
    """Controls the state of the analysis workflow."""

    def set_analysis_state(self, state) -> None:  # pragma: no cover - UI state propagation
        """Update the analysis state."""


@runtime_checkable
class StatusReporter(Protocol):
    """Abstraction for reporting status messages to the user."""

    def show_message(self, message: str) -> None:
        """Display a transient status message."""


@runtime_checkable
class MessagePresenter(Protocol):
    """Abstraction over user facing message dialogs."""

    def warning(self, title: str, message: str) -> None:
        """Show a warning dialog to the user."""

    def error(self, title: str, message: str) -> None:
        """Show an error dialog to the user."""


class QMessagePresenter(MessagePresenter):
    """Qt backed implementation of :class:`MessagePresenter`."""

    def __init__(self, parent) -> None:
        self._parent = parent

    def warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self._parent, title, message)

    def error(self, title: str, message: str) -> None:
        QMessageBox.critical(self._parent, title, message)


class UIStatusReporter(StatusReporter):
    """Status reporter implementation backed by a Qt status bar."""

    def __init__(self, status_bar) -> None:
        self._status_bar = status_bar

    def show_message(self, message: str) -> None:
        self._status_bar.showMessage(message)


class UIRepositorySelector(RepositorySelector):
    """Repository selector backed by the repository widget."""

    def __init__(self, repository_widget) -> None:
        self._repository_widget = repository_widget

    def select_repository(self) -> Optional[str]:
        self._repository_widget.browseRepository()
        path = self._repository_widget.repo_path.text()
        return path or None

    def notify_selection(self, repository_path: str) -> None:
        self._repository_widget.pathChanged.emit(repository_path)


class UIRepositoryValidator(RepositoryValidator):
    """Repository validator that delegates to the repository widget."""

    def __init__(self, repository_widget) -> None:
        self._repository_widget = repository_widget

    def validate(self, repository_path: str) -> None:
        is_valid, error_message = self._repository_widget.validate()
        if not is_valid:
            raise RepositoryValidationError(error_message or "Invalid repository path")


class UIAnalysisDisplay(AnalysisDisplay):
    """Bridge between the analysis manager and the right panel."""

    def __init__(self, right_panel) -> None:
        self._right_panel = right_panel

    def set_configuration(self, config: Dict[str, object]) -> None:
        self._right_panel.setConfiguration(config)

    def start_analysis(self, worker) -> None:  # pragma: no cover - Qt wiring
        self._right_panel.startAnalysis(worker)

    def stop_analysis(self) -> None:  # pragma: no cover - Qt wiring
        self._right_panel.stopAnalysis()


class UIAnalysisConfigCollector(AnalysisConfigCollector):
    """Collects configuration data from the left panel widgets."""

    _DEFAULT_IMAGE_EXTENSIONS: Iterable[str] = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".svg",
        ".webp",
        ".tiff",
        ".ico",
    )

    def __init__(self, left_panel, repository_validator: RepositoryValidator) -> None:
        self._left_panel = left_panel
        self._repository_validator = repository_validator

    def collect(self) -> AnalysisConfig:
        repository_config = self._left_panel.analysis_options.get_configuration()
        filters_config = self._left_panel.file_filters.get_configuration()
        output_config = self._left_panel.output_options.get_configuration()

        repository_path = repository_config.get("repository_path", "")
        if not repository_path:
            raise RepositoryValidationError("Repository path is required")

        self._repository_validator.validate(repository_path)

        repo_cfg = RepositoryConfig(
            repository_path=repository_path,
            max_file_size=repository_config.get("max_file_size", 50),
            include_binary=repository_config.get("include_binary", False),
            follow_symlinks=repository_config.get("follow_symlinks", False),
            encoding=repository_config.get("encoding"),
            hash_algorithm=repository_config.get("hash_algorithm", "xxhash"),
            thread_count=repository_config.get("thread_count", 4),
            image_extensions=tuple(
                repository_config.get("image_extensions", self._DEFAULT_IMAGE_EXTENSIONS)
                or self._DEFAULT_IMAGE_EXTENSIONS
            ),
            cache_path=repository_config.get("cache_path", ".cache"),
        )

        filters_cfg = FiltersConfig(
            excluded_folders=tuple(filters_config.get("excluded_folders", [])),
            excluded_files=tuple(filters_config.get("excluded_files", [])),
            exclude_patterns=tuple(filters_config.get("exclude_patterns", [])),
        )

        output_cfg = OutputConfig(
            format=output_config.get("format", "json").lower(),
            output_path=output_config.get("output_path", ""),
            streaming=output_config.get("streaming", False),
            include_summary=output_config.get("include_summary", True),
            pretty_print=output_config.get("pretty_print", True),
            use_compression=output_config.get("use_compression", False),
        )

        config_manager = UnifiedConfigManager()
        config_manager.set_value("analysis.max_file_size_mb", repo_cfg.max_file_size)
        config_manager.set_value("analysis.include_binary", repo_cfg.include_binary)
        config_manager.set_value("analysis.follow_symlinks", repo_cfg.follow_symlinks)
        config_manager.set_value("analysis.encoding", repo_cfg.encoding or "auto")
        config_manager.set_value("analysis.threads", repo_cfg.thread_count)
        config_manager.set_value("analysis.hash_algorithm", repo_cfg.hash_algorithm)
        if repo_cfg.cache_path:
            config_manager.set_value("cache.path", repo_cfg.cache_path)
        if output_cfg.format:
            config_manager.set_value("analysis.default_format", output_cfg.format)
        config_manager.set_value("analysis.include_summary", output_cfg.include_summary)
        config_manager.set_value("output.streaming", output_cfg.streaming)
        config_manager.set_value("output.pretty_print", output_cfg.pretty_print)
        config_manager.set_value("output.compression", output_cfg.use_compression)

        return AnalysisConfig(
            repository=repo_cfg,
            filters=filters_cfg,
            output=output_cfg,
        )
