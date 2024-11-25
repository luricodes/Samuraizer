# samuraizer/gui/dialogs/components/settings/groups/llm_settings.py

import logging
from typing import Optional
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox,
    QDoubleSpinBox, QSpinBox, QWidget
)
from PyQt6.QtCore import Qt

from samuraizer.config.llm_config import LLMConfigManager

logger = logging.getLogger(__name__)

class LLMSettingsGroup(QGroupBox):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("LLM API Settings", parent)
        # Get LLMConfigManager instance from MainWindow
        main_window = self._get_main_window()
        self.llm_config = main_window.llm_config_manager if main_window else LLMConfigManager()
        self.setup_ui()

    def _get_main_window(self):
        """Get the main window instance by traversing up the widget hierarchy."""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'llm_config_manager'):
                return parent
            parent = parent.parent()
        return None

    def setup_ui(self) -> None:
        """Set up the LLM settings UI."""
        layout = QVBoxLayout()

        # Provider Selection
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(self.llm_config.get_providers())
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(self.provider_combo)
        layout.addLayout(provider_layout)

        # API Key
        api_key_layout = QHBoxLayout()
        api_key_layout.addWidget(QLabel("API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Enter your API key")
        api_key_layout.addWidget(self.api_key_input)
        layout.addLayout(api_key_layout)

        # Model Selection
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(False)
        model_layout.addWidget(self.model_combo)
        layout.addLayout(model_layout)

        # Temperature
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("Temperature:"))
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setDecimals(1)
        temp_layout.addWidget(self.temperature_spin)
        layout.addLayout(temp_layout)

        # Max Tokens
        tokens_layout = QHBoxLayout()
        tokens_layout.addWidget(QLabel("Max Tokens:"))
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(1, 32000)
        self.max_tokens_spin.setSingleStep(100)
        tokens_layout.addWidget(self.max_tokens_spin)
        layout.addLayout(tokens_layout)

        # API Base URL
        api_base_layout = QHBoxLayout()
        api_base_layout.addWidget(QLabel("API Base URL:"))
        self.api_base_input = QLineEdit()
        api_base_layout.addWidget(self.api_base_input)
        layout.addLayout(api_base_layout)

        # Description
        self.description_label = QLabel(
            "Configure the Language Model settings for AI-powered analysis. "
            "An API key is required for accessing the language model services."
        )
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        self.setLayout(layout)

        # Initialize UI with current config
        config = self.llm_config.get_config()
        self._update_ui_from_config(config)

    def _update_ui_from_config(self, config: dict) -> None:
        """Update UI elements with values from config."""
        # Set provider
        provider = config['provider']
        self.provider_combo.setCurrentText(provider)
        
        # Set API key
        self.api_key_input.setText(config['api_key'])
        
        # Set model
        if provider == 'Custom':
            self.model_combo.setCurrentText(config.get('custom_model', ''))
        else:
            self.model_combo.setCurrentText(config['model'])
        
        # Set other values
        self.temperature_spin.setValue(config['temperature'])
        self.max_tokens_spin.setValue(config['max_tokens'])
        self.api_base_input.setText(config['api_base'])

    def _on_provider_changed(self, provider: str) -> None:
        """Handle provider selection changes."""
        logger.debug(f"Provider changed to: {provider}")
        # Update model choices
        self.model_combo.clear()
        models = self.llm_config.get_models(provider)
        
        if provider == 'Custom':
            self.model_combo.setEditable(True)
            self.model_combo.setPlaceholderText("Enter model name...")
            self.api_base_input.setEnabled(True)
            self.api_base_input.clear()
            logger.debug("Enabled custom provider fields")
        else:
            self.model_combo.setEditable(False)
            self.model_combo.addItems(models)
            self.api_base_input.setText(self.llm_config.get_default_api_base(provider))
            self.api_base_input.setEnabled(False)
            logger.debug(f"Set models for {provider}: {models}")

    def load_settings(self) -> None:
        """Load current LLM settings."""
        try:
            logger.debug("Loading LLM settings")
            config = self.llm_config.get_config()
            self._update_ui_from_config(config)
            logger.debug("LLM settings loaded successfully")
        except Exception as e:
            logger.error(f"Error loading LLM settings: {e}", exc_info=True)
            if hasattr(self.parent(), 'show_error'):
                self.parent().show_error("Settings Error", f"Failed to load LLM settings: {str(e)}")

    def save_settings(self) -> None:
        """Save current LLM settings."""
        try:
            logger.debug("Saving LLM settings")
            provider = self.provider_combo.currentText()
            config = {
                'provider': provider,
                'api_key': self.api_key_input.text(),
                'temperature': self.temperature_spin.value(),
                'max_tokens': self.max_tokens_spin.value(),
                'api_base': self.api_base_input.text()
            }
            
            # Handle model based on provider
            if provider == 'Custom':
                config['custom_model'] = self.model_combo.currentText()
                config['model'] = ''
                logger.debug(f"Saving custom model: {config['custom_model']}")
            else:
                config['model'] = self.model_combo.currentText()
                config['custom_model'] = ''
                logger.debug(f"Saving model: {config['model']}")
            
            logger.debug(f"Saving config: {config}")
            self.llm_config.save_config(config)
            logger.debug("LLM settings saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving LLM settings: {e}", exc_info=True)
            if hasattr(self.parent(), 'show_error'):
                self.parent().show_error("Settings Error", f"Failed to save LLM settings: {str(e)}")

    def validate(self) -> bool:
        """Validate LLM settings."""
        try:
            logger.debug("Validating LLM settings")
            # API key is required
            if not self.api_key_input.text().strip():
                logger.warning("API key is missing")
                if hasattr(self.parent(), 'show_error'):
                    self.parent().show_error(
                        "Validation Error",
                        "API key is required for LLM services.\nPlease enter your API key."
                    )
                return False
            
            provider = self.provider_combo.currentText()
            logger.debug(f"Validating provider: {provider}")
            
            # For custom provider, require model name and valid API base URL
            if provider == 'Custom':
                if not self.model_combo.currentText().strip():
                    logger.warning("Custom model name is missing")
                    if hasattr(self.parent(), 'show_error'):
                        self.parent().show_error(
                            "Validation Error",
                            "Model name is required for custom provider."
                        )
                    return False
                    
                api_base = self.api_base_input.text().strip()
                if not api_base.startswith(('http://', 'https://')):
                    logger.warning("Invalid API base URL")
                    if hasattr(self.parent(), 'show_error'):
                        self.parent().show_error(
                            "Validation Error",
                            "Invalid API base URL. Must start with http:// or https://"
                        )
                    return False
            else:
                if not self.model_combo.currentText():
                    logger.warning("Model selection is missing")
                    if hasattr(self.parent(), 'show_error'):
                        self.parent().show_error(
                            "Validation Error",
                            "Please select a model."
                        )
                    return False
            
            logger.debug("LLM settings validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Error validating LLM settings: {e}", exc_info=True)
            if hasattr(self.parent(), 'show_error'):
                self.parent().show_error("Validation Error", str(e))
            return False
