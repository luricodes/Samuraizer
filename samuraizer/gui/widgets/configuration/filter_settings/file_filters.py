# samuraizer/gui/widgets/configuration/filter_settings/file_filters.py

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QListWidget, QPushButton, QInputDialog, QMessageBox,
    QLabel, QLineEdit, QScrollArea, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction

from samuraizer.config.config_manager import ConfigurationManager
from samuraizer.config.events import ConfigEvent, ConfigEventType
from .filter_config_listener import FilterConfigListener
from samuraizer.config.types import ConfigurationData

logger = logging.getLogger(__name__)

class EditableListWidget(QWidget):
    """A custom widget that displays an editable list with add/remove functionality"""
    
    itemsChanged = pyqtSignal()  # Signal emitted when items change
    
    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.title = title
        self.setup_ui()

    def setup_ui(self) -> None:
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        
        # Create list widget
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        
        # Create buttons
        btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self.add_item)
        
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self.remove_selected_items)
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        
        # Add widgets to layout
        layout.addWidget(self.list_widget)
        layout.addLayout(btn_layout)

    def show_context_menu(self, position) -> None:
        """Show context menu for list items"""
        menu = QMenu()
        
        add_action = QAction("Add Item", self)
        add_action.triggered.connect(self.add_item)
        menu.addAction(add_action)
        
        if self.list_widget.selectedItems():
            remove_action = QAction("Remove Selected", self)
            remove_action.triggered.connect(self.remove_selected_items)
            menu.addAction(remove_action)
        
        menu.exec(self.list_widget.mapToGlobal(position))

    def add_item(self) -> None:
        """Add a new item to the list"""
        text, ok = QInputDialog.getText(
            self,
            f"Add {self.title}",
            f"Enter {self.title.lower()} name:"
        )
        
        if ok and text:
            self.list_widget.addItem(text)
            self.itemsChanged.emit()

    def remove_selected_items(self) -> None:
        """Remove selected items from the list"""
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))
        self.itemsChanged.emit()

    def get_items(self) -> set[str]:
        """Get all items as a set"""
        return {
            self.list_widget.item(i).text()
            for i in range(self.list_widget.count())
        }

    def set_items(self, items: set[str]) -> None:
        """Set the list items"""
        self.list_widget.clear()
        for item in sorted(items):
            self.list_widget.addItem(item)

    def add_single_item(self, item: str) -> None:
        """Add a single item to the list without dialog"""
        self.list_widget.addItem(item)
        self.itemsChanged.emit()

    def remove_item(self, item: str) -> None:
        """Remove a specific item from the list"""
        items = self.list_widget.findItems(item, Qt.MatchFlag.MatchExactly)
        for item_widget in items:
            self.list_widget.takeItem(self.list_widget.row(item_widget))
        self.itemsChanged.emit()

