# samuraizer/gui/widgets/configuration/analysis_options.py

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QLabel,
    QFrame,
    QHBoxLayout,
)
from PyQt6.QtCore import QSettings, Qt

from samuraizer.config.config_manager import ConfigurationManager

from ..github_integration.repository_selection import RepositorySelectionWidget
from .analysis_settings.analysis_configuration import AnalysisConfigurationWidget
from .analysis_settings.threading_options import ThreadingOptionsWidget

logger = logging.getLogger(__name__)


class SectionCard(QFrame):
    """Reusable visual container that mimics a modern settings card."""

    def __init__(self, title: str, subtitle: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("analysisSectionCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("analysisSectionTitle")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("analysisSectionSubtitle")
            subtitle_label.setWordWrap(True)
            layout.addWidget(subtitle_label)

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(16)
        layout.addLayout(self.content_layout)

    def addWidget(self, widget: QWidget) -> None:
        self.content_layout.addWidget(widget)


class AnalysisOptionsWidget(QWidget):
    """Main widget for configuring analysis options."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings()
        self.config_manager = ConfigurationManager()
        self.initUI()
        self.loadSettings()

    def initUI(self) -> None:
        """Initialize the user interface."""
        self.setObjectName("analysisOptionsRoot")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(16)

        header = QLabel("Analysis Setup")
        header.setObjectName("analysisOptionsHeading")
        subheader = QLabel("Follow the guided steps to prepare your repository analysis. Start by selecting a source, refine how files are processed, and finally tune performance settings.")
        subheader.setObjectName("analysisOptionsSubheading")
        subheader.setWordWrap(True)

        main_layout.addWidget(header)
        main_layout.addWidget(subheader)

        # Create a scroll area
        scroll_area = QScrollArea()
        scroll_area.setObjectName("analysisOptionsScroll")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Create a container widget for the scroll area
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(18)

        # Repository Selection
        self.repository_widget = RepositorySelectionWidget()
        self.repository_widget.pathChanged.connect(self.onPathChanged)
        repository_card = SectionCard(
            "Step 1 · Repository Source",
            "Import one or multiple repositories. Use the tabs to add local directories or clone directly from GitHub.",
        )
        repository_card.addWidget(self.repository_widget)
        layout.addWidget(repository_card)

        # Analysis Configuration
        self.analysis_config_widget = AnalysisConfigurationWidget()
        analysis_card = SectionCard(
            "Step 2 · Analysis Rules",
            "Control how Samuraizer interprets file content, limits binary data, and preview encoding before running the analysis.",
        )
        analysis_card.addWidget(self.analysis_config_widget)
        layout.addWidget(analysis_card)

        # Threading Options
        self.threading_options_widget = ThreadingOptionsWidget()
        threading_card = SectionCard(
            "Step 3 · Performance",
            "Allocate worker threads to balance speed and resource usage for your environment.",
        )
        threading_card.addWidget(self.threading_options_widget)
        layout.addWidget(threading_card)

        layout.addStretch()

        # Set the container as the scroll area's widget
        scroll_area.setWidget(container)

        # Add the scroll area to the main layout
        main_layout.addWidget(scroll_area)

        self._apply_styles()

    def _apply_styles(self) -> None:
        """Apply local styling to achieve a polished appearance."""

        self.setStyleSheet(
            """
            #analysisOptionsRoot {
                background: transparent;
            }
            #analysisOptionsHeading {
                font-size: 20px;
                font-weight: 600;
            }
            #analysisOptionsSubheading {
                color: palette(mid);
                font-size: 13px;
            }
            QScrollArea#analysisOptionsScroll {
                border: none;
            }
            #analysisOptionsScroll QWidget {
                background: transparent;
            }
            QFrame#analysisSectionCard {
                border: 1px solid palette(midlight);
                border-radius: 14px;
                background: palette(base);
            }
            #analysisSectionTitle {
                font-size: 15px;
                font-weight: 600;
            }
            #analysisSectionSubtitle {
                color: palette(mid);
                font-size: 12px;
            }
            QFrame#analysisSectionCard QLabel {
                color: palette(text);
            }
            """
        )

    def onPathChanged(self, path):
        """Handle repository path changes."""
        self.settings.setValue("analysis/last_repository", path)

    def loadSettings(self):
        """Load saved settings."""
        try:
            # Load last used repository
            last_repo = self.settings.value("analysis/last_repository", "")
            if last_repo:
                self.repository_widget.set_repository_path(last_repo)

            config = self.config_manager.get_active_profile_config()
            analysis_cfg = config.get("analysis", {})

            max_file_size = int(analysis_cfg.get("max_file_size_mb", 50))
            self.analysis_config_widget.max_size.setValue(max_file_size)

            include_binary = bool(analysis_cfg.get("include_binary", False))
            self.analysis_config_widget.include_binary.setChecked(include_binary)

            follow_symlinks = bool(analysis_cfg.get("follow_symlinks", False))
            self.analysis_config_widget.follow_symlinks.setChecked(follow_symlinks)

            encoding_value = analysis_cfg.get("encoding", "auto") or "auto"
            self.analysis_config_widget.encoding.setCurrentText(str(encoding_value))

            threads = analysis_cfg.get("threads") or 4
            self.threading_options_widget.thread_count.setValue(int(threads))

        except Exception as e:
            logger.error(f"Error loading settings: {e}", exc_info=True)

    def saveSettings(self):
        """Save current settings."""
        try:
            self.settings.setValue("analysis/max_file_size", self.analysis_config_widget.max_size.value())
            self.settings.setValue("analysis/include_binary", self.analysis_config_widget.include_binary.isChecked())
            self.settings.setValue("analysis/follow_symlinks", self.analysis_config_widget.follow_symlinks.isChecked())
            self.settings.setValue("analysis/encoding", self.analysis_config_widget.encoding.currentText())
            self.settings.setValue("analysis/thread_count", self.threading_options_widget.thread_count.value())
            
            # Remove old pool_size setting if it exists
            self.settings.remove("analysis/pool_size")

            # Synchronise with unified configuration
            self.config_manager.set_value("analysis.max_file_size_mb", self.analysis_config_widget.max_size.value())
            self.config_manager.set_value("analysis.include_binary", self.analysis_config_widget.include_binary.isChecked())
            self.config_manager.set_value("analysis.follow_symlinks", self.analysis_config_widget.follow_symlinks.isChecked())
            encoding = self.analysis_config_widget.encoding.currentText() or "auto"
            self.config_manager.set_value("analysis.encoding", encoding)
            self.config_manager.set_value("analysis.threads", self.threading_options_widget.thread_count.value())
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}", exc_info=True)

    def validateInputs(self) -> bool:
        """Validate the analysis options."""
        repo_path = self.repository_widget.get_repository_path().strip()
        if not repo_path:
            return False
        if not Path(repo_path).exists():
            return False
        return True

    def get_configuration(self) -> dict:
        """Get the current configuration as a dictionary."""
        return {
            'repository_path': self.repository_widget.get_repository_path(),
            'max_file_size': self.analysis_config_widget.max_size.value(),
            'include_binary': self.analysis_config_widget.include_binary.isChecked(),
            'follow_symlinks': self.analysis_config_widget.follow_symlinks.isChecked(),
            'encoding': None if self.analysis_config_widget.encoding.currentText() == "auto" else self.analysis_config_widget.encoding.currentText(),
            'thread_count': self.threading_options_widget.thread_count.value(),
        }
