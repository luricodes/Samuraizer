# samuraizer/config/llm_config.py

import logging
from typing import Dict, Any, Optional, List
from .config_manager import ConfigurationManager

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
    
    def __init__(self) -> None:
        self.config_manager = ConfigurationManager()
        self._config_key = "llm_settings"
        
    def get_config(self) -> Dict[str, Any]:
        """Get current LLM configuration."""
        default_config = {
            'provider': 'OpenAI',
            'api_key': '',
            'model': self.PROVIDERS['OpenAI']['default_model'],
            'temperature': 0.7,
            'max_tokens': 2000,
            'api_base': self.PROVIDERS['OpenAI']['api_base'],
            'custom_model': ''  # For custom provider
        }
        
        try:
            if not hasattr(self.config_manager, 'exclusion_config'):
                return default_config
                
            # Use the existing config structure
            if 'llm_settings' not in self.config_manager.exclusion_config.config:
                self.config_manager.exclusion_config.config['llm_settings'] = default_config
                self.config_manager.exclusion_config._save_config()
                
            return self.config_manager.exclusion_config.config['llm_settings']
            
        except Exception as e:
            logger.error(f"Error getting LLM configuration: {e}")
            return default_config
    
    def save_config(self, config: Dict[str, Any]) -> None:
        """Save LLM configuration."""
        try:
            if not hasattr(self.config_manager, 'exclusion_config'):
                raise Exception("Configuration manager not properly initialized")
                
            self.config_manager.exclusion_config.config['llm_settings'] = config
            self.config_manager.exclusion_config._save_config()
            logger.debug("LLM configuration saved successfully")
            
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
        return self.get_config()['provider']
    
    def set_provider(self, provider: str) -> None:
        """Set the provider."""
        config = self.get_config()
        config['provider'] = provider
        # Update API base if not custom
        if provider != 'Custom':
            config['api_base'] = self.get_default_api_base(provider)
            config['model'] = self.PROVIDERS[provider]['default_model']
        self.save_config(config)
    
    def get_api_key(self) -> str:
        """Get the API key."""
        return self.get_config()['api_key']
    
    def set_api_key(self, api_key: str) -> None:
        """Set the API key."""
        config = self.get_config()
        config['api_key'] = api_key
        self.save_config(config)
    
    def get_model(self) -> str:
        """Get the model name."""
        config = self.get_config()
        if config['provider'] == 'Custom':
            return config.get('custom_model', '')
        return config['model']
    
    def set_model(self, model: str) -> None:
        """Set the model name."""
        config = self.get_config()
        if config['provider'] == 'Custom':
            config['custom_model'] = model
        else:
            config['model'] = model
        self.save_config(config)
    
    def get_temperature(self) -> float:
        """Get the temperature value."""
        return self.get_config()['temperature']
    
    def set_temperature(self, temperature: float) -> None:
        """Set the temperature value."""
        config = self.get_config()
        config['temperature'] = temperature
        self.save_config(config)
    
    def get_max_tokens(self) -> int:
        """Get the max tokens value."""
        return self.get_config()['max_tokens']
    
    def set_max_tokens(self, max_tokens: int) -> None:
        """Set the max tokens value."""
        config = self.get_config()
        config['max_tokens'] = max_tokens
        self.save_config(config)
    
    def get_api_base(self) -> str:
        """Get the API base URL."""
        return self.get_config()['api_base']
    
    def set_api_base(self, api_base: str) -> None:
        """Set the API base URL."""
        config = self.get_config()
        config['api_base'] = api_base
        self.save_config(config)
