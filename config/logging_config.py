"""
AyurKosha — Structured Logging Setup
"""

import logging
import sys

from config.settings import settings


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("ayurkosha")
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)

    return logger


logger = setup_logging()
