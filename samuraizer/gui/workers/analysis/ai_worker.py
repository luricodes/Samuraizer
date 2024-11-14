import logging
from typing import Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal
import openai
import requests
import json
from pathlib import Path
import hashlib
import time

logger = logging.getLogger(__name__)

class AIWorker(QObject):
    """Worker for handling AI/LLM processing in a separate thread."""
    
    # Signals
    started = pyqtSignal()
    progress = pyqtSignal(str)  # Emits progress updates
    finished = pyqtSignal(str)  # Emits analysis result
    error = pyqtSignal(str)     # Emits error message
    
    def __init__(self, prompt: str, config: Dict[str, Any]):
        super().__init__()
        self.prompt = prompt
        self.config = config
        self.cache_dir = Path.home() / '.samuraizer' / 'ai_cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._stop_requested = False
        
    def stop(self):
        """Request the worker to stop processing."""
        self._stop_requested = True
        
    def _get_cache_key(self, prompt: str) -> str:
        """Generate a cache key for the given prompt."""
        cache_data = {
            'prompt': prompt,
            'model': self.config.get('model'),
            'provider': self.config.get('provider'),
            'max_tokens': self.config.get('max_tokens')
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()
        
    def _get_cached_result(self, cache_key: str) -> Optional[str]:
        """Try to get cached result."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                cache_data = json.loads(cache_file.read_text())
                if time.time() - cache_data['timestamp'] < 86400:  # 24 hours
                    return cache_data['result']
            except Exception as e:
                logger.warning(f"Failed to read cache: {e}")
        return None
        
    def _save_to_cache(self, cache_key: str, result: str):
        """Save result to cache."""
        try:
            cache_file = self.cache_dir / f"{cache_key}.json"
            cache_data = {
                'timestamp': time.time(),
                'result': result
            }
            cache_file.write_text(json.dumps(cache_data))
        except Exception as e:
            logger.warning(f"Failed to write to cache: {e}")
        
    def run(self):
        """Main worker execution method."""
        try:
            self.started.emit()
            self.progress.emit("Preparing analysis...")
            
            # Check cache
            cache_key = self._get_cache_key(self.prompt)
            cached_result = self._get_cached_result(cache_key)
            
            if cached_result:
                self.progress.emit("Using cached analysis result")
                self.finished.emit(cached_result)
                return
                
            provider = self.config.get('provider', 'OpenAI')
            api_key = self.config.get('api_key', '')
            model = self.config.get('model', 'gpt-4-turbo-preview')
            endpoint = self.config.get('endpoint', '')
            max_tokens = self.config.get('max_tokens', 2000)
            
            # Implement retry logic
            max_retries = 3
            retry_delay = 1  # seconds
            
            for attempt in range(max_retries):
                if self._stop_requested:
                    self.error.emit("Analysis cancelled")
                    return
                    
                try:
                    # Call appropriate API based on provider
                    if provider == "OpenAI":
                        result = self._call_openai_api(model, api_key, max_tokens)
                    elif provider == "Anthropic":
                        result = self._call_anthropic_api(model, api_key, max_tokens)
                    else:
                        result = self._call_custom_api(model, api_key, endpoint, max_tokens)
                    
                    # Cache successful result
                    self._save_to_cache(cache_key, result)
                    
                    self.finished.emit(result)
                    return
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {e}")
                        self.progress.emit(f"Retrying analysis ({attempt + 2}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        raise
            
        except Exception as e:
            logger.error(f"Error in AI processing: {e}", exc_info=True)
            self.error.emit(str(e))
            
    def _call_openai_api(self, model: str, api_key: str, max_tokens: int) -> str:
        """Make call to OpenAI API."""
        self.progress.emit("Analyzing code with OpenAI...")
        openai.api_key = api_key
        
        # Split long prompts into chunks if needed
        chunks = self._split_prompt(self.prompt, 4000)  # 4000 tokens max per chunk
        
        full_response = []
        for i, chunk in enumerate(chunks):
            if self._stop_requested:
                break
                
            if len(chunks) > 1:
                self.progress.emit(f"Processing part {i+1} of {len(chunks)}")
                
            response = openai.ChatCompletion.create(
                model=model,
                messages=[{"role": "user", "content": chunk}],
                max_tokens=max_tokens
            )
            full_response.append(response.choices[0].message.content)
            
        return "\n".join(full_response)
        
    def _call_anthropic_api(self, model: str, api_key: str, max_tokens: int) -> str:
        """Make call to Anthropic API."""
        self.progress.emit("Analyzing code with Claude...")
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        
        data = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": self.prompt}]
        }
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=data
        )
        
        return response.json()["content"][0]["text"]
        
    def _call_custom_api(self, model: str, api_key: str, endpoint: str, max_tokens: int) -> str:
        """Make call to custom API endpoint."""
        self.progress.emit("Analyzing code...")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "prompt": self.prompt,
            "max_tokens": max_tokens
        }
        
        response = requests.post(endpoint, headers=headers, json=data)
        return response.json()["response"]
        
    def _split_prompt(self, prompt: str, max_tokens: int) -> list[str]:
        """Split a long prompt into smaller chunks."""
        chunks = []
        current_chunk = []
        current_length = 0
        
        for line in prompt.split('\n'):
            # Rough estimate: 4 chars = 1 token
            line_tokens = len(line) // 4
            if current_length + line_tokens > max_tokens:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_length = line_tokens
            else:
                current_chunk.append(line)
                current_length += line_tokens
                
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
            
        return chunks
