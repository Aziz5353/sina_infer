import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from src.config.constants import CONTEXTUALIZE_PROMPT
from src.config.settings import settings
from src.inference.pipeline_definition import pipeline
from src.inference.state import SinaState

logger = logging.getLogger(__name__)


def _render_history(history: list[dict], max_turns: int) -> str:
    recent = history[-max_turns:]
    lines = []
    for turn in recent:
        speaker = "المستخدم" if turn.get("role") == "user" else "المساعد"
        lines.append(f"{speaker}: {turn.get('content', '')}")
    return "\n".join(lines)


async def contextualize_node(state: SinaState) -> dict:
    question = state["question"]
    history = state.get("history") or []

    if not history:
        logger.debug("contextualize | skipped (no history)")
        return {}

    t0 = time.perf_counter()
    rendered_history = _render_history(history, settings.CONTEXTUALIZE_HISTORY_TURNS)
    user_content = (
        f"<history>\n{rendered_history}\n</history>\n\n"
        f"<question>\n{question}\n</question>"
    )
    response = await pipeline.contextualize_llm.ainvoke(
        [
            SystemMessage(content=CONTEXTUALIZE_PROMPT),
            HumanMessage(content=user_content),
        ]
    )
    standalone = (response.content or "").strip() or question
    took = time.perf_counter() - t0
    logger.info(
        f"contextualize | turns={len(history)} "
        f"original={question!r} standalone={standalone!r} took={took:.2f}s"
    )
    return {"question": standalone}
