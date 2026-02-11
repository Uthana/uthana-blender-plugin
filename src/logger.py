import logging
import os
import sys

# Create single logger instance for the entire uplugin
logger = logging.getLogger("uthana.uplugin")


def setup_logger():
    """Setup logging configuration - call this once during plugin initialization"""
    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        return

    # Get log level from environment variable, default to INFO
    log_level_str = os.getenv("UTHANA_LOGLEVEL", "INFO").upper()

    # Map string to logging level
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    log_level = level_map.get(log_level_str, logging.INFO)

    # Create console handler for terminal output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Create formatter with timestamp and module name
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [Uthana] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)

    # Configure logger
    logger.addHandler(console_handler)
    logger.setLevel(log_level)
    logger.propagate = False  # Don't propagate to root logger
