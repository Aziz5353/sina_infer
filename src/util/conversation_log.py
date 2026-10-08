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
    "route",
    "query_type",
    "clarify_reason",
    "refusal_reason",
    "case",
    "missing_critical_info",
    "red_flags",
    "search_queries",
    "search_attempts",
    "evidence_gaps",
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
        "route": final_state.get("route", ""),
        "query_type": final_state.get("query_type", ""),
        "clarify_reason": final_state.get("clarify_reason", ""),
        "refusal_reason": final_state.get("refusal_reason") or "",
        "case": _json(final_state.get("case")),
        "missing_critical_info": _json(final_state.get("missing_critical_info")),
        "red_flags": _json(final_state.get("red_flags")),
        "search_queries": _json(final_state.get("search_queries")),
        "search_attempts": final_state.get("search_attempts", ""),
        "evidence_gaps": _json(final_state.get("evidence_gaps")),
        "sources": _json(sources),
        "answer": answer,
        "latency_s": f"{latency_s:.2f}",
        "error": error,
    }


def save_conversation(row: dict) -> None:
    """Append one turn to the conversations CSV. Never raises."""
    if not settings.SAVE_CONVERSATIONS:
        return
    path = Path(settings.CONVERSATIONS_CSV_PATH)
    try:
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            write_header = not path.exists() or path.stat().st_size == 0
            with path.open("a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                if write_header:
                    writer.writeheader()
                writer.writerow(row)
    except Exception:
        logger.exception(f"conversation_log | failed to write {path}")
