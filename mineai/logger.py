"""
Centralized logging configuration for MineAI Modpack Translator.

Usage in any module:

  from mineai.logger import get_logger
  log = get_logger(__name__)

  log.info("Translating batch of %d items", len(items))
  log.warning("Placeholder mismatch in key=%s, retrying", key)
  log.error("API request failed", exc_info=True)

The logger writes to:
- A rotating log file at logs/mineai-YYYYMMDD-HHMMSS.log
- The console (level configurable, default INFO)
- An optional GUI handler (passed in by the GUI layer)

Sensitive data such as API keys and Bearer tokens are automatically masked.
"""

from __future__ import annotations

import logging
import logging.handlers
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_SESSION_LOG_PATH = LOG_DIR / f"mineai-{datetime.now():%Y%m%d-%H%M%S}.log"

_ROOT_LOGGER_NAME = "mineai"

# Regex patterns for sensitive values that should never appear in logs.
# We keep the first 6 and last 4 characters for traceability ("sk-prox...a3f9").
_SENSITIVE_PATTERNS = [
  re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),                # OpenAI / OpenRouter style
  re.compile(r"Bearer\s+[A-Za-z0-9._\-]{16,}"),         # HTTP Authorization headers
  re.compile(r"[A-Fa-f0-9]{32,}"),                      # Generic hex tokens (DeepL etc.)
  re.compile(r"key=([A-Za-z0-9_\-]{16,})"),             # Query-string API keys
]


def _mask_secret(value: str) -> str:
  """Keep enough characters to identify a key without leaking it."""
  if len(value) <= 12:
      return "***"
  return f"{value[:6]}...{value[-4:]}"


class SafeFormatter(logging.Formatter):
  """Formatter that strips/masks secrets before emitting a log record."""

  def format(self, record: logging.LogRecord) -> str:
      message = super().format(record)
      for pattern in _SENSITIVE_PATTERNS:
          message = pattern.sub(lambda m: _mask_secret(m.group(0)), message)
      return message


_DEFAULT_FORMAT = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
_DEFAULT_DATEFMT = "%H:%M:%S"

_configured = False


def setup_logging(
  console_level: str = "INFO",
  file_level: str = "DEBUG",
  gui_handler: Optional[logging.Handler] = None,
) -> logging.Logger:
  """Configure the root mineai logger. Safe to call multiple times — only
  the first call adds handlers; subsequent calls update levels.
  """
  global _configured

  root = logging.getLogger(_ROOT_LOGGER_NAME)
  root.setLevel(logging.DEBUG)
  # Prevent double-emission via the Python root logger.
  root.propagate = False

  formatter = SafeFormatter(_DEFAULT_FORMAT, datefmt=_DEFAULT_DATEFMT)

  if not _configured:
      # Rotating file handler — captures everything for post-mortem debugging.
      file_handler = logging.handlers.RotatingFileHandler(
          _SESSION_LOG_PATH,
          maxBytes=10 * 1024 * 1024,  # 10 MB per file
          backupCount=3,
          encoding="utf-8",
      )
      file_handler.setLevel(getattr(logging, file_level.upper(), logging.DEBUG))
      file_handler.setFormatter(formatter)
      root.addHandler(file_handler)

      # Console handler — what the user sees in stdout.
      console_handler = logging.StreamHandler()
      console_handler.setLevel(getattr(logging, console_level.upper(), logging.INFO))
      console_handler.setFormatter(formatter)
      root.addHandler(console_handler)

      _configured = True
  else:
      # Update levels on existing handlers without re-adding them.
      for handler in root.handlers:
          if isinstance(handler, logging.handlers.RotatingFileHandler):
              handler.setLevel(getattr(logging, file_level.upper(), logging.DEBUG))
          elif isinstance(handler, logging.StreamHandler):
              handler.setLevel(getattr(logging, console_level.upper(), logging.INFO))

  if gui_handler is not None and gui_handler not in root.handlers:
      gui_handler.setFormatter(formatter)
      gui_handler.setLevel(logging.INFO)
      root.addHandler(gui_handler)

  return root


def get_logger(name: str) -> logging.Logger:
  """Return a child logger under the mineai namespace.

  Typical usage:
      log = get_logger(__name__)   # -> "mineai.engines.openrouter"
  """
  if name.startswith(_ROOT_LOGGER_NAME):
      # Avoid double-prefixing ("mineai.mineai.engines.foo").
      return logging.getLogger(name)
  return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")


def current_log_path() -> Path:
  """Path to the current session's log file. Useful for the GUI's
  'Open log file' button and for bug-report instructions in the README.
  """
  return _SESSION_LOG_PATH
