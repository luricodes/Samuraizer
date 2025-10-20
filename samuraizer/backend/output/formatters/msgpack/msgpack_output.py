from __future__ import annotations

import logging
import tempfile
import shutil
import zlib
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Dict,
    Generator,
    Union,
    Optional,
    TypeVar,
    Protocol,
    runtime_checkable,
    List,
    BinaryIO,
)
from dataclasses import dataclass
from types import TracebackType

import msgpack  # type: ignore[import-untyped]
from colorama import Fore, Style

# Type definitions
T = TypeVar('T')
JsonValue = Union[Dict[str, Any], list[Any], str, int, float, bool, None]

@runtime_checkable
class MessagePackSerializable(Protocol):
    """Protocol for objects that can be serialized to MessagePack format."""
    def to_msgpack(self) -> bytes: ...

@dataclass
class MessagePackConfig:
    """Configuration for MessagePack serialization."""
    use_compression: bool = False
    compression_level: int = 6  # zlib default
    use_bin_type: bool = True
    use_single_float: bool = True
    strict_types: bool = True
    unicode_errors: str = 'replace'
    datetime_handling: bool = True
    max_str_len: int = 2**32 - 1  # MessagePack string length limit
    max_bin_len: int = 2**32 - 1  # MessagePack binary length limit

    @classmethod
    def from_dict(cls, config: Optional[Dict[str, Any]] = None) -> MessagePackConfig:
        """Create a MessagePackConfig from a dictionary."""
        if config is None:
            return cls()
        
        return cls(
            use_compression=config.get('use_compression', False),
            compression_level=config.get('compression_level', 6),
            use_bin_type=config.get('use_bin_type', True),
            use_single_float=config.get('use_single_float', True),
            strict_types=config.get('strict_types', True),
            unicode_errors=config.get('unicode_errors', 'replace'),
            datetime_handling=config.get('datetime_handling', True),
            max_str_len=config.get('max_str_len', 2**32 - 1),
            max_bin_len=config.get('max_bin_len', 2**32 - 1)
        )

class MessagePackError(Exception):
    """Base exception for MessagePack-related errors."""
    pass

class MessagePackSerializationError(MessagePackError):
    """Raised when serialization fails."""
    pass

class MessagePackSizeLimitError(MessagePackError):
    """Raised when data exceeds MessagePack size limits."""
    pass

def compress_data(data: bytes, level: int = 6) -> bytes:
    """Compress data using zlib with specified compression level."""
    try:
        return zlib.compress(data, level)
    except zlib.error as e:
        raise MessagePackError(f"Compression failed: {e}")

def decompress_data(data: bytes) -> bytes:
    """Decompress zlib-compressed data."""
    try:
        return zlib.decompress(data)
    except zlib.error as e:
        raise MessagePackError(f"Decompression failed: {e}")

class MessagePackEncoder:
    """Handles encoding of Python objects to MessagePack format."""
    
    def __init__(self, config: Optional[MessagePackConfig] = None):
        self.config = config or MessagePackConfig()

    def _convert_value(self, obj: Any) -> Any:
        """Convert Python objects to MessagePack-compatible format."""
        if isinstance(obj, datetime):
            return {
                '__datetime__': True,
                'timestamp': obj.timestamp(),
                'tz': str(obj.tzinfo) if obj.tzinfo else None
            }
        elif isinstance(obj, Path):
            return str(obj)
        elif isinstance(obj, bytes):
            if len(obj) > self.config.max_bin_len:
                raise MessagePackSizeLimitError(
                    f"Binary data exceeds maximum length: {len(obj)} > {self.config.max_bin_len}"
                )
            return obj
        elif isinstance(obj, str):
            if len(obj) > self.config.max_str_len:
                raise MessagePackSizeLimitError(
                    f"String exceeds maximum length: {len(obj)} > {self.config.max_str_len}"
                )
            return obj
        elif isinstance(obj, (set, frozenset)):
            return list(obj)
        elif isinstance(obj, MessagePackSerializable):
            return obj.to_msgpack()
        return obj

    def encode(self, data: Any) -> bytes:
        """Encode data to MessagePack format with optional compression."""
        try:
            packed = msgpack.packb(
                data,
                default=self._convert_value,
                use_bin_type=self.config.use_bin_type,
                use_single_float=self.config.use_single_float,
                strict_types=self.config.strict_types,
                unicode_errors=self.config.unicode_errors
            )
            
            if self.config.use_compression:
                return compress_data(packed, self.config.compression_level)
            return packed
        except (TypeError, msgpack.PackException) as e:
            raise MessagePackSerializationError(f"Serialization failed: {e}")

