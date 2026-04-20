"""
Ombre Logger
============
Structured logging for the Ombre pipeline.
Logs stay local — never transmitted externally.
"""

from __future__ import annotations

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Get a logger for an Ombre module."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.propagate = False
    return logger
