import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from config.constants import GENERATE_PROMPT
from inference.pipeline_definition import pipeline
from inference.state import SinaState

logger = logging.getLogger(__name__)


def _build_context(state: SinaState) -> str:
    parts: list[str] = []

    docs = state.get("retrieved_docs") or []
    if docs:
        rendered = "\n\n".join(
            f"[{i + 1}]\n"
            f"{d.metadata.get('original_text') or d.page_content}\n"
            f"poet_name: {d.metadata.get('poet_name', '')}\n"
            f"poem_title: {d.metadata.get('poem_title', '')}\n"
            f"poem_page_url: {d.metadata.get('poem_page_url', '')}"
            for i, d in enumerate(docs)
        )
        parts.append(f"<retrieved_poems>\n{rendered}\n</retrieved_poems>")

    web = state.get("search_results") or []
    if web:
        rendered = "\n\n".join(
            f"[{i + 1}]\n{r.get('title', '')}\n{r.get('content', '')}\n({r.get('url', '')})"
            for i, r in enumerate(web)
        )
        parts.append(f"<web_results>\n{rendered}\n</web_results>")

    return "\n\n".join(parts)


async def generate_node(state: SinaState) -> dict:
    t0 = time.perf_counter()
    context = _build_context(state)
    user_content = (
        f"{context}\n\nالسؤال: {state['question']}" if context else state["question"]
    )
    docs = state.get("retrieved_docs") or []
    web = state.get("search_results") or []
    logger.info(
        f"generate | docs={len(docs)} web={len(web)} "
        f"context_chars={len(context)}"
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
        f"generate | answer_chars={len(response.content)} took={took:.2f}s"
    )
    logger.debug(f"generate | answer=\n{response.content}")
    return {"answer": response.content}