class PatternListWidget(QWidget):
    """Widget for managing exclusion patterns"""
    
    patternsChanged = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self) -> None:
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        
        # Pattern input
        input_layout = QHBoxLayout()
        self.pattern_input = QLineEdit()
        self.pattern_input.setPlaceholderText("Enter glob or regex pattern (e.g., *.txt or regex:^test.*)")
        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self.add_pattern)
        
        input_layout.addWidget(self.pattern_input)
        input_layout.addWidget(self.add_btn)
        
        # Pattern list
        self.pattern_list = QListWidget()
        self.pattern_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.pattern_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pattern_list.customContextMenuRequested.connect(self.show_context_menu)
        
        # Remove button
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_selected_patterns)
        
        # Help text
        help_text = QLabel(
            "Patterns can be glob patterns (*.txt) or regex patterns (regex:^test.*)\n"
            "Glob patterns are simpler and match against filenames only\n"
            "Regex patterns are more powerful and can match against full paths"
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: gray;")
        
        # Add widgets to layout
        layout.addLayout(input_layout)
        layout.addWidget(self.pattern_list)
        layout.addWidget(self.remove_btn)
        layout.addWidget(help_text)

    def show_context_menu(self, position) -> None:
        """Show context menu for pattern list"""
        menu = QMenu()
        
        add_action = QAction("Add Pattern", self)
        add_action.triggered.connect(lambda: self.pattern_input.setFocus())
        menu.addAction(add_action)
        
        if self.pattern_list.selectedItems():
            remove_action = QAction("Remove Selected", self)
            remove_action.triggered.connect(self.remove_selected_patterns)
            menu.addAction(remove_action)
        
        menu.exec(self.pattern_list.mapToGlobal(position))

    def add_pattern(self) -> None:
        """Add a new pattern to the list"""
        pattern = self.pattern_input.text().strip()
        if pattern:
            self.pattern_list.addItem(pattern)
            self.pattern_input.clear()
            self.patternsChanged.emit()

    def remove_selected_patterns(self) -> None:
        """Remove selected patterns from the list"""
        for item in self.pattern_list.selectedItems():
            self.pattern_list.takeItem(self.pattern_list.row(item))
        self.patternsChanged.emit()

    def get_patterns(self) -> list[str]:
        """Get all patterns as a list"""
        return [
            self.pattern_list.item(i).text()
            for i in range(self.pattern_list.count())
        ]

    def set_patterns(self, patterns: list[str]) -> None:
        """Set the pattern list"""
        self.pattern_list.clear()
        for pattern in patterns:
            self.pattern_list.addItem(pattern)

    def add_single_pattern(self, pattern: str) -> None:
        """Add a single pattern without clearing input"""
        self.pattern_list.addItem(pattern)
        self.patternsChanged.emit()

    def remove_pattern(self, pattern: str) -> None:
        """Remove a specific pattern"""
        items = self.pattern_list.findItems(pattern, Qt.MatchFlag.MatchExactly)
        for item in items:
            self.pattern_list.takeItem(self.pattern_list.row(item))
        self.patternsChanged.emit()

class FileFiltersWidget(QWidget):
    """Main widget for managing file and folder filters"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config_manager = ConfigurationManager()
        self.config_listener = FilterConfigListener(self)
        self.setup_ui()
        self.load_settings()

    def setup_ui(self) -> None:
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        
        # Create a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Create main content widget
        content = QWidget()
        content_layout = QVBoxLayout(content)
        
        # Excluded Folders
        folders_group = QGroupBox("Excluded Folders")
        folders_layout = QVBoxLayout()
        self.folders_list = EditableListWidget("Folder")
        self.folders_list.itemsChanged.connect(self.save_settings)
        folders_layout.addWidget(self.folders_list)
        folders_group.setLayout(folders_layout)
        content_layout.addWidget(folders_group)
        
        # Excluded Files
        files_group = QGroupBox("Excluded Files")
        files_layout = QVBoxLayout()
        self.files_list = EditableListWidget("File")
        self.files_list.itemsChanged.connect(self.save_settings)
        files_layout.addWidget(self.files_list)
        files_group.setLayout(files_layout)
        content_layout.addWidget(files_group)
        
        # Image Extensions
        image_group = QGroupBox("Image Extensions")
        image_layout = QVBoxLayout()
        self.image_list = EditableListWidget("Image Extension")
        self.image_list.itemsChanged.connect(self.save_settings)
        help_text = QLabel("File extensions to identify image files (e.g., .jpg, .png)")
        help_text.setStyleSheet("color: gray;")
        help_text.setWordWrap(True)
        image_layout.addWidget(self.image_list)
        image_layout.addWidget(help_text)
        image_group.setLayout(image_layout)
        content_layout.addWidget(image_group)
        
        # Exclusion Patterns
        patterns_group = QGroupBox("Exclusion Patterns")
        patterns_layout = QVBoxLayout()
        self.patterns_list = PatternListWidget()
        self.patterns_list.patternsChanged.connect(self.save_settings)
        patterns_layout.addWidget(self.patterns_list)
        patterns_group.setLayout(patterns_layout)
        content_layout.addWidget(patterns_group)
        
        # Configuration file location
        config_path = self.config_manager.exclusion_config.config_file
        config_label = QLabel(f"Configuration File: {config_path}")
        config_label.setStyleSheet("color: gray;")
        config_label.setWordWrap(True)
        content_layout.addWidget(config_label)
        
        # Reset to Defaults button
        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self.reset_to_defaults)
        content_layout.addWidget(self.reset_btn)
        
        # Set up scroll area
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def load_settings(self) -> None:
        """Load settings from configuration manager"""
        try:
            # Get current config
            excluded_folders = self.config_manager.exclusion_config.get_excluded_folders()
            excluded_files = self.config_manager.exclusion_config.get_excluded_files()
            exclude_patterns = self.config_manager.exclusion_config.get_exclude_patterns()
            image_extensions = self.config_manager.exclusion_config.get_image_extensions()
            
            # Update UI
            self.folders_list.set_items(excluded_folders)
            self.files_list.set_items(excluded_files)
            self.patterns_list.set_patterns(exclude_patterns)
            self.image_list.set_items(set(image_extensions))
            
            logger.info("Filter settings loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading filter settings: {e}")
            self.show_error("Settings Error", f"Failed to load settings: {str(e)}")

    def save_settings(self) -> None:
        """Save current settings through configuration manager"""
        try:
            current_config = self.get_configuration()
            
            # Update configuration through manager
            self.config_manager.save_gui_filters(self)
            logger.debug("Filter settings saved to config file")
            
        except Exception as e:
            logger.error(f"Error saving filter settings: {e}")
            self.show_error("Save Error", f"Failed to save settings: {str(e)}")

    def reset_to_defaults(self) -> None:
        """Reset all filters to default values"""
        try:
            # Show confirmation dialog
            result = QMessageBox.question(
                self,
                "Reset to Defaults",
                "Are you sure you want to reset all filters to their default values?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if result == QMessageBox.StandardButton.Yes:
                # Reset configuration to defaults
                self.config_manager.reset_to_defaults()
                # Reload the UI with default values
                self.load_settings()
                logger.info("Filters reset to defaults")
                QMessageBox.information(self, "Reset Complete", "Filters have been reset to default values.")
                
        except Exception as e:
            logger.error(f"Error resetting to defaults: {e}")
            self.show_error("Reset Error", f"Failed to reset to defaults: {str(e)}")

    def get_configuration(self) -> Dict[str, Any]:
        """Get the current filter configuration"""
        return {
            'excluded_folders': list(self.folders_list.get_items()),
            'excluded_files': list(self.files_list.get_items()),
            'exclude_patterns': self.patterns_list.get_patterns(),
            'image_extensions': list(self.image_list.get_items())
        }

    def show_error(self, title: str, message: str) -> None:
        """Show an error message dialog"""
        QMessageBox.critical(self, title, message)
