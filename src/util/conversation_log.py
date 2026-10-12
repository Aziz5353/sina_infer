import csv
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from src.config.settings import settings

logger = logging.getLogger(__name__)

# One row per /chat turn. List/dict fields are stored as JSON strings so the
# file round-trips cleanly with pandas (`json.loads` per cell).
FIELDNAMES = (
    "timestamp",
    "message",
    "history",
    "standalone_message",
    "language",
    "route",
    "query_type",
    "task",
    "case",
    "missing_critical_info",
    "red_flags",
    "search_queries",
    "sources",
    "answer",
    "latency_s",
    "error",
)

_lock = threading.Lock()


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False) if value else ""


def build_row(final_state: dict, answer: str, latency_s: float, error: str = "") -> dict:
    sources = [
        {"url": r.get("url"), "title": r.get("title"), "score": r.get("score")}
        for r in final_state.get("web_results") or []
    ]
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "message": final_state.get("message", ""),
        "history": _json(final_state.get("history")),
        "standalone_message": final_state.get("standalone_message", ""),
        "language": final_state.get("language", ""),
        "route": final_state.get("route", ""),
        "query_type": final_state.get("query_type", ""),
        "task": final_state.get("task", ""),
        "case": _json(final_state.get("case")),
        "missing_critical_info": _json(final_state.get("missing_critical_info")),
        "red_flags": _json(final_state.get("red_flags")),
        "search_queries": _json(final_state.get("search_queries")),
        "sources": _json(sources),
        "answer": answer,
        "latency_s": f"{latency_s:.2f}",
        "error": error,
    }


def _target_path() -> Path:
    """The configured CSV, or the first sibling (_v2, _v3, ...) that is new or has the
    current columns, so rows never end up under an older version's header."""
    base = Path(settings.CONVERSATIONS_CSV_PATH)
    version = 1
    while True:
        path = base if version == 1 else base.with_name(f"{base.stem}_v{version}{base.suffix}")
        if not path.exists() or path.stat().st_size == 0:
            return path
        with path.open(newline="", encoding="utf-8") as f:
            if tuple(next(csv.reader(f), [])) == FIELDNAMES:
                return path
        version += 1


def save_conversation(row: dict) -> None:
    """Append one turn to the conversations CSV. Never raises."""
    if not settings.SAVE_CONVERSATIONS:
        return
    path = Path(settings.CONVERSATIONS_CSV_PATH)
    try:
        with _lock:
            path = _target_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            write_header = not path.exists() or path.stat().st_size == 0
            with path.open("a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                if write_header:
                    writer.writeheader()
                writer.writerow(row)
    except Exception:
        logger.exception(f"conversation_log | failed to write {path}")
