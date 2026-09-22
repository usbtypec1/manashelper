import logging
import logging.handlers
from pathlib import Path

_LOG_DIR = Path("logs")
_LOG_FILE = _LOG_DIR / "manashelper.log"
_MAX_BYTES = 50 * 1024 * 1024
_BACKUP_COUNT = 2  # plus the active file itself: 3 files on disk, 150 MB max total


def configure_logging() -> None:
    """Root logger setup: console + a size-rotated file handler under `logs/`.

    Must run after `run_migrations()` (see main.py) — alembic's own `env.py` calls
    `logging.config.fileConfig`, which replaces the root logger's handlers with its own
    console-only ones, so configuring this any earlier would just get overwritten.
    Every `logging.getLogger(...)` call in the app (and in aiogram/apscheduler) propagates up
    to the root logger by default, so this one setup covers all of them, including the
    `@dispatcher.errors()` global handler in main.py.
    """
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