class MessagePackDecoder:
    """Handles decoding of MessagePack data to Python objects."""
    
    def __init__(self, config: Optional[MessagePackConfig] = None):
        self.config = config or MessagePackConfig()

    def _convert_value(self, obj: Any) -> Any:
        """Convert MessagePack data back to Python objects."""
        if isinstance(obj, dict):
            if obj.get('__datetime__'):
                timestamp = obj.get('timestamp')
                if timestamp is not None:
                    return datetime.fromtimestamp(timestamp)
            return obj
        return obj

    def decode(self, data: bytes) -> Any:
        """Decode MessagePack data with optional decompression."""
        try:
            if self.config.use_compression:
                data = decompress_data(data)
            
            return msgpack.unpackb(
                data,
                object_hook=self._convert_value,
                raw=False,
                strict_map_key=self.config.strict_types
            )
        except (TypeError, msgpack.UnpackException) as e:
            raise MessagePackError(f"Deserialization failed: {e}")

    def decode_stream(self, data: bytes) -> List[Any]:
        """Decode multiple MessagePack objects from a stream."""
        try:
            if self.config.use_compression:
                data = decompress_data(data)
            
            unpacker = msgpack.Unpacker(
                raw=False,
                object_hook=self._convert_value,
                strict_map_key=self.config.strict_types
            )
            unpacker.feed(data)
            
            return list(unpacker)
        except (TypeError, msgpack.UnpackException) as e:
            raise MessagePackError(f"Stream deserialization failed: {e}")

@dataclass
class _PayloadValidationResult:
    """Outcome of validating the decoded MessagePack payload."""

    is_valid: bool
    reason: Optional[str] = None

    def log_failure(self) -> None:
        if not self.is_valid and self.reason:
            logging.debug("MessagePack validation failed: %s", self.reason)


def _validate_msgpack_entry(entry: Any, context: str) -> _PayloadValidationResult:
    """Validate a single MessagePack entry produced by ``decode_stream``."""

    if isinstance(entry, dict):
        if not entry:
            return _PayloadValidationResult(False, f"mapping entry at {context} is empty")

        non_string_keys = [type(key).__name__ for key in entry.keys() if not isinstance(key, str)]
        if non_string_keys:
            return _PayloadValidationResult(
                False,
                (
                    f"mapping entry at {context} contains non-string keys: "
                    f"{sorted(set(non_string_keys))}"
                ),
            )

        return _PayloadValidationResult(True)

    if isinstance(entry, list):
        if not entry:
            return _PayloadValidationResult(False, f"list entry at {context} is empty")

        for nested_index, nested in enumerate(entry):
            nested_context = f"{context}[{nested_index}]"
            nested_result = _validate_msgpack_entry(nested, nested_context)
            if not nested_result.is_valid:
                return nested_result

        return _PayloadValidationResult(True)

    return _PayloadValidationResult(
        False,
        f"entry at {context} has unsupported type {type(entry).__name__}",
    )


def _validate_msgpack_payload(decoded_objects: List[Any]) -> _PayloadValidationResult:
    """Ensure decoded MessagePack payload matches expected structure."""

    if not decoded_objects:
        return _PayloadValidationResult(False, "decoded payload is empty")

    for index, entry in enumerate(decoded_objects):
        result = _validate_msgpack_entry(entry, f"index {index}")
        if not result.is_valid:
            return result

    return _PayloadValidationResult(True)

class MessagePackStreamWriter:
    """Context manager for streaming MessagePack data."""
    
    def __init__(
        self,
        output_file: str,
        config: Optional[MessagePackConfig] = None
    ):
        self.output_file = output_file
        self.file: Optional[BinaryIO] = None
        self.encoder = MessagePackEncoder(config)
        self.records_written = 0
        self.bytes_written = 0

    def __enter__(self) -> MessagePackStreamWriter:
        self.file = open(self.output_file, 'wb')
        return self

    def write_entry(self, data: Dict[str, Any]) -> None:
        """Write a single entry to the MessagePack stream."""
        if self.file is None:
            raise RuntimeError("MessagePackStreamWriter not initialized. Call __enter__ first.")
        try:
            encoded_data = self.encoder.encode(data)
            self.file.write(encoded_data)
            self.records_written += 1
            self.bytes_written += len(encoded_data)
            
            if self.records_written % 1000 == 0:
                logging.debug(
                    f"Processed {self.records_written} records, "
                    f"total bytes written: {self.bytes_written:,}"
                )
        except MessagePackError as e:
            logging.error(f"Error packing entry: {e}")
            # Write error entry
            error_entry = {
                "type": "error",
                "content": f"Failed to pack entry: {str(e)}",
                "original_data": str(data)
            }
            self.file.write(self.encoder.encode(error_entry))

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if self.file:
            self.file.close()
            logging.debug(
                f"MessagePack stream complete: {self.records_written:,} records, "
                f"{self.bytes_written:,} bytes written"
            )

