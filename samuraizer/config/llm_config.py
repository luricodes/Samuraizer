# samuraizer/config/llm_config.py

import logging
import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class LLMConfigManager:
    """Manager for LLM API configuration settings."""
    
    PROVIDERS = {
        'OpenAI': {
            'models': [
                'gpt-4-turbo-preview',
                'gpt-4',
                'gpt-3.5-turbo'
            ],
            'default_model': 'gpt-3.5-turbo',
            'api_base': 'https://api.openai.com/v1'
        },
        'Anthropic': {
            'models': [
                'claude-3-opus-20240229',
                'claude-3-sonnet-20240229',
                'claude-3-haiku-20240307'
            ],
            'default_model': 'claude-3-haiku-20240307',
            'api_base': 'https://api.anthropic.com/v1'
        },
        'Custom': {
            'models': [],
            'default_model': '',
            'api_base': ''
        }
    }

    DEFAULT_CONFIG = {
        'provider': 'OpenAI',
        'api_key': '',
        'model': PROVIDERS['OpenAI']['default_model'],
        'temperature': 0.7,
        'max_tokens': 2000,
        'api_base': PROVIDERS['OpenAI']['api_base'],
        'custom_model': ''  # For custom provider
    }
    
    def __init__(self) -> None:
        """Initialize the LLM configuration manager."""
        self.config_dir = self._get_config_dir()
        self.config_file = self.config_dir / "llm_config.yaml"
        logger.info(f"LLM config file path: {self.config_file}")
        self.config = self._load_or_create_config()
        
    def _get_config_dir(self) -> Path:
        """Get the configuration directory path."""
        if os.name == 'nt':  # Windows
            base_dir = Path(os.environ.get('APPDATA', '')) / "Samuraizer"
        else:  # Unix-like
            base_dir = Path.home() / ".config" / "Samuraizer"
        logger.info(f"Config directory: {base_dir}")
        return base_dir
        
    def _ensure_config_dir(self) -> None:
        """Ensure the configuration directory exists."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created/verified config directory: {self.config_dir}")
        except Exception as e:
            logger.error(f"Failed to create config directory: {e}")
            raise
        
    def _load_or_create_config(self) -> Dict[str, Any]:
        """Load existing config or create default one if it doesn't exist."""
        self._ensure_config_dir()
        
        if not self.config_file.exists():
            logger.info("Config file does not exist, creating default config")
            return self._create_default_config()
            
        try:
            logger.info("Loading existing config file")
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Merge with defaults to ensure all fields exist
            merged_config = self.DEFAULT_CONFIG.copy()
            if config:
                merged_config.update(config)
                logger.info("Successfully loaded and merged config")
            else:
                logger.warning("Loaded config was empty, using defaults")
            return merged_config
            
        except Exception as e:
            logger.error(f"Error loading LLM config file: {e}")
            logger.info("Falling back to default config")
            return self.DEFAULT_CONFIG.copy()
                
    def _create_default_config(self) -> Dict[str, Any]:
        """Create and save the default configuration file."""
        try:
            self._save_config_to_file(self.DEFAULT_CONFIG)
            logger.info(f"Created default LLM config file at: {self.config_file}")
            return self.DEFAULT_CONFIG.copy()
        except Exception as e:
            logger.error(f"Failed to create default LLM config: {e}")
            return self.DEFAULT_CONFIG.copy()
            
    def _save_config_to_file(self, config_data: Dict[str, Any]) -> None:
        """Save configuration data to file with proper error handling."""
        temp_file = self.config_file.with_suffix('.yaml.tmp')
        try:
            # Write to temporary file first
            logger.info(f"Writing config to temp file: {temp_file}")
            with open(temp_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(config_data, f, default_flow_style=False, allow_unicode=True)
            
            # Rename temporary file to actual config file
            logger.info("Replacing config file with temp file")
            temp_file.replace(self.config_file)
            logger.info("Config file saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save LLM configuration: {e}")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                    logger.info("Cleaned up temp file after error")
                except:
                    pass
            raise
    
    def get_config(self) -> Dict[str, Any]:
        """Get current LLM configuration."""
        logger.debug(f"Current config: {self.config}")
        return self.config.copy()
    
    def save_config(self, config: Dict[str, Any]) -> None:
        """Save LLM configuration."""
        try:
            logger.info("Saving new config")
            logger.debug(f"New config data: {config}")
            # Update current config
            self.config = config
            # Save to file
            self._save_config_to_file(self.config)
            logger.info("LLM configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving LLM configuration: {e}")
            raise
    
    def get_providers(self) -> List[str]:
        """Get list of available providers."""
        return list(self.PROVIDERS.keys())
    
    def get_models(self, provider: str) -> List[str]:
        """Get list of models for a provider."""
        if provider in self.PROVIDERS:
            return self.PROVIDERS[provider]['models']
        return []
    
    def get_default_api_base(self, provider: str) -> str:
        """Get default API base URL for a provider."""
        if provider in self.PROVIDERS:
            return self.PROVIDERS[provider]['api_base']
        return ''
    
    def get_provider(self) -> str:
        """Get the current provider."""
        return self.config['provider']
    
    def set_provider(self, provider: str) -> None:
        """Set the provider."""
        self.config['provider'] = provider
        # Update API base if not custom
        if provider != 'Custom':
            self.config['api_base'] = self.get_default_api_base(provider)
            self.config['model'] = self.PROVIDERS[provider]['default_model']
        self.save_config(self.config)
    
    def get_api_key(self) -> str:
        """Get the API key."""
        return self.config['api_key']
    
    def set_api_key(self, api_key: str) -> None:
        """Set the API key."""
        self.config['api_key'] = api_key
        self.save_config(self.config)
    
    def get_model(self) -> str:
        """Get the model name."""
        if self.config['provider'] == 'Custom':
            return self.config.get('custom_model', '')
        return self.config['model']
    
    def set_model(self, model: str) -> None:
        """Set the model name."""
        if self.config['provider'] == 'Custom':
            self.config['custom_model'] = model
        else:
            self.config['model'] = model
        self.save_config(self.config)
    
    def get_temperature(self) -> float:
        """Get the temperature value."""
        return self.config['temperature']
    
    def set_temperature(self, temperature: float) -> None:
        """Set the temperature value."""
        self.config['temperature'] = temperature
        self.save_config(self.config)
    
    def get_max_tokens(self) -> int:
        """Get the max tokens value."""
        return self.config['max_tokens']
    
    def set_max_tokens(self, max_tokens: int) -> None:
        """Set the max tokens value."""
        self.config['max_tokens'] = max_tokens
        self.save_config(self.config)
    
    def get_api_base(self) -> str:
        """Get the API base URL."""
        return self.config['api_base']
    
    def set_api_base(self, api_base: str) -> None:
        """Set the API base URL."""
        self.config['api_base'] = api_base
        self.save_config(self.config)
