import logging
import time
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.config.constants import ASSESS_PROMPT
from src.config.settings import settings
from src.inference.context import render_case_context, render_list, render_web_results
from src.inference.pipeline_definition import pipeline
from src.inference.state import SinaState

logger = logging.getLogger(__name__)


class AssessOutput(BaseModel):
    sufficient: bool = Field(
        description="True if the web results support a differential and recommendations "
        "(or a direct answer for a clinical_question)."
    )
    gaps: list[str] = Field(default_factory=list, description="What the results are missing.")
    refined_queries: list[str] = Field(
        default_factory=list,
        description="New, more targeted de-identified English queries to fill the gaps.",
    )


async def assess_evidence_node(state: SinaState) -> dict:
    t0 = time.perf_counter()
    results = state.get("web_results") or []
    previous = state.get("search_queries") or []
    user_content = (
        f"{render_case_context(state)}\n\n"
        f"<previous_queries>\n{render_list(previous)}\n</previous_queries>\n\n"
        f"<web_results>\n{render_web_results(results)}\n</web_results>"
    )
    logger.debug(f"assess_evidence | user_content=\n{user_content}")
    llm = pipeline.assess_llm.with_structured_output(AssessOutput)
    result = cast(
        AssessOutput,
        await llm.ainvoke(
            [
                SystemMessage(
                    content=ASSESS_PROMPT.format(max_queries=settings.SEARCH_QUERIES_PER_TURN)
                ),
                HumanMessage(content=user_content),
            ]
        ),
    )

    sufficient = result.sufficient
    gaps = list(result.gaps)
    if len(results) < settings.SEARCH_MIN_RESULTS:
        sufficient = False
        if not gaps:
            gaps = ["too few relevant results from the configured sources"]
    # The graph routes on evidence_gaps, so an insufficient verdict must carry one.
    if not sufficient and not gaps:
        gaps = ["the retrieved content does not adequately cover this request"]

    seen = {q.strip().lower() for q in previous}
    refined = [
        q.strip() for q in result.refined_queries if q.strip() and q.strip().lower() not in seen
    ][: settings.SEARCH_QUERIES_PER_TURN]

    took = time.perf_counter() - t0
    logger.info(
        f"assess_evidence | attempts={state.get('search_attempts', 0)} results={len(results)} "
        f"sufficient={sufficient} llm_sufficient={result.sufficient} gaps={len(gaps)} "
        f"refined_queries={len(refined)} took={took:.2f}s"
    )
    logger.debug(f"assess_evidence | gaps={gaps} refined_queries={refined}")

    update: dict = {"evidence_gaps": [] if sufficient else gaps}
    if sufficient:
        return update
    if refined and state.get("search_attempts", 0) < settings.MAX_SEARCH_ATTEMPTS:
        update["search_queries"] = refined
    else:
        update["clarify_reason"] = "evidence_gap"
    return update
