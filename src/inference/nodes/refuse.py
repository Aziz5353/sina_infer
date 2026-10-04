import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from src.config.constants import REFUSAL_PROMPT
from src.inference.pipeline_definition import pipeline
from src.inference.state import SinaState

logger = logging.getLogger(__name__)


async def refuse_node(state: SinaState) -> dict:
    t0 = time.perf_counter()
    reason = state.get("refusal_reason") or "out_of_scope"
    logger.info(f"refuse | reason={reason}")
    response = await pipeline.refuse_llm.ainvoke(
        [
            SystemMessage(content=REFUSAL_PROMPT),
            HumanMessage(content=f"reason: {reason}\nquestion: {state['question']}"),
        ]
    )
    took = time.perf_counter() - t0
    logger.info(
        f"refuse | answer_chars={len(response.content)} took={took:.2f}s"
    )
    return {"answer": response.content}
