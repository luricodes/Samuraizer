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
        self.llm_config = LLMConfigManager()
        self.setup_ui()

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
        self.load_settings()

    def _on_provider_changed(self, provider: str) -> None:
        """Handle provider selection changes."""
        # Update model choices
        self.model_combo.clear()
        models = self.llm_config.get_models(provider)
        
        if provider == 'Custom':
            self.model_combo.setEditable(True)
            self.model_combo.setPlaceholderText("Enter model name...")
            self.api_base_input.setEnabled(True)
            self.api_base_input.clear()
        else:
            self.model_combo.setEditable(False)
            self.model_combo.addItems(models)
            self.api_base_input.setText(self.llm_config.get_default_api_base(provider))
            self.api_base_input.setEnabled(False)

    def load_settings(self) -> None:
        """Load current LLM settings."""
        try:
            config = self.llm_config.get_config()
            
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
            
        except Exception as e:
            logger.error(f"Error loading LLM settings: {e}")

    def save_settings(self) -> None:
        """Save current LLM settings."""
        try:
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
            else:
                config['model'] = self.model_combo.currentText()
                config['custom_model'] = ''
            
            self.llm_config.save_config(config)
            
        except Exception as e:
            logger.error(f"Error saving LLM settings: {e}")

    def validate(self) -> bool:
        """Validate LLM settings."""
        try:
            # API key is required
            if not self.api_key_input.text().strip():
                logger.error("API key is required")
                return False
            
            provider = self.provider_combo.currentText()
            
            # For custom provider, require model name and valid API base URL
            if provider == 'Custom':
                if not self.model_combo.currentText().strip():
                    logger.error("Model name is required for custom provider")
                    return False
                    
                api_base = self.api_base_input.text().strip()
                if not api_base.startswith(('http://', 'https://')):
                    logger.error("Invalid API base URL")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating LLM settings: {e}")
            return False
