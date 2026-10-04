import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from src.config.constants import GENERATE_PROMPT
from src.inference.context import render_case_context, render_web_results
from src.inference.pipeline_definition import pipeline
from src.inference.state import SinaState

logger = logging.getLogger(__name__)


async def generate_node(state: SinaState) -> dict:
    t0 = time.perf_counter()
    web = state.get("web_results") or []
    user_content = (
        f"{render_case_context(state)}\n\n"
        f"<web_results>\n{render_web_results(web)}\n</web_results>"
    )
    logger.debug(f"generate | user_content=\n{user_content}")
    response = await pipeline.generate_llm.ainvoke(
        [
            SystemMessage(content=GENERATE_PROMPT),
            HumanMessage(content=user_content),
        ]
    )
    took = time.perf_counter() - t0
    logger.info(
        f"generate | query_type={state.get('query_type')} web={len(web)} "
        f"red_flags={len(state.get('red_flags') or [])} context_chars={len(user_content)} "
        f"answer_chars={len(response.content)} took={took:.2f}s"
    )
    logger.debug(f"generate | answer=\n{response.content}")
    return {"answer": response.content}
