import logging
import time
from typing import Literal, cast

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.config.constants import ANALYZER_PROMPT
from src.config.settings import settings
from src.inference.pipeline_definition import pipeline
from src.inference.state import SinaState

logger = logging.getLogger(__name__)


class Case(BaseModel):
    """Patient details exactly as stated by the doctor. Unknown → null / empty."""

    age: str | None = Field(default=None, description="Age as stated, e.g. '45' or '3 months'.")
    sex: str | None = Field(default=None, description="Sex as stated, e.g. 'male', 'female'.")
    pregnancy_status: str | None = Field(
        default=None, description="e.g. 'pregnant, 32 weeks', 'not pregnant'; null if not stated."
    )
    chief_complaint: str | None = None
    symptoms: list[str] = Field(default_factory=list)
    duration: str | None = Field(default=None, description="Duration of the main complaint.")
    vitals: str | None = Field(default=None, description="Vitals as stated, e.g. 'BP 150/95, HR 110'.")
    exam_findings: list[str] = Field(default_factory=list)
    labs_imaging: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    comorbidities: list[str] = Field(default_factory=list)


class AnalyzerOutput(BaseModel):
    route: Literal["search", "clarify", "refuse"] = Field(
        description="Which downstream branch should run for this message."
    )
    query_type: Literal["patient_case", "clinical_question"] = Field(
        description="Specific patient assessment vs general clinical question."
    )
    case: Case | None = Field(
        default=None,
        description="Extracted patient details for a patient_case; null otherwise. Never invent values.",
    )
    missing_critical_info: list[str] = Field(
        default_factory=list,
        description="Missing items that would materially change the differential or management.",
    )
    red_flags: list[str] = Field(
        default_factory=list,
        description="Stated findings that need urgent action now.",
    )
    search_queries: list[str] = Field(
        default_factory=list,
        description="1..N de-identified English search queries when route='search'; empty otherwise.",
    )
    refusal_reason: str | None = Field(
        default=None,
        description="Short reason when route='refuse'; otherwise null.",
    )


def _filled_fields(case: dict) -> int:
    return sum(1 for value in case.values() if value)


async def analyzer_node(state: SinaState) -> dict:
    t0 = time.perf_counter()
    message = state.get("standalone_message") or state["message"]
    logger.debug(f"analyzer | message={message!r}")
    llm = pipeline.analyzer_llm.with_structured_output(AnalyzerOutput)
    result = cast(
        AnalyzerOutput,
        await llm.ainvoke(
            [
                SystemMessage(
                    content=ANALYZER_PROMPT.format(max_queries=settings.SEARCH_QUERIES_PER_TURN)
                ),
                HumanMessage(content=message),
            ]
        ),
    )

    route = result.route
    # A general clinical question never needs patient details.
    if route == "clarify" and result.query_type == "clinical_question":
        route = "search"
    # Clarifying needs something to ask about; without it, search and state assumptions.
    if route == "clarify" and not result.missing_critical_info:
        route = "search"

    queries = [q.strip() for q in result.search_queries if q.strip()]
    queries = queries[: settings.SEARCH_QUERIES_PER_TURN]
    if route == "search" and not queries:
        queries = [message]

    case = result.case.model_dump() if result.case else {}
    took = time.perf_counter() - t0
    logger.info(
        f"analyzer | route={route} query_type={result.query_type} "
        f"case_fields={_filled_fields(case)} missing={len(result.missing_critical_info)} "
        f"red_flags={len(result.red_flags)} queries={len(queries) if route == 'search' else 0} "
        f"took={took:.2f}s"
    )
    logger.debug(
        f"analyzer | llm_route={result.route} case={case} "
        f"missing={result.missing_critical_info} red_flags={result.red_flags} "
        f"queries={queries} refusal={result.refusal_reason!r}"
    )
    update: dict = {
        "route": route,
        "query_type": result.query_type,
        "case": case,
        "missing_critical_info": result.missing_critical_info,
        "red_flags": result.red_flags,
        "search_queries": queries if route == "search" else [],
        "refusal_reason": result.refusal_reason,
    }
    if route == "clarify":
        update["clarify_reason"] = "case_gap"
    return update
