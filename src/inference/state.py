from typing import Literal, NotRequired, TypedDict


Route = Literal["answer", "clarify", "refuse"]
QueryType = Literal["patient_case", "clinical_question"]
Task = Literal["consult", "calculation", "documentation", "patient_education", "teaching"]
Language = Literal["ar", "en"]


class HistoryTurn(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class SinaState(TypedDict):
    message: str
    history: NotRequired[list[HistoryTurn]]
    language: NotRequired[Language]
    standalone_message: NotRequired[str]
    route: NotRequired[Route]
    query_type: NotRequired[QueryType]
    task: NotRequired[Task]
    case: NotRequired[dict]
    missing_critical_info: NotRequired[list[str]]
    red_flags: NotRequired[list[str]]
    search_queries: NotRequired[list[str]]
    web_results: NotRequired[list[dict]]
    answer: NotRequired[str]
