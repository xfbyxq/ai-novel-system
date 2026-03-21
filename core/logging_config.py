"""Logging configuration for the Novel Generation System."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from backend.config import settings

# Logging levels
LOG_LEVEL = logging.INFO
if settings.APP_DEBUG:
    LOG_LEVEL = logging.DEBUG

# Log format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Log file path
LOG_FILE = "novel_system.log"


def setup_logging():
    """Set up logging configuration."""
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    # Clear existing handlers
    root_logger.handlers = []

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(console_handler)

    # Create file handler (rotating)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
    )
    file_handler.setLevel(LOG_LEVEL)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(file_handler)

    # Set log levels for specific libraries
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    return root_logger


# Initialize logging
logger = setup_logging()
