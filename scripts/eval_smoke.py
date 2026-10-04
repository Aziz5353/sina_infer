"""Smoke-test the graph against a fixed set of inputs.

Run after any graph/prompt/config change to eyeball whether quality regressed:

    uv run python -m scripts.eval_smoke
        # or
    python -m scripts.eval_smoke

Edit TEST_INPUTS below to put your own 5 questions. Each run prints a summary
to the console AND writes a timestamped JSON file under scripts/eval_runs/ so
you can diff two runs to spot regressions.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from inference.graph import build_graph
from inference.state import HistoryTurn, SinaState


class TestInput(TypedDict, total=False):
    question: str
    history: list[HistoryTurn]


# ─────────────────────────────────────────────────────────────────────────────
# EDIT THIS LIST — five inputs to exercise the graph.
# Each item must have a "question". Optionally add "history" to test the
# contextualize node (list of {"role": "user"|"assistant", "content": "..."}).
# ─────────────────────────────────────────────────────────────────────────────
TEST_INPUTS: list[TestInput] = [
    {"question": "REPLACE ME — input 1"},
    {"question": "REPLACE ME — input 2"},
    {"question": "REPLACE ME — input 3"},
    {"question": "REPLACE ME — input 4"},
    {"question": "REPLACE ME — input 5"},
]

OUTPUT_DIR = Path(__file__).parent / "eval_runs"


def _truncate(text: str, n: int = 400) -> str:
    text = text or ""
    return text if len(text) <= n else text[:n] + "…"


def _summarize_state(state: dict) -> dict:
    docs = state.get("retrieved_docs") or []
    web = state.get("search_results") or []
    return {
        "question_sent": state.get("question"),
        "original_question": state.get("original_question"),
        "route": state.get("route"),
        "rewritten_query": state.get("rewritten_query"),
        "poet_name": state.get("poet_name"),
        "poet_era": state.get("poet_era"),
        "poem_category": state.get("poem_category"),
        "refusal_reason": state.get("refusal_reason"),
        "retrieved_count": len(docs),
        "retrieved_meta": [d.metadata for d in docs[:3]],
        "search_count": len(web),
        "search_urls": [r.get("url") for r in web[:3]],
        "answer": state.get("answer"),
    }


def _print_case(idx: int, case: TestInput, summary: dict, took: float) -> None:
    print("=" * 78)
    print(f"CASE {idx} (took {took:.2f}s)")
    print("-" * 78)
    print(f"input:            {case['question']!r}")
    if case.get("history"):
        print(f"history_turns:    {len(case['history'])}")
    print(f"route:            {summary['route']}")
    print(f"rewritten_query:  {summary['rewritten_query']!r}")
    print(
        f"meta:             poet={summary['poet_name'] or '-'} "
        f"era={summary['poet_era'] or '-'} "
        f"category={summary['poem_category'] or '-'}"
    )
    print(f"retrieved_docs:   {summary['retrieved_count']}")
    print(f"search_results:   {summary['search_count']}")
    if summary["refusal_reason"]:
        print(f"refusal_reason:   {summary['refusal_reason']}")
    print("answer:")
    print(_truncate(summary["answer"] or "<empty>"))
    print()


async def _run_one(graph, case: TestInput) -> tuple[dict, float]:
    q = case["question"]
    initial: SinaState = {
        "question": q,
        "original_question": q,
        "history": case.get("history", []),
    }
    t0 = time.perf_counter()
    final = await graph.ainvoke(initial)
    return _summarize_state(final), time.perf_counter() - t0


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = build_graph()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = []

    for i, case in enumerate(TEST_INPUTS, start=1):
        try:
            summary, took = await _run_one(graph, case)
            _print_case(i, case, summary, took)
            results.append({
                "case": i,
                "input": case,
                "took_s": round(took, 2),
                "summary": summary,
            })
        except Exception as e:
            print("=" * 78)
            print(f"CASE {i} — FAILED: {e!r}")
            results.append({"case": i, "input": case, "error": repr(e)})

    out_file = OUTPUT_DIR / f"run_{run_id}.json"
    out_file.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("=" * 78)
    print(f"Saved: {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
