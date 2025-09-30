import logging
import os
from collections import deque
from logging.handlers import RotatingFileHandler
from threading import Lock
from typing import Any, Dict, List, Optional

import coloredlogs

# Global log buffer for real-time streaming
_log_buffer: deque = deque(maxlen=1000)  # Keep last 1000 log entries
_log_buffer_lock = Lock()
_log_listeners: List = []  # Store SSE listeners


class BufferedHandler(logging.Handler):
    """Custom handler that stores logs in memory buffer for real-time streaming."""

    def emit(self, record):
        try:
            msg = self.format(record)
            log_entry = {
                "timestamp": (
                    self.formatter.formatTime(record) if self.formatter else record.asctime
                ),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "formatted": msg,
            }

            with _log_buffer_lock:
                _log_buffer.append(log_entry)

            # Notify all SSE listeners
            for listener in _log_listeners[:]:  # Copy list to avoid modification during iteration
                try:
                    listener(log_entry)
                except Exception:
                    # Remove broken listeners
                    if listener in _log_listeners:
                        _log_listeners.remove(listener)

        except Exception:
            self.handleError(record)


def add_log_listener(listener):
    """Add a listener for real-time log streaming."""
    _log_listeners.append(listener)


def remove_log_listener(listener):
    """Remove a log listener."""
    if listener in _log_listeners:
        _log_listeners.remove(listener)


def get_log_buffer(
    limit: Optional[int] = None, level_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get logs from the buffer with optional filtering."""
    with _log_buffer_lock:
        logs = list(_log_buffer)

    if level_filter:
        logs = [log for log in logs if log["level"] == level_filter.upper()]

    if limit:
        logs = logs[-limit:]

    return logs


def setup_logging(config):
    """Setup logging based on configuration"""
    log_level = config.get("logs", {}).get("level", "INFO").upper()

    # Create logs directory
    log_dir = "/config/logs"
    os.makedirs(log_dir, exist_ok=True)

    # Configure the root logger
    logger = logging.getLogger()

    # Clear any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Console handler with coloredlogs
    coloredlogs.install(
        level=log_level,
        fmt="%(asctime)s - %(levelname)s - %(message)s",
        logger=logger,
    )

    # File handler with rotation
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "stash-manager.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(log_level)
    logger.addHandler(file_handler)

    # Buffer handler for real-time streaming
    buffer_handler = BufferedHandler()
    buffer_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    buffer_handler.setFormatter(buffer_formatter)
    buffer_handler.setLevel(log_level)
    logger.addHandler(buffer_handler)

    # Update werkzeug logger level
    werkzeug_logger = logging.getLogger("werkzeug")
    if log_level != "DEBUG":
        werkzeug_logger.setLevel(logging.WARNING)
    else:
        werkzeug_logger.setLevel(logging.INFO)

    logging.info(f"Logging level set to {log_level}")
    logging.info(f"Log files will be written to {log_dir}")


def reconfigure_logging(log_level: str):
    """Reconfigure logging level at runtime"""
    log_level = log_level.upper()

    # Update root logger level
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Update all handlers
    for handler in logger.handlers:
        handler.setLevel(log_level)

    # Update werkzeug logger level
    werkzeug_logger = logging.getLogger("werkzeug")
    if log_level != "DEBUG":
        werkzeug_logger.setLevel(logging.WARNING)
    else:
        werkzeug_logger.setLevel(logging.INFO)

    logging.info(f"Logging level updated to {log_level}")
