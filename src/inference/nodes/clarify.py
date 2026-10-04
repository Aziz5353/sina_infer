import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from src.config.constants import CLARIFY_PROMPT
from src.config.settings import settings
from src.inference.context import render_case_context, render_list
from src.inference.pipeline_definition import pipeline
from src.inference.state import SinaState

logger = logging.getLogger(__name__)


async def clarify_node(state: SinaState) -> dict:
    t0 = time.perf_counter()
    reason = state.get("clarify_reason") or "case_gap"
    user_content = (
        f"clarify_reason: {reason}\n\n"
        f"{render_case_context(state)}\n\n"
        f"<evidence_gaps>\n{render_list(state.get('evidence_gaps'))}\n</evidence_gaps>"
    )
    logger.debug(f"clarify | user_content=\n{user_content}")
    response = await pipeline.clarify_llm.ainvoke(
        [
            SystemMessage(
                content=CLARIFY_PROMPT.format(max_questions=settings.MAX_CLARIFYING_QUESTIONS)
            ),
            HumanMessage(content=user_content),
        ]
    )
    took = time.perf_counter() - t0
    logger.info(
        f"clarify | reason={reason} missing={len(state.get('missing_critical_info') or [])} "
        f"gaps={len(state.get('evidence_gaps') or [])} "
        f"red_flags={len(state.get('red_flags') or [])} "
        f"answer_chars={len(response.content)} took={took:.2f}s"
    )
    logger.debug(f"clarify | answer=\n{response.content}")
    return {"answer": response.content}
