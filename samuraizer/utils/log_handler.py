import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Dict, List, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

@dataclass
class LogEntry:
    """Data class for storing log entries."""
    message: str
    level: int
    color: str
    timestamp: float
    formatted: str

class GuiLogHandler(QObject, logging.Handler):
    """
    Custom logging handler that emits Qt signals for log messages.
    Supports batching and buffer management.
    """
    
    # Signal emitted when new log records are received
    log_record_received = pyqtSignal(dict)
    batch_records_received = pyqtSignal(list)
    
    # Define colors for different log levels
    LEVEL_COLORS = {
        logging.DEBUG: "#808080",    # Gray
        logging.INFO: "#4CAF50",     # Green
        logging.WARNING: "#FFA500",  # Orange
        logging.ERROR: "#FF0000",    # Red
        logging.CRITICAL: "#800080", # Purple
    }

    def __init__(
        self,
        max_buffer_size: int = 1000,
        batch_size: int = 10,
        batch_interval: int = 100  # ms
    ):
        super(QObject, self).__init__()
        super(logging.Handler, self).__init__()
        
        self.flushOnClose = False
        self._max_buffer_size = max_buffer_size
        self._batch_size = batch_size
        self._buffer: Deque[LogEntry] = deque(maxlen=max_buffer_size)
        self._current_batch: List[LogEntry] = []
        
        # Set up default formatter
        self.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        
        # Set up batch timer
        self._batch_timer = QTimer(self)
        self._batch_timer.timeout.connect(self._emit_batch)
        self._batch_timer.start(batch_interval)

    def prepare_for_shutdown(self):
        """Prepare the handler for shutdown."""
        try:
            if self._batch_timer.isActive():
                self._batch_timer.stop()
            if self._current_batch:
                self._emit_batch()
            self._buffer.clear()
            self._current_batch.clear()
        except Exception:
            pass

    def setMaxBufferSize(self, size: int) -> None:
        """Set maximum number of log entries to keep in buffer."""
        # Create new buffer with new size
        new_buffer: Deque[LogEntry] = deque(maxlen=size)
        
        # If new size is smaller, only keep most recent entries
        entries = list(self._buffer)
        if size < len(entries):
            entries = entries[-size:]
            
        # Add entries to new buffer
        new_buffer.extend(entries)
        self._buffer = new_buffer
        self._max_buffer_size = size

    def getBuffer(self) -> List[LogEntry]:
        """Get all entries in the buffer."""
        return list(self._buffer)

    def getBufferSize(self) -> int:
        """Get current number of entries in buffer."""
        return len(self._buffer)

    def emit(self, record: logging.LogRecord) -> None:
        """Process and emit a log record."""
        try:
            # Format the message
            msg = self.format(record)
            
            # Create log entry
            entry = LogEntry(
                message=record.getMessage(),
                level=record.levelno,
                color=self.LEVEL_COLORS.get(record.levelno, "#000000"),
                timestamp=record.created,
                formatted=msg
            )
            
            # Add to buffer (deque handles size automatically)
            self._buffer.append(entry)
            
            # Add to current batch
            self._current_batch.append(entry)
            
            # Emit immediately for critical and error logs
            if record.levelno >= logging.ERROR:
                self._emit_single(entry)
            # Emit batch if it's full
            elif len(self._current_batch) >= self._batch_size:
                self._emit_batch()
                
        except Exception:
            self.handleError(record)

    def _emit_single(self, entry: LogEntry) -> None:
        """Emit a single log entry."""
        try:
            self.log_record_received.emit({
                'message': entry.formatted,
                'level': entry.level,
                'color': entry.color,
                'timestamp': entry.timestamp,
                'buffer_size': len(self._buffer)
            })
        except Exception:
            pass

    def _emit_batch(self) -> None:
        """Emit the current batch of log entries."""
        if self._current_batch:
            try:
                batch_data: List[Dict[str, float | int | str]] = [{
                    'message': entry.formatted,
                    'level': entry.level,
                    'color': entry.color,
                    'timestamp': entry.timestamp,
                    'buffer_size': len(self._buffer)
                } for entry in self._current_batch]
                
                self.batch_records_received.emit(batch_data)
                
            except Exception:
                pass
            finally:
                self._current_batch.clear()

    def clearBuffer(self) -> None:
        """Clear all entries from the buffer."""
        self._buffer.clear()
        self._current_batch.clear()
