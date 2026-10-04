from typing import Literal, NotRequired, TypedDict


Route = Literal["search", "clarify", "refuse"]
QueryType = Literal["patient_case", "clinical_question"]
ClarifyReason = Literal["case_gap", "evidence_gap"]


class HistoryTurn(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class SinaState(TypedDict):
    message: str
    history: NotRequired[list[HistoryTurn]]
    standalone_message: NotRequired[str]
    route: NotRequired[Route]
    query_type: NotRequired[QueryType]
    case: NotRequired[dict]
    missing_critical_info: NotRequired[list[str]]
    red_flags: NotRequired[list[str]]
    search_queries: NotRequired[list[str]]
    web_results: NotRequired[list[dict]]
    search_attempts: NotRequired[int]
    evidence_gaps: NotRequired[list[str]]
    clarify_reason: NotRequired[ClarifyReason]
    refusal_reason: NotRequired[str | None]
    answer: NotRequired[str]
