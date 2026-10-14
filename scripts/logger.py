#!/usr/bin/env python3
"""
Centralized Logging Module

Provides file-based logging with automatic log rotation on script start.
Logs are stored in /logs/{module_name}.log with archives in /logs/archives/.
"""
import os
import shutil
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import TextIO


class LogLevel(IntEnum):
    DEBUG = 10
    INFO = 20
    WARN = 30
    ERROR = 40


# Module-level state
_log_file: TextIO | None = None
_log_level: LogLevel = LogLevel.INFO
_console_enabled: bool = False
_file_enabled: bool = True
_module_name: str = "app"
_logs_dir: Path | None = None


def _get_logs_dir() -> Path:
    """Get the logs directory path."""
    global _logs_dir
    if _logs_dir is None:
        # logs/ is at the same level as scripts/
        scripts_dir = Path(__file__).parent
        _logs_dir = scripts_dir.parent / "logs"
        _logs_dir.mkdir(exist_ok=True)
        (_logs_dir / "archives").mkdir(exist_ok=True)
    return _logs_dir


def _get_timestamp() -> str:
    """Get formatted timestamp for log entries."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_archive_timestamp() -> str:
    """Get formatted timestamp for archive filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _archive_existing_log(log_path: Path) -> None:
    """Move existing non-empty log file to archives."""
    if log_path.exists() and log_path.stat().st_size > 0:
        archives_dir = _get_logs_dir() / "archives"
        archive_name = f"{log_path.stem}_{_get_archive_timestamp()}.log"
        archive_path = archives_dir / archive_name
        shutil.move(str(log_path), str(archive_path))


def init_logger(
    module_name: str,
    level: LogLevel = LogLevel.INFO,
    console_enabled: bool = False,
    file_enabled: bool = True
) -> None:
    """
    Initialize the logger for a module.

    Archives any existing log file and starts fresh.

    Args:
        module_name: Name used for the log file (e.g., "llm_client")
        level: Minimum log level to record
        console_enabled: Whether to also print to console (stderr)
        file_enabled: Whether to write to log file
    """
    global _log_file, _log_level, _console_enabled, _file_enabled, _module_name

    # Close existing log file if open
    if _log_file is not None:
        _log_file.close()
        _log_file = None

    _module_name = module_name
    _log_level = level
    _console_enabled = console_enabled
    _file_enabled = file_enabled

    if _file_enabled:
        log_path = _get_logs_dir() / f"{module_name}.log"
        _archive_existing_log(log_path)
        _log_file = open(log_path, "w", encoding="utf-8")


def ensure_logger(module_name: str) -> None:
    # Re-initializing closes the active file and archives the target, which breaks a long-running
    # process (its own log is swapped out mid-write) and fails if another process holds the file.
    if _log_file is None:
        init_logger(module_name)


def _write_log(level: LogLevel, message: str) -> None:
    """Write a log entry if level meets threshold."""
    if level < _log_level:
        return

    timestamp = _get_timestamp()
    level_name = level.name
    formatted = f"[{timestamp}] [{level_name}] {message}"

    if _file_enabled and _log_file is not None:
        _log_file.write(formatted + "\n")
        _log_file.flush()

    if _console_enabled:
        import sys
        print(formatted, file=sys.stderr)


def debug(message: str) -> None:
    """Log a debug message."""
    _write_log(LogLevel.DEBUG, message)


def info(message: str) -> None:
    """Log an info message."""
    _write_log(LogLevel.INFO, message)


def warn(message: str) -> None:
    """Log a warning message."""
    _write_log(LogLevel.WARN, message)


def error(message: str) -> None:
    """Log an error message."""
    _write_log(LogLevel.ERROR, message)


def log_llm_request(
    model: str,
    provider: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int
) -> None:
    """Log an LLM API request with formatted details."""
    info(f"{'='*60}")
    info(f"LLM REQUEST")
    info(f"Provider: {provider}")
    info(f"Model: {model}")
    info(f"Temperature: {temperature}")
    info(f"Max Tokens: {max_tokens}")
    info(f"Messages:")

    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        # Handle multipart content (images)
        if isinstance(content, list):
            text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
            image_count = sum(1 for p in content if p.get("type") in ("image_url", "image"))
            content_summary = " ".join(text_parts)
            if image_count:
                content_summary += f" [+{image_count} image(s)]"
        else:
            content_summary = content

        # Truncate long content for readability
        if len(content_summary) > 500:
            content_summary = content_summary[:500] + "..."

        info(f"  [{i}] {role}: {content_summary}")


def log_llm_response(response: str, duration_ms: float | None = None) -> None:
    """Log an LLM API response."""
    info(f"LLM RESPONSE:")

    if duration_ms is not None:
        info(f"Duration: {duration_ms:.0f}ms")

    # Truncate very long responses in log
    if len(response) > 2000:
        info(f"Content (truncated): {response[:2000]}...")
        info(f"Full length: {len(response)} characters")
    else:
        info(f"Content: {response}")

    info(f"{'='*60}")


def log_llm_error(error_msg: str) -> None:
    """Log an LLM API error."""
    error(f"LLM ERROR: {error_msg}")
    info(f"{'='*60}")


def close_logger() -> None:
    """Close the log file handle."""
    global _log_file
    if _log_file is not None:
        _log_file.close()
        _log_file = None
