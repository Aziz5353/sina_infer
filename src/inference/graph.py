from typing import Literal

from langgraph.graph import END, START, StateGraph

from src.inference.nodes.analyzer import analyzer_node
from src.inference.nodes.contextualize import contextualize_node
from src.inference.nodes.generate import generate_node
from src.inference.nodes.refuse import refuse_node
from src.inference.nodes.retrieve import retrieve_node
from src.inference.nodes.search import search_node
from src.inference.state import SinaState


def _route_from_analyzer(state: SinaState) -> Literal["retrieve", "search", "generate", "refuse"]:
    return state.get("route", "generate")


def _route_from_retrieve(state: SinaState) -> Literal["search", "generate"]:
    docs = state.get("retrieved_docs") or []
    return "generate" if docs else "search"


def build_graph():
    builder = StateGraph(SinaState)

    builder.add_node("contextualize", contextualize_node)
    builder.add_node("analyzer", analyzer_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("search", search_node)
    builder.add_node("generate", generate_node)
    builder.add_node("refuse", refuse_node)

    builder.add_edge(START, "contextualize")
    builder.add_edge("contextualize", "analyzer")
    builder.add_conditional_edges(
        "analyzer",
        _route_from_analyzer,
        {
            "retrieve": "retrieve",
            "search": "search",
            "generate": "generate",
            "refuse": "refuse",
        },
    )
    builder.add_conditional_edges(
        "retrieve",
        _route_from_retrieve,
        {"search": "search", "generate": "generate"},
    )
    builder.add_edge("search", "generate")
    builder.add_edge("generate", END)
    builder.add_edge("refuse", END)

    return builder.compile()
