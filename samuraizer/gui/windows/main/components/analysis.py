"""Analysis management with dependency injected collaborators."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Coroutine, Dict, Optional

from samuraizer.config.unified import UnifiedConfigManager
from samuraizer.gui.workers.analysis.analyzer_worker import AnalyzerWorker
from samuraizer.gui.windows.main.components.analysis_dependencies import (
    AnalysisConfig,
    AnalysisConfigCollector,
    AnalysisDisplay,
    AnalysisStateController,
    MessagePresenter,
    RepositorySelector,
    RepositoryValidationError,
    RepositoryValidator,
    StatusReporter,
)
from samuraizer.gui.windows.main.components.ui_state import AnalysisState

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Custom exception for configuration validation errors."""


class AnalysisManager:
    """Coordinates analysis workflows independently of concrete UI widgets."""

    def __init__(
        self,
        repository_selector: RepositorySelector,
        repository_validator: RepositoryValidator,
        config_collector: AnalysisConfigCollector,
        analysis_display: AnalysisDisplay,
        state_controller: AnalysisStateController,
        status_reporter: StatusReporter,
        message_presenter: MessagePresenter,
    ) -> None:
        self._repository_selector = repository_selector
        self._repository_validator = repository_validator
        self._config_collector = config_collector
        self._analysis_display = analysis_display
        self._state_controller = state_controller
        self._status_reporter = status_reporter
        self._message_presenter = message_presenter

        self.analyzer_worker: Optional[AnalyzerWorker] = None
        self.analysis_task: Optional[asyncio.Task] = None
        self.current_config: Optional[AnalysisConfig] = None
        self.results_data: Optional[Dict[str, object]] = None

    def open_repository(self) -> None:
        """Open a repository for analysis using the configured selector."""

        try:
            repository_path = self._repository_selector.select_repository()
            if not repository_path:
                return

            self._repository_validator.validate(repository_path)
            self._repository_selector.notify_selection(repository_path)
            self._status_reporter.show_message(f"Repository opened: {repository_path}")
        except RepositoryValidationError as exc:
            logger.debug("Repository validation failed: %s", exc)
            self._status_reporter.show_message("Invalid repository path selected")
            self._message_presenter.warning("Invalid Repository", str(exc))
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error("Error opening repository: %s", exc, exc_info=True)
            self._message_presenter.error("Error", f"Failed to open repository: {exc}")

    def start_analysis(self) -> None:
        """Start the repository analysis."""

        self._schedule_coroutine(self.start_analysis_async())

    async def start_analysis_async(self) -> None:
        """Asynchronous workflow for starting the analysis."""

        try:
            if not self._validate_analysis_prerequisites():
                return

            assert self.current_config is not None
            config_payload = self.current_config.to_dict()

            self._analysis_display.set_configuration(config_payload)
            self._state_controller.set_analysis_state(AnalysisState.RUNNING)

            await self._setup_analysis_worker(config_payload)
            assert self.analyzer_worker is not None

            self._analysis_display.start_analysis(self.analyzer_worker)

            task = asyncio.create_task(self.analyzer_worker.run())
            self.analysis_task = task

            try:
                results = await task
            except asyncio.CancelledError:
                logger.debug("Analysis task cancelled")
                self._state_controller.set_analysis_state(AnalysisState.IDLE)
                self._status_reporter.show_message("Analysis cancelled.")
                await self._cleanup_previous_analysis_async()
            except Exception as exc:
                logger.error("Analysis task raised an exception: %s", exc, exc_info=True)
                await self._on_analysis_error_async(str(exc))
            else:
                if isinstance(results, dict):
                    await self._on_analysis_finished_async(results)
            finally:
                if self.analysis_task is task:
                    self.analysis_task = None
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error("Error starting analysis: %s", exc, exc_info=True)
            await self._on_analysis_error_async(str(exc))

    def stop_analysis(self) -> None:
        """Stop the current analysis."""

        self._schedule_coroutine(self.stop_analysis_async())

    async def stop_analysis_async(self) -> None:
        """Asynchronously stop the current analysis."""

        try:
            self._analysis_display.stop_analysis()
            await self._cleanup_previous_analysis_async()
            self._state_controller.set_analysis_state(AnalysisState.IDLE)
            self._status_reporter.show_message("Analysis stopped.")
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error("Error stopping analysis: %s", exc, exc_info=True)
            self._status_reporter.show_message(f"Error stopping analysis: {exc}")
            self._state_controller.set_analysis_state(AnalysisState.ERROR)

    def cleanup(self) -> None:
        """Cleanup resources when closing the application."""

        self._schedule_coroutine(self._cleanup_previous_analysis_async())

    def _validate_analysis_prerequisites(self) -> bool:
        """Validate all prerequisites before starting analysis."""

        try:
            self._update_configuration()
            assert self.current_config is not None

            repo_config = self.current_config.repository
            output_config = self.current_config.output

            repo_path = repo_config.repository_path
            if not repo_path:
                raise ConfigurationError("Repository path is required")

            path_obj = Path(repo_path)
            if not path_obj.exists():
                raise ConfigurationError(f"Repository directory does not exist: {repo_path}")
            if not path_obj.is_dir():
                raise ConfigurationError(f"Selected path is not a directory: {repo_path}")
            if not os.access(path_obj, os.R_OK):
                raise ConfigurationError(f"Repository directory is not readable: {repo_path}")

            output_path = output_config.output_path
            if not output_path:
                raise ConfigurationError("Output path is required")

            output_dir = Path(output_path).parent
            if not output_dir.exists():
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                except Exception as exc:  # pragma: no cover - defensive guard
                    raise ConfigurationError(f"Failed to create output directory: {exc}") from exc

            if not os.access(output_dir, os.W_OK):
                raise ConfigurationError(f"Output directory is not writable: {output_dir}")

            config_manager = UnifiedConfigManager()
            config = config_manager.get_active_profile_config()
            analysis_cfg = config.get("analysis", {})
            cache_cfg = config.get("cache", {})
            cache_disabled = not bool(analysis_cfg.get("cache_enabled", True))
            if not cache_disabled:
                cache_path = cache_cfg.get("path") or repo_config.cache_path
                cache_dir = Path(cache_path)
                try:
                    cache_dir.mkdir(parents=True, exist_ok=True)
                except Exception as exc:  # pragma: no cover - defensive guard
                    raise ConfigurationError(f"Failed to create cache directory: {exc}") from exc

                if not os.access(cache_dir, os.W_OK):
                    raise ConfigurationError(f"Cache directory is not writable: {cache_dir}")

                logger.info("Cache directory validated: %s", cache_dir)
            else:
                logger.info("Cache is disabled, skipping cache validation")

            return True
        except ConfigurationError as exc:
            self._message_presenter.warning(
                "Configuration Error",
                f"{exc}\n\nPlease check your settings and try again.",
            )
            return False
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error("Validation error: %s", exc, exc_info=True)
            self._message_presenter.error(
                "Error",
                f"Failed to validate analysis setup:\n\n{exc}\n\nCheck the logs for more details.",
            )
            return False

    def _schedule_coroutine(self, coro: Coroutine[Any, Any, Any]) -> None:
        """Dispatch a coroutine on the running event loop or execute synchronously."""

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coro)
        else:
            loop.create_task(coro)

    async def _setup_analysis_worker(self, config_payload: Dict[str, object]) -> None:
        """Set up the analysis worker, ensuring previous state is cleared."""

        try:
            await self._cleanup_previous_analysis_async()
            self.analyzer_worker = AnalyzerWorker(config_payload)
        except Exception as exc:
            logger.error("Error setting up worker: %s", exc, exc_info=True)
            raise

    async def _on_analysis_finished_async(self, results: Dict[str, object]) -> None:
        """Handle analysis completion."""

        self.results_data = results
        self._state_controller.set_analysis_state(AnalysisState.COMPLETED)
        await self._cleanup_previous_analysis_async()

    async def _on_analysis_error_async(self, error_message: str) -> None:
        """Handle analysis error."""

        self._message_presenter.error(
            "Analysis Error",
            f"An error occurred during analysis:\n\n{error_message}\n\nCheck the logs for more details.",
        )
        self._state_controller.set_analysis_state(AnalysisState.ERROR)
        await self._cleanup_previous_analysis_async()

    async def _cancel_analysis_task_async(self) -> None:
        """Cancel any running analysis task asynchronously."""

        task = self.analysis_task
        if task is None:
            return

        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.debug("Analysis task raised during cancellation: %s", exc, exc_info=True)

        if self.analysis_task is task:
            self.analysis_task = None

    async def _cleanup_previous_analysis_async(self) -> None:
        """Clean up previous analysis resources asynchronously."""

        try:
            await self._cancel_analysis_task_async()

            if self.analyzer_worker:
                try:
                    self.analyzer_worker.stop()
                except Exception:
                    logger.debug("Failed to stop analyzer worker during cleanup", exc_info=True)

                try:
                    self.analyzer_worker.deleteLater()
                except Exception:
                    logger.debug("Analyzer worker already deleted", exc_info=True)

            self.analyzer_worker = None
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error("Error cleaning up analysis: %s", exc, exc_info=True)

    def _update_configuration(self) -> None:
        """Update the current configuration from the configured collector."""

        try:
            config = self._config_collector.collect()
            self.current_config = config
        except RepositoryValidationError as exc:
            logger.error("Configuration error: %s", exc)
            raise ConfigurationError(str(exc)) from exc
        except Exception as exc:
            logger.error("Error updating configuration: %s", exc, exc_info=True)
            raise ConfigurationError(f"Failed to update configuration: {exc}") from exc
