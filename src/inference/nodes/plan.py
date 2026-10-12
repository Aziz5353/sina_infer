import logging
import re
import time
from typing import Literal, cast

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field

from src.config.constants import CLARIFY_FALLBACK_INTRO, PLAN_PROMPT, REFUSE_FALLBACK_REPLY
from src.config.settings import settings
from src.inference.pipeline_definition import pipeline
from src.inference.state import Language, QueryType, Route, SinaState, Task

logger = logging.getLogger(__name__)

_ARABIC = re.compile(r"[؀-ۿݐ-ݿ]")
# Arabic, Cyrillic and CJK scripts. Sources are English, so a query in another
# script retrieves nothing useful (or off-topic pages in that language).
_NON_ENGLISH_SCRIPT = re.compile(
    r"[Ѐ-ӿ؀-ۿݐ-ݿ぀-ヿ㐀-鿿가-힯]"
)


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


class PlanOutput(BaseModel):
    standalone_question: str = Field(description="The request rewritten to stand alone.")
    route: Route = Field(description="answer, clarify or refuse.")
    query_type: QueryType
    task: Task = Field(default="consult")
    case: Case | None = Field(default=None, description="patient_case only; null otherwise.")
    missing_critical_info: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    queries: list[str] = Field(default_factory=list, description="English search queries; guideline first.")
    reply: str | None = Field(default=None, description="Message to the doctor for clarify / refuse.")


def detect_language(text: str) -> Language:
    return "ar" if _ARABIC.search(text) else "en"


def _render_history(history: list[dict], max_turns: int) -> str:
    lines = []
    for turn in history[-max_turns:]:
        speaker = "Doctor" if turn["role"] == "user" else "Assistant"
        lines.append(f"{speaker}: {turn['content']}")
    return "\n".join(lines) or "(empty)"


def _clean_queries(queries: list[str]) -> list[str]:
    queries = [q.strip() for q in queries if q.strip()]
    english = [q for q in queries if not _NON_ENGLISH_SCRIPT.search(q)]
    if len(english) != len(queries):
        logger.warning(f"plan | dropped {len(queries) - len(english)} non-English query(ies)")
    return english[: settings.SEARCH_QUERIES_PER_TURN]


def resolve_route(result: PlanOutput) -> Route:
    """Code-side guards on the model's route."""
    route = result.route
    # Clarifying is only for a consult about a specific patient with something to ask;
    # documents, explanations, calculations and teaching state assumptions instead.
    if route == "clarify" and (
        result.task != "consult"
        or result.query_type != "patient_case"
        or not result.missing_critical_info
    ):
        route = "answer"
    return route


def fallback_reply(route: Route, result: PlanOutput, language: Language) -> str:
    if route == "refuse":
        return REFUSE_FALLBACK_REPLY[language]
    items = result.missing_critical_info[: settings.MAX_CLARIFYING_QUESTIONS]
    return CLARIFY_FALLBACK_INTRO[language] + "\n" + "\n".join(
        f"{i}. {item}" for i, item in enumerate(items, start=1)
    )


async def plan_node(state: SinaState) -> dict:
    t0 = time.perf_counter()
    message = state["message"]
    history = state.get("history") or []
    language = detect_language(message)
    user_content = (
        f"<history>\n{_render_history(history, settings.HISTORY_TURNS)}\n</history>\n\n"
        f"<message>\n{message}\n</message>"
    )
    logger.debug(f"plan | user_content=\n{user_content}")
    llm = pipeline.plan_llm.with_structured_output(PlanOutput)
    result = cast(
        PlanOutput,
        await llm.ainvoke(
            [
                SystemMessage(
                    content=PLAN_PROMPT.format(
                        max_queries=settings.SEARCH_QUERIES_PER_TURN,
                        max_questions=settings.MAX_CLARIFYING_QUESTIONS,
                    )
                ),
                HumanMessage(content=user_content),
            ]
        ),
    )

    route = resolve_route(result)
    standalone = result.standalone_question.strip() or message
    queries = _clean_queries(result.queries)
    if route == "answer" and not queries:
        # A clarify overridden by resolve_route comes without queries, or every
        # query came back in another script.
        queries = [standalone]

    case = result.case.model_dump() if result.case else {}

    update: dict = {
        "language": language,
        "standalone_message": standalone,
        "route": route,
        "query_type": result.query_type,
        "task": result.task,
        "case": case,
        "missing_critical_info": result.missing_critical_info,
        "red_flags": result.red_flags,
        "search_queries": queries if route == "answer" else [],
    }
    if route != "answer":
        reply = (result.reply or "").strip() or fallback_reply(route, result, language)
        get_stream_writer()({"content": reply})
        update["answer"] = reply

    took = time.perf_counter() - t0
    logger.info(
        f"plan | route={route} llm_route={result.route} query_type={result.query_type} "
        f"task={result.task} language={language} history_turns={len(history)} "
        f"case_fields={sum(1 for v in case.values() if v)} "
        f"missing={len(result.missing_critical_info)} red_flags={len(result.red_flags)} "
        f"queries={len(update['search_queries'])} took={took:.2f}s"
    )
    logger.debug(
        f"plan | standalone={standalone!r} case={case} missing={result.missing_critical_info} "
        f"red_flags={result.red_flags} queries={queries}"
    )
    return update
