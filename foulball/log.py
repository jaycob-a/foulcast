"""
Structured logging for FoulCast.

Usage:
    from foulball.log import get_logger
    logger = get_logger(__name__)
    logger.info("message")

Controlled by FOULCAST_LOG_LEVEL env var (default: INFO).
"""
import os
import logging

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False
_warned_keys: set[str] = set()


def get_logger(name: str) -> logging.Logger:
    """Get a logger for the given module name."""
    global _configured
    if not _configured:
        level_name = os.environ.get("FOULCAST_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        logging.basicConfig(format=_LOG_FORMAT, datefmt=_DATE_FORMAT, level=level)
        _configured = True
    return logging.getLogger(name)


def _warn_once(logger: logging.Logger, key: str, msg: str):
    """Log a warning only the first time a given key is seen."""
    if key not in _warned_keys:
        _warned_keys.add(key)
        logger.warning(msg)


def enable_file_logging(path: str):
    """Add a file handler to the root logger for shadow run output capture."""
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    logging.getLogger().addHandler(handler)
