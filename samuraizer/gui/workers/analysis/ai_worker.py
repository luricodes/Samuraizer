import logging
from typing import Dict, Any, Optional, List
from PyQt6.QtCore import QObject, pyqtSignal
import openai
import anthropic
from anthropic._exceptions import APIError, APIStatusError, APITimeoutError, RateLimitError
from anthropic.types import MessageParam, ContentBlock
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
    
    # Constants for Anthropic API limits
    ANTHROPIC_MAX_BYTES = 9000000  # Maximum bytes allowed by Anthropic
    ANTHROPIC_CHUNK_SIZE = 8000000  # Slightly smaller chunk size for safety margin
    
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
            api_base = self.config.get('api_base', '')
            max_tokens = self.config.get('max_tokens', 2000)
            temperature = self.config.get('temperature', 0.7)
            
            # Get model based on provider
            if provider == 'Custom':
                model = self.config.get('custom_model', '')
            else:
                model = self.config.get('model', '')
            
            if not api_key:
                raise ValueError("API key is required")
                
            if not model:
                raise ValueError("Model selection is required")
            
            # Implement retry logic with exponential backoff
            max_retries = 3
            base_delay = 1  # Initial delay in seconds
            max_delay = 16  # Maximum delay in seconds
            
            for attempt in range(max_retries):
                if self._stop_requested:
                    self.error.emit("Analysis cancelled")
                    return
                    
                try:
                    # Call appropriate API based on provider
                    if provider == "OpenAI":
                        if api_base:
                            openai.api_base = api_base
                        result = self._call_openai_api(model, api_key, max_tokens, temperature)
                    elif provider == "Anthropic":
                        result = self._call_anthropic_api(model, api_key, max_tokens, temperature)
                    elif provider == "Custom":
                        result = self._call_custom_api(model, api_key, api_base, max_tokens, temperature)
                    else:
                        raise ValueError(f"Unsupported provider: {provider}")
                    
                    # Cache successful result
                    self._save_to_cache(cache_key, result)
                    
                    self.finished.emit(result)
                    return
                    
                except RateLimitError as e:
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    if attempt < max_retries - 1:
                        logger.warning(f"Rate limit hit (attempt {attempt + 1}): {e}")
                        self.progress.emit(f"Rate limit reached. Retrying in {delay} seconds...")
                        time.sleep(delay)
                    else:
                        raise
                except (APITimeoutError, APIError) as e:
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    if attempt < max_retries - 1:
                        logger.warning(f"API error (attempt {attempt + 1}): {e}")
                        self.progress.emit(f"Retrying analysis ({attempt + 2}/{max_retries})")
                        time.sleep(delay)
                    else:
                        raise
                except APIStatusError as e:
                    # Don't retry on status errors (like invalid API key)
                    logger.error(f"API status error: {e}")
                    raise
            
        except Exception as e:
            logger.error(f"Error in AI processing: {e}", exc_info=True)
            # Transform error messages into user-friendly format
            error_msg = self._get_user_friendly_error(e)
            self.error.emit(error_msg)
            
    def _get_user_friendly_error(self, error: Exception) -> str:
        """Convert technical error messages into user-friendly format."""
        if isinstance(error, anthropic.BadRequestError):
            if "too many total text bytes" in str(error):
                return "The file is too large for analysis. The content will be automatically split into smaller chunks."
            return "Invalid request to AI service. Please check your input and try again."
        elif isinstance(error, RateLimitError):
            return "API rate limit reached. Please wait a few minutes and try again."
        elif isinstance(error, APITimeoutError):
            return "The request timed out. Please try again."
        elif isinstance(error, ValueError):
            return str(error)  # ValueError messages are usually already user-friendly
        else:
            return f"An unexpected error occurred: {str(error)}"
            
    def _call_openai_api(self, model: str, api_key: str, max_tokens: int, temperature: float) -> str:
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
                max_tokens=max_tokens,
                temperature=temperature
            )
            full_response.append(response.choices[0].message.content)
            
        return "\n".join(full_response)
        
    def _call_anthropic_api(self, model: str, api_key: str, max_tokens: int, temperature: float) -> str:
        """Make call to Anthropic API using official client library."""
        self.progress.emit("Analyzing code with Claude...")
        
        try:
            # Initialize Anthropic client
            client = anthropic.Anthropic(api_key=api_key)
            
            # Check input size and split if necessary
            prompt_bytes = len(self.prompt.encode('utf-8'))
            if prompt_bytes > self.ANTHROPIC_MAX_BYTES:
                chunks = self._split_text_by_bytes(self.prompt, self.ANTHROPIC_CHUNK_SIZE)
                self.progress.emit(f"Content split into {len(chunks)} parts for processing")
                
                full_response = []
                for i, chunk in enumerate(chunks, 1):
                    if self._stop_requested:
                        break
                        
                    self.progress.emit(f"Processing part {i} of {len(chunks)}")
                    
                    # Process each chunk
                    messages: List[MessageParam] = [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Part {i}/{len(chunks)}:\n\n{chunk}"
                                }
                            ]
                        }
                    ]
                    
                    message = client.messages.create(
                        model=model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        system="You are an expert code analyzer. Analyze the provided code thoroughly and provide detailed insights.",
                        messages=messages
                    )
                    
                    if message.content:
                        response_text = []
                        for block in message.content:
                            if isinstance(block, ContentBlock) and block.type == "text":
                                response_text.append(block.text)
                        full_response.append("\n".join(response_text))
                
                return "\n\n=== Analysis Summary ===\n\n" + "\n\n=== Next Part ===\n\n".join(full_response)
                
            else:
                # Single request for smaller content
                messages: List[MessageParam] = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": self.prompt
                            }
                        ]
                    }
                ]
                
                message = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system="You are an expert code analyzer. Analyze the provided code thoroughly and provide detailed insights.",
                    messages=messages
                )
                
                if message.content:
                    response_text = []
                    for block in message.content:
                        if isinstance(block, ContentBlock) and block.type == "text":
                            response_text.append(block.text)
                    return "\n".join(response_text)
                else:
                    raise ValueError("No content in response")
                    
        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            raise
        
    def _call_custom_api(self, model: str, api_key: str, api_base: str, max_tokens: int, temperature: float) -> str:
        """Make call to custom API endpoint."""
        if not api_base:
            raise ValueError("API base URL is required for custom provider")
            
        self.progress.emit("Analyzing code with custom provider...")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "prompt": self.prompt,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        response = requests.post(api_base, headers=headers, json=data)
        
        if response.status_code != 200:
            raise ValueError(f"API request failed: {response.text}")
            
        return response.json()["response"]
        
    def _split_prompt(self, prompt: str, max_tokens: int) -> list[str]:
        """Split a long prompt into smaller chunks based on token count."""
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
        
    def _split_text_by_bytes(self, text: str, chunk_size: int) -> List[str]:
        """Split text into chunks based on byte size while preserving line integrity."""
        chunks = []
        current_chunk = []
        current_size = 0
        
        for line in text.split('\n'):
            line_bytes = len((line + '\n').encode('utf-8'))
            
            if current_size + line_bytes > chunk_size:
                if current_chunk:  # Save current chunk if it exists
                    chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_bytes
            else:
                current_chunk.append(line)
                current_size += line_bytes
                
        if current_chunk:  # Add the last chunk
            chunks.append('\n'.join(current_chunk))
            
        return chunks
