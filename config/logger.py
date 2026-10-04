import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-5s | %(name)-32s | %(message)s"
_LOG_DATEFMT = "%H:%M:%S"
_LOG_DIR = Path("logs")
_LOG_MAX_BYTES = 50 * 1024 * 1024  # 50 MB per file before rotating
_LOG_BACKUP_COUNT = 3              # keep <name>.log{,.1,.2,.3}; older are deleted


def _file_handler(path: Path, level: int, formatter: logging.Formatter) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path,
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


def setup_logger() -> None:
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATEFMT)

    console = logging.StreamHandler()
    console.setLevel(settings.LOG_LEVEL)
    console.setFormatter(formatter)

    handlers: list[logging.Handler] = [console]
    if settings.LOG_TO_FILE:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        handlers.append(_file_handler(_LOG_DIR / "app-debug.log", logging.DEBUG, formatter))
        handlers.append(_file_handler(_LOG_DIR / "app-info.log", logging.INFO, formatter))

    logging.basicConfig(
        level=logging.DEBUG if settings.LOG_TO_FILE else settings.LOG_LEVEL,
        handlers=handlers,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