def validate_msgpack_file(file_path: str, config: Optional[Dict[str, Any]] = None) -> bool:
    """Validate a MessagePack file by attempting to decode it."""
    try:
        file_path_obj = Path(file_path)
        file_size = file_path_obj.stat().st_size

        if file_size == 0:
            logging.error(f"{Fore.RED}MessagePack validation failed: file is empty{Style.RESET_ALL}")
            return False

        msgpack_config = MessagePackConfig.from_dict(config)

        with file_path_obj.open('rb') as f:
            raw_bytes = f.read()

        if not raw_bytes:
            logging.error(f"{Fore.RED}MessagePack validation failed: file contains no data{Style.RESET_ALL}")
            return False

        if len(raw_bytes) != file_size:
            logging.error(
                f"{Fore.RED}MessagePack validation failed: expected {file_size} bytes but read {len(raw_bytes)}{Style.RESET_ALL}"
            )
            return False

        decoder = MessagePackDecoder(msgpack_config)
        decoded_objects = decoder.decode_stream(raw_bytes)

        payload_validation = _validate_msgpack_payload(decoded_objects)
        if not payload_validation.is_valid:
            payload_validation.log_failure()
            reason_suffix = (
                f" ({payload_validation.reason})" if payload_validation.reason else ""
            )
            logging.error(
                f"{Fore.RED}MessagePack validation failed: decoded payload has unexpected structure{reason_suffix}{Style.RESET_ALL}"
            )
            return False

        logging.debug(f"{Fore.GREEN}MessagePack validation details:{Style.RESET_ALL}")
        logging.debug(f"  - File: {file_path}")
        logging.debug(f"  - Size: {file_size:,} bytes")
        logging.debug(
            f"  - Compression: {'Enabled' if msgpack_config.use_compression else 'Disabled'}"
        )
        logging.debug(f"  - Structure: Stream with {len(decoded_objects)} entries")
        if decoded_objects:
            logging.debug(f"  - First entry type: {type(decoded_objects[0]).__name__}")
        logging.debug(f"  - Format: Valid MessagePack")
        logging.debug(f"  - Integrity: Data successfully decoded")

        logging.info(f"{Fore.GREEN}MessagePack validation successful{Style.RESET_ALL}")
        return True
    except (IOError, MessagePackError) as e:
        logging.error(f"{Fore.RED}MessagePack validation failed: {e}{Style.RESET_ALL}")
        return False


def output_to_msgpack(
    data: Dict[str, Any],
    output_file: str,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """Write data to a MessagePack file."""
    msgpack_config = MessagePackConfig.from_dict(config)
    encoder = MessagePackEncoder(msgpack_config)
    
    try:
        temp_dir = Path(output_file).parent
        with tempfile.NamedTemporaryFile('wb', delete=False, dir=temp_dir) as temp_file:
            encoded_data = encoder.encode(data)
            temp_file.write(encoded_data)
            temp_file_path = Path(temp_file.name)

        shutil.move(str(temp_file_path), output_file)
        logging.debug(f"MessagePack output written to '{output_file}'")

        # Validate the written file with the same configuration
        if validate_msgpack_file(output_file, config):
            logging.info(f"{Fore.GREEN}✓ MessagePack file successfully created and validated{Style.RESET_ALL}")
        else:
            logging.error(f"{Fore.RED}✗ MessagePack file validation failed{Style.RESET_ALL}")
    
    except MessagePackError as e:
        logging.error(f"{Fore.RED}MessagePack error: {e}{Style.RESET_ALL}")
        raise
    except IOError as e:
        logging.error(
            f"{Fore.RED}IO error writing MessagePack file '{output_file}': {e}{Style.RESET_ALL}"
        )
        raise
    except Exception as e:
        logging.error(
            f"{Fore.RED}Unexpected error writing MessagePack file '{output_file}': {e}{Style.RESET_ALL}"
        )
        raise

def output_to_msgpack_stream(
    data_generator: Generator[Dict[str, Any], None, None],
    output_file: str,
    config: Optional[Dict[str, Any]] = None
) -> None:
    """Write data to a MessagePack file in streaming mode."""
    msgpack_config = MessagePackConfig.from_dict(config)
    try:
        with MessagePackStreamWriter(output_file, msgpack_config) as writer:
            for data in data_generator:
                if not isinstance(data, dict):
                    logging.error(
                        f"Unexpected data type: {type(data)}. Expected: dict. "
                        f"Data: {data}"
                    )
                    continue
                writer.write_entry(data)

        # Validate the completed stream file with the same configuration
        if validate_msgpack_file(output_file, config):
            logging.info(f"{Fore.GREEN}✓ MessagePack stream file successfully created and validated{Style.RESET_ALL}")
        else:
            logging.error(f"{Fore.RED}✗ MessagePack stream file validation failed{Style.RESET_ALL}")
        
    except IOError as e:
        logging.error(f"IO error writing MessagePack stream: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error writing MessagePack stream: {e}")
        raise
