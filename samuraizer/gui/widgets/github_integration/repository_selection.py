# samuraizer/gui/widgets/configuration/repository/repository_selection.py

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional
import logging

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QTabWidget,
    QLabel,
    QFrame,
    QGridLayout,
    QToolButton,
    QStyle,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon

from .github_widget import GitHubWidget
from .repository_list_widget import RepositoryListWidget

logger = logging.getLogger(__name__)


class RepositorySummaryCard(QFrame):
    """Compact summary widget for the currently selected repository."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("repositorySummaryCard")

        self._path_exists = False

        layout = QGridLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(6)

        # Header row
        title = QLabel("Active Repository")
        title.setObjectName("summaryTitle")
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.status_badge = QLabel("Not selected")
        self.status_badge.setObjectName("repoStatusBadge")
        self.status_badge.setProperty("status", "pending")

        layout.addWidget(title, 0, 0, 1, 2)
        layout.addWidget(self.status_badge, 0, 2, alignment=Qt.AlignmentFlag.AlignRight)

        # Repository path row
        path_label = QLabel("Path")
        path_label.setProperty("summaryLabel", True)
        self.path_field = QLineEdit()
        self.path_field.setReadOnly(True)
        self.path_field.setObjectName("repoPathDisplay")
        self.path_field.setPlaceholderText("No repository selected")

        self.copy_button = QToolButton()
        self.copy_button.setObjectName("copyRepoPathButton")
        icon = QIcon.fromTheme("edit-copy")
        if icon.isNull():
            style: Optional[QStyle] = self.style()
            if style is None:
                app = QApplication.instance()
                style = app.style() if isinstance(app, QApplication) else None
            if style is not None:
                icon = style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        self.copy_button.setIcon(icon)
        self.copy_button.setToolTip("Copy repository path to clipboard")
        self.copy_button.clicked.connect(self._copy_path_to_clipboard)

        layout.addWidget(path_label, 1, 0)
        layout.addWidget(self.path_field, 1, 1)
        layout.addWidget(self.copy_button, 1, 2)

        # Metadata rows
        source_label = QLabel("Source")
        source_label.setProperty("summaryLabel", True)
        self.source_value = QLabel("—")
        self.source_value.setObjectName("repoSourceValue")

        branch_label = QLabel("Branch")
        branch_label.setProperty("summaryLabel", True)
        self.branch_value = QLabel("—")
        self.branch_value.setObjectName("repoBranchValue")

        layout.addWidget(source_label, 2, 0)
        layout.addWidget(self.source_value, 2, 1, 1, 2)
        layout.addWidget(branch_label, 3, 0)
        layout.addWidget(self.branch_value, 3, 1, 1, 2)

        # Feedback message
        self.feedback_label = QLabel("Select a repository from the list or clone one from GitHub.")
        self.feedback_label.setObjectName("repoFeedbackLabel")
        self.feedback_label.setWordWrap(True)
        layout.addWidget(self.feedback_label, 4, 0, 1, 3)

    # ------------------------------------------------------------------
    def _copy_path_to_clipboard(self) -> None:
        """Copy the current repository path to the clipboard."""

        path = self.path_field.text().strip()
        if not path:
            return

        clipboard = QApplication.clipboard()
        if clipboard is None:
            logger.warning("Unable to copy repository path: clipboard unavailable.")
            return

        clipboard.setText(path)
        self.feedback_label.setText("Path copied to clipboard.")
        self.feedback_label.setProperty("highlight", True)
        self._reapply_styles(self.feedback_label)

    def update_summary(self, repo_path: Optional[str], metadata: Optional[Dict[str, str]]) -> None:
        """Update the card contents for the supplied repository information."""

        metadata = metadata or {}
        if not repo_path:
            self._path_exists = False
            self.path_field.clear()
            self.source_value.setText("—")
            self.branch_value.setText("—")
            self.status_badge.setText("Not selected")
            self.status_badge.setProperty("status", "pending")
            self.feedback_label.setText("Select a repository from the list or clone one from GitHub.")
            self.feedback_label.setProperty("highlight", False)
        else:
            self.path_field.setText(repo_path)
            source = metadata.get("type", "Local")
            branch = metadata.get("branch")

            exists = Path(repo_path).exists()
            self._path_exists = exists

            self.source_value.setText(source)
            if branch and branch.lower() != "default":
                self.branch_value.setText(branch)
            else:
                self.branch_value.setText("Default branch")

            if exists:
                self.status_badge.setText("Ready")
                self.status_badge.setProperty("status", "ready")
                self.feedback_label.setText("Repository connected. You can proceed with the analysis settings.")
                self.feedback_label.setProperty("highlight", False)
            else:
                self.status_badge.setText("Unavailable")
                self.status_badge.setProperty("status", "missing")
                self.feedback_label.setText("The selected path could not be found. Please verify the location or choose another repository.")
                self.feedback_label.setProperty("highlight", False)

        self._reapply_styles(self.status_badge, self.feedback_label)

    def _reapply_styles(self, *widgets: QWidget) -> None:
        """Force Qt to refresh dynamic properties on the provided widgets."""

        app = QApplication.instance()
        fallback_style: Optional[QStyle] = app.style() if isinstance(app, QApplication) else None

        for widget in widgets:
            style: Optional[QStyle] = widget.style()
            if style is None:
                style = fallback_style
            if style is None:
                continue
            style.unpolish(widget)
            style.polish(widget)
            widget.update()


class RepositorySelectionWidget(QWidget):
    """Widget for selecting and managing repository sources."""

    pathChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_metadata: Dict[str, str] = {}
        self.initUI()

    def initUI(self) -> None:
        """Initialize the user interface."""
        self.setObjectName("repositorySelectionRoot")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)

        intro_label = QLabel("Manage the repositories you want to analyze. Add a local directory or clone from GitHub and we will keep the active selection in sync with your analysis settings.")
        intro_label.setObjectName("repositoryIntro")
        intro_label.setWordWrap(True)
        main_layout.addWidget(intro_label)

        # Summary card showing the currently active repository context
        self.summary_card = RepositorySummaryCard()
        main_layout.addWidget(self.summary_card)

        # Create repository list widget
        self.repo_list_widget = RepositoryListWidget()
        self.repo_list_widget.repositorySelected.connect(self.on_repository_selected)
        self.repo_list_widget.repositoryAdded.connect(self.on_repository_added)
        self.repo_list_widget.repositoryRemoved.connect(self.on_repository_removed)

        # Create GitHub repository widget
        self.github_widget = GitHubWidget()
        self.github_widget.repository_cloned.connect(self.onGitHubRepoCloned)

        # Tab widget that separates local management from GitHub integration
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("repositoryTabs")
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.addTab(self.repo_list_widget, "Local & Linked Repositories")
        self.tab_widget.addTab(self.github_widget, "Clone from GitHub")

        main_layout.addWidget(self.tab_widget)

        # Expose the line edit used by other components
        self.repo_path = self.summary_card.path_field

        self._apply_styles()

    # ------------------------------------------------------------------
    def _apply_styles(self) -> None:
        """Apply component-level styling for a polished presentation."""

        self.setStyleSheet(
            """
            #repositorySelectionRoot {
                background: transparent;
            }
            #repositoryIntro {
                color: palette(mid);
                font-size: 13px;
            }
            QFrame#repositorySummaryCard {
                background: palette(base);
                border: 1px solid palette(midlight);
                border-radius: 12px;
            }
            QLabel#summaryTitle {
                font-size: 15px;
                font-weight: 600;
            }
            QLabel[summaryLabel="true"] {
                color: palette(dark);
                font-weight: 500;
            }
            QLabel#repoStatusBadge {
                padding: 2px 10px;
                border-radius: 10px;
                font-size: 11px;
                font-weight: 600;
                background: #e5e7eb;
                color: #374151;
            }
            QLabel#repoStatusBadge[status="ready"] {
                background: #d1fae5;
                color: #047857;
            }
            QLabel#repoStatusBadge[status="missing"] {
                background: #fee2e2;
                color: #b91c1c;
            }
            QLabel#repoStatusBadge[status="pending"] {
                background: #e5e7eb;
                color: #6b7280;
            }
            QLabel#repoFeedbackLabel {
                color: palette(mid);
                font-size: 12px;
            }
            QLabel#repoFeedbackLabel[highlight="true"] {
                color: #047857;
            }
            QLineEdit#repoPathDisplay {
                padding: 6px 10px;
                border-radius: 8px;
                border: 1px solid palette(midlight);
                background: palette(alternate-base);
                selection-background-color: palette(highlight);
            }
            QToolButton#copyRepoPathButton {
                border: none;
                padding: 4px;
            }
            QToolButton#copyRepoPathButton:hover {
                background: palette(alternate-base);
                border-radius: 6px;
            }
            QListWidget#repositoryList {
                border: 1px solid palette(midlight);
                border-radius: 10px;
                padding: 4px;
            }
            QPushButton#addLocalRepoButton,
            QPushButton#addGithubRepoButton,
            QPushButton#removeRepoButton {
                padding: 6px 12px;
                border-radius: 8px;
                border: 1px solid palette(midlight);
                background: palette(base);
            }
            QPushButton#addLocalRepoButton:hover,
            QPushButton#addGithubRepoButton:hover,
            QPushButton#removeRepoButton:hover {
                background: palette(alternate-base);
            }
            QTabWidget#repositoryTabs::pane {
                border: 1px solid palette(midlight);
                border-radius: 10px;
            }
            QTabWidget#repositoryTabs::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                padding: 8px 16px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: palette(base);
            }
            """
        )

    # ------------------------------------------------------------------
    def on_repository_selected(self, repo_path: str, metadata: Dict[str, str]) -> None:
        """Handle repository selection from the list."""

        self.tab_widget.setCurrentWidget(self.repo_list_widget)
        self._update_summary(repo_path, metadata)
        self.pathChanged.emit(repo_path)
        logger.info("Selected repository: %s", repo_path)

    def on_repository_added(self, repo_path: str, metadata: Dict[str, str]) -> None:
        """Handle addition of a new repository."""

        self._update_summary(repo_path, metadata)
        self.pathChanged.emit(repo_path)
        logger.info("Added repository: %s", repo_path)

    def on_repository_removed(self, repo_path: str) -> None:
        """Handle removal of a repository."""

        if self.repo_path.text() == repo_path:
            current_item = self.repo_list_widget.list_widget.currentItem()
            if current_item:
                new_path = current_item.data(Qt.ItemDataRole.UserRole)
                metadata = current_item.data(Qt.ItemDataRole.UserRole + 1) or {"type": "Local"}
                self._update_summary(new_path, metadata)
                self.pathChanged.emit(new_path)
            else:
                self._update_summary(None, None)
                self.pathChanged.emit("")
        logger.info("Removed repository: %s", repo_path)

    def onGitHubRepoCloned(self, repo_path: str, branch: str) -> None:
        """Handle when a GitHub repository is successfully cloned."""

        self.repo_list_widget.register_github_repository(repo_path, branch)
        logger.info("Cloned GitHub repository: %s", repo_path)

    # ------------------------------------------------------------------
    def _update_summary(self, repo_path: Optional[str], metadata: Optional[Dict[str, str]]) -> None:
        """Update the summary card and active repository cache."""

        self.summary_card.update_summary(repo_path, metadata)
        if repo_path:
            self._active_metadata = dict(metadata or {})
            self.repo_path.setText(repo_path)
        else:
            self._active_metadata = {}
            self.repo_path.clear()

    # ------------------------------------------------------------------
    def validate(self) -> tuple[bool, str]:
        """Validate all selected repository paths."""

        validations = []
        for repo_path in self.repo_list_widget.repositories:
            is_valid, error = self._validate_path(repo_path)
            if not is_valid:
                validations.append(error)

        if not validations:
            return True, ""
        return False, "\n".join(validations)

    def _validate_path(self, path: str) -> tuple[bool, str]:
        """Validate a single repository path."""

        if not path:
            return False, "Repository path is required."

        path_obj = Path(path)

        if not path_obj.exists():
            return False, f"Directory does not exist: {path}"

        if not path_obj.is_dir():
            return False, f"Selected path is not a directory: {path}"

        if not self._is_accessible(path_obj):
            return False, f"Directory is not accessible: {path}"

        return True, ""

    def _is_accessible(self, path: Path) -> bool:
        """Check if the directory is accessible."""

        try:
            next(path.iterdir(), None)
            return True
        except (PermissionError, OSError):
            return False

    def set_repository_path(self, path: str) -> None:
        """Set the repository path programmatically."""

        if not path:
            self._update_summary(None, None)
            return

        metadata = self.repo_list_widget.get_repository_metadata(path)
        if metadata:
            # Attempt to select the corresponding list item
            for index in range(self.repo_list_widget.list_widget.count()):
                item = self.repo_list_widget.list_widget.item(index)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == path:
                    self.repo_list_widget.list_widget.setCurrentItem(item)
                    break
        else:
            metadata = {"type": "Local" if Path(path).exists() else "Unknown"}

        self._update_summary(path, metadata)

    def get_repository_path(self) -> str:
        """Get the repository path."""

        return self.repo_path.text()

    def get_active_repository_metadata(self) -> Dict[str, str]:
        """Return metadata for the active repository selection."""

        return dict(self._active_metadata)

    def closeEvent(self, event):
        """Handle widget closure."""
        self.github_widget.cleanup()
        super().closeEvent(event)
