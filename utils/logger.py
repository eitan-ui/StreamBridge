import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

from models.config import APP_DATA_DIR

LOG_DIR = os.path.join(APP_DATA_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def setup_file_logger() -> logging.Logger:
    """Setup a file logger with daily rotation (max 7 files)."""
    logger = logging.getLogger("streambridge")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        log_file = os.path.join(LOG_DIR, "streambridge.log")
        handler = TimedRotatingFileHandler(
            log_file, when="midnight", backupCount=7, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(handler)

    return logger
