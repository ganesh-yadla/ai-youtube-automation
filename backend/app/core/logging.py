"""Structured (JSON) logging configuration."""

import logging
import sys

from pythonjsonlogger.json import JsonFormatter


def configure_logging(log_level: str = "INFO") -> None:
    """Configure the root logger to emit structured JSON to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level.upper())
