# output_options/jsonl_options_group.py

import logging
from PyQt6.QtWidgets import (
    QGroupBox, QFormLayout, QCheckBox, QLabel, QHBoxLayout, QSpinBox
)
from PyQt6.QtCore import pyqtSignal, Qt

logger = logging.getLogger(__name__)

class JsonlOptionsGroup(QGroupBox):
    optionChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("JSONL Options", parent)
        self.initUI()
        self._cached_options = None

    def initUI(self):
        layout = QFormLayout()

        self.llm_finetuning = QCheckBox("Format for LLM fine-tuning")
        self.llm_finetuning.setChecked(True)
        self.llm_finetuning.stateChanged.connect(self._on_llm_option_changed)
        layout.addRow("", self.llm_finetuning)

        # LLM Options Subgroup
        self.llm_options_group = QGroupBox("Fine-tuning Options")
        llm_options_layout = QFormLayout()

        self.include_metadata = QCheckBox("Include metadata (id, timestamp, source)")
        self.include_metadata.setChecked(True)
        self.include_metadata.stateChanged.connect(self.on_option_changed)
        llm_options_layout.addRow("", self.include_metadata)

        self.code_structure = QCheckBox("Extract code structure (imports, functions, classes)")
        self.code_structure.setChecked(True)
        self.code_structure.stateChanged.connect(self.on_option_changed)
        llm_options_layout.addRow("", self.code_structure)

        self.skip_preprocessing = QCheckBox("Skip code preprocessing")
        self.skip_preprocessing.setChecked(False)
        self.skip_preprocessing.stateChanged.connect(self.on_option_changed)
        llm_options_layout.addRow("", self.skip_preprocessing)

        context_layout = QHBoxLayout()
        self.context_depth = QSpinBox()
        self.context_depth.setRange(1, 3)
        self.context_depth.setValue(2)
        self.context_depth.valueChanged.connect(self.on_option_changed)
        context_layout.addWidget(QLabel("Context Depth:"))
        context_layout.addWidget(self.context_depth)
        context_layout.addStretch()
        llm_options_layout.addRow(context_layout)

        context_desc = QLabel(
            "1=Basic, 2=Standard (recommended), 3=Detailed context extraction"
        )
        context_desc.setStyleSheet("color: gray;")
        llm_options_layout.addRow("", context_desc)

        self.llm_options_group.setLayout(llm_options_layout)
        layout.addRow(self.llm_options_group)

        jsonl_desc = QLabel(
            "LLM fine-tuning format includes code content with optional structure analysis "
            "and contextual information for improved training quality."
        )
        jsonl_desc.setWordWrap(True)
        jsonl_desc.setStyleSheet("color: gray;")
        layout.addRow("", jsonl_desc)

        self.setLayout(layout)
        self.setVisible(False)  # Controlled by format selection
        
        # Initialize subsettings state
        self._update_subsettings_state(self.llm_finetuning.isChecked())

    def _update_subsettings_state(self, enabled: bool):
        """Update the enabled state of all subsettings"""
        self.llm_options_group.setEnabled(enabled)
        
        widgets = [
            self.include_metadata,
            self.code_structure,
            self.skip_preprocessing,
            self.context_depth
        ]
        
        for widget in widgets:
            widget.setEnabled(enabled)

    def _on_llm_option_changed(self, state):
        """Handle changes to the main LLM option"""
        is_enabled = state == Qt.CheckState.Checked.value
        logger.debug(f"LLM Fine-Tuning Enabled: {is_enabled}")
        
        # Update subsettings state
        self._update_subsettings_state(is_enabled)
        
        # Emit change signal
        self.optionChanged.emit()

    def on_option_changed(self, value):
        self.optionChanged.emit()

    def load_settings(self, settings_manager):
        # Load sub-settings first
        self.include_metadata.setChecked(settings_manager.load_setting("output/include_metadata", True, type_=bool))
        self.code_structure.setChecked(settings_manager.load_setting("output/code_structure", True, type_=bool))
        self.skip_preprocessing.setChecked(settings_manager.load_setting("output/skip_preprocessing", False, type_=bool))
        self.context_depth.setValue(settings_manager.load_setting("output/context_depth", 2, type_=int))
        
        # Load and apply main setting last
        llm_enabled = settings_manager.load_setting("output/llm_finetuning", True, type_=bool)
        self.llm_finetuning.setChecked(llm_enabled)
        self._update_subsettings_state(llm_enabled)

    def save_settings(self, settings_manager):
        settings_manager.save_setting("output/llm_finetuning", self.llm_finetuning.isChecked())
        settings_manager.save_setting("output/include_metadata", self.include_metadata.isChecked())
        settings_manager.save_setting("output/code_structure", self.code_structure.isChecked())
        settings_manager.save_setting("output/skip_preprocessing", self.skip_preprocessing.isChecked())
        settings_manager.save_setting("output/context_depth", self.context_depth.value())

    def get_options(self) -> dict:
        return {
            'llm_finetuning': self.llm_finetuning.isChecked(),
            'include_metadata': self.include_metadata.isChecked(),
            'code_structure': self.code_structure.isChecked(),
            'skip_preprocessing': self.skip_preprocessing.isChecked(),
            'context_depth': self.context_depth.value()
        }

    def set_options(self, options: dict):
        # Set sub-options first
        self.include_metadata.setChecked(options.get('include_metadata', True))
        self.code_structure.setChecked(options.get('code_structure', True))
        self.skip_preprocessing.setChecked(options.get('skip_preprocessing', False))
        self.context_depth.setValue(options.get('context_depth', 2))
        
        # Set main option and update states
        llm_enabled = options.get('llm_finetuning', True)
        self.llm_finetuning.setChecked(llm_enabled)
        self._update_subsettings_state(llm_enabled)

    def set_visible(self, visible: bool):
        if not visible:
            # Cache current options before hiding
            self._cached_options = self.get_options()
            self.setVisible(False)
        else:
            self.setVisible(True)
            # Restore cached options if available
            if self._cached_options is not None:
                self.set_options(self._cached_options)
                self._cached_options = None
            else:
                # Default state if no cached options
                self.set_options({
                    'llm_finetuning': True,
                    'include_metadata': True,
                    'code_structure': True,
                    'skip_preprocessing': False,
                    'context_depth': 2
                })
