"""Structured logging configuration for DocuMind AI.

Provides a single ``get_logger`` function that returns a configured logger
with JSON-like formatting, useful for production debugging and audit trails.
"""

import logging
import sys
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """Custom formatter that produces structured, parseable log lines."""

    def format(self, record: logging.LogRecord) -> str:
        # Build a structured log entry with timestamp, level, module, message
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Include exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include extra fields passed via logger.info("msg", extra={...})
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            }:
                log_entry[key] = value

        # Simple key=value formatting (no external dependency)
        parts = [f"[{log_entry['timestamp']}]", f"{log_entry['level']:<8}",
                 f"{log_entry['logger']}:{log_entry['line']}",
                 log_entry["message"]]

        if "exception" in log_entry:
            parts.append(f"\n{log_entry['exception']}")

        return " | ".join(parts)


def get_logger(name: str = "documind") -> logging.Logger:
    """Return a configured logger instance.

    Args:
        name: Logger name, typically the module name via ``__name__``.

    Returns:
        A logging.Logger with structured formatting attached.
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Console handler with structured formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(StructuredFormatter())
    logger.addHandler(console_handler)

    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False

    return logger
