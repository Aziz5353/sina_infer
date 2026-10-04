from typing import Literal

from langgraph.graph import END, START, StateGraph

from src.inference.nodes.analyzer import analyzer_node
from src.inference.nodes.assess_evidence import assess_evidence_node
from src.inference.nodes.clarify import clarify_node
from src.inference.nodes.contextualize import contextualize_node
from src.inference.nodes.generate import generate_node
from src.inference.nodes.refuse import refuse_node
from src.inference.nodes.search import search_node
from src.inference.state import SinaState


def _route_from_analyzer(state: SinaState) -> Literal["search", "clarify", "refuse"]:
    return state.get("route", "search")


def _route_from_assess(state: SinaState) -> Literal["generate", "search", "clarify"]:
    # assess_evidence leaves evidence_gaps empty when the evidence is sufficient,
    # and sets clarify_reason="evidence_gap" once retrying is no longer possible.
    if not state.get("evidence_gaps"):
        return "generate"
    if state.get("clarify_reason") == "evidence_gap":
        return "clarify"
    return "search"


def build_graph():
    builder = StateGraph(SinaState)

    builder.add_node("contextualize", contextualize_node)
    builder.add_node("analyzer", analyzer_node)
    builder.add_node("search", search_node)
    builder.add_node("assess_evidence", assess_evidence_node)
    builder.add_node("generate", generate_node)
    builder.add_node("clarify", clarify_node)
    builder.add_node("refuse", refuse_node)

    builder.add_edge(START, "contextualize")
    builder.add_edge("contextualize", "analyzer")
    builder.add_conditional_edges(
        "analyzer",
        _route_from_analyzer,
        {"search": "search", "clarify": "clarify", "refuse": "refuse"},
    )
    builder.add_edge("search", "assess_evidence")
    builder.add_conditional_edges(
        "assess_evidence",
        _route_from_assess,
        {"generate": "generate", "search": "search", "clarify": "clarify"},
    )
    builder.add_edge("generate", END)
    builder.add_edge("clarify", END)
    builder.add_edge("refuse", END)

    return builder.compile()
