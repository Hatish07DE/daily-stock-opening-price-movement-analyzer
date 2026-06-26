import logging
from pathlib import Path
from datetime import datetime


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logs"


def setup_logger(name: str = "stock_pipeline") -> logging.Logger:
    """
    Creates and returns a reusable logger for the stock pipeline.

    Logs will be written to:
    1. Terminal/console
    2. logs/pipeline_YYYY-MM-DD.log
    """

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_date = datetime.utcnow().strftime("%Y-%m-%d")
    log_file_path = LOG_DIR / f"pipeline_{log_date}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid duplicate logs if logger is imported multiple times
    if logger.handlers:
        return logger

    log_format = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(log_format)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger