import logging
import re
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer

from src.config.constants import (
    ANSWER_PROMPT,
    ANSWER_SECTIONS,
    CLOSING_LINE,
    HEADINGS,
    LANGUAGE_NAMES,
    NO_RESULTS_REPLY,
    RED_FLAGS_SECTION,
)
from src.inference.pipeline_definition import pipeline
from src.inference.state import SinaState

logger = logging.getLogger(__name__)

_CITATION = re.compile(r"\[(\d{1,3})\]")


def answer_layout(state: SinaState) -> list[tuple[str, str]]:
    """Pick the answer sections for this turn in code, so the model never has to
    decide which sections to skip (smaller models tend to print empty ones)."""
    task = state["task"]
    key = f"consult_{state['query_type']}" if task == "consult" else task
    return [*([RED_FLAGS_SECTION] if state["red_flags"] else []), *ANSWER_SECTIONS[key]]


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "(none)"


def render_context(state: SinaState) -> str:
    case = "\n".join(
        f"- {key}: {', '.join(value) if isinstance(value, list) else value}"
        for key, value in state["case"].items()
        if value
    )
    sources = "\n\n".join(
        f"[{i}] {r.get('title', '')}\nURL: {r.get('url', '')}\n{r.get('content', '')}"
        for i, r in enumerate(state["web_results"], start=1)
    )
    return (
        f"<request>\n{state['standalone_message']}\n</request>\n\n"
        f"<case>\n{case or '(none)'}\n</case>\n\n"
        f"<red_flags>\n{_bullets(state['red_flags'])}\n</red_flags>\n\n"
        f"<missing_information>\n{_bullets(state['missing_critical_info'])}\n</missing_information>\n\n"
        f"<sources>\n{sources}\n</sources>"
    )


def render_sources(results: list[dict], answer: str, language: str) -> str:
    """Sources list built from the citations actually used in the answer."""
    cited = sorted({int(n) for n in _CITATION.findall(answer) if 1 <= int(n) <= len(results)})
    lines = [f"\n\n## {HEADINGS[language]['sources']}"] if cited else []
    lines += [f"[{n}] {results[n - 1].get('title', '').strip()} — {results[n - 1].get('url', '')}  " for n in cited]
    lines.append(f"\n{CLOSING_LINE[language]}")
    return "\n".join(lines)


async def answer_node(state: SinaState) -> dict:
    t0 = time.perf_counter()
    write = get_stream_writer()
    language = state["language"]
    web = state["web_results"]

    if not web:
        reply = NO_RESULTS_REPLY[language]
        write({"content": reply})
        logger.info("answer | no sources, skipped the model")
        return {"answer": reply}

    layout = answer_layout(state)
    headings = HEADINGS[language]
    system = ANSWER_PROMPT.format(
        language=LANGUAGE_NAMES[language],
        sections="\n".join(f"## {headings[key]}\n{instruction}\n" for key, instruction in layout),
    )
    user_content = render_context(state)
    logger.debug(f"answer | system=\n{system}")
    logger.debug(f"answer | user_content=\n{user_content}")

    parts: list[str] = []
    async for chunk in pipeline.answer_llm.astream(
        [SystemMessage(content=system), HumanMessage(content=user_content)]
    ):
        if isinstance(chunk.content, str) and chunk.content:
            parts.append(chunk.content)
            write({"content": chunk.content})
    sources = render_sources(web, "".join(parts), language)
    write({"content": sources})

    answer = "".join(parts) + sources
    took = time.perf_counter() - t0
    logger.info(
        f"answer | query_type={state['query_type']} task={state['task']} "
        f"language={language} sections={len(layout)} sources={len(web)} "
        f"context_chars={len(user_content)} answer_chars={len(answer)} took={took:.2f}s"
    )
    logger.debug(f"answer | answer=\n{answer}")
    return {"answer": answer}
