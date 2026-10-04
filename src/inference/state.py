from typing import Literal, NotRequired, TypedDict

from langchain_core.documents import Document


Route = Literal["retrieve", "search", "generate", "refuse"]


class HistoryTurn(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class SinaState(TypedDict):
    question: str
    original_question: str
    history: NotRequired[list[HistoryTurn]]
    route: NotRequired[Route]
    rewritten_query: NotRequired[str | None]
    poet_name: NotRequired[str | None]
    poet_era: NotRequired[str | None]
    poem_category: NotRequired[list[str] | None]
    poem_meter: NotRequired[str | None]
    poem_rhyme: NotRequired[str | None]
    retrieved_docs: NotRequired[list[Document]]
    search_results: NotRequired[list[dict]]
    refusal_reason: NotRequired[str | None]
    answer: NotRequired[str]
