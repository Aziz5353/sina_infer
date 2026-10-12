from typing import Literal

from langgraph.graph import END, START, StateGraph

from src.inference.nodes.answer import answer_node
from src.inference.nodes.plan import plan_node
from src.inference.nodes.retrieve import retrieve_node
from src.inference.state import SinaState


def _route_from_plan(state: SinaState):
    return "retrieve" if state["route"] == "answer" else END


def build_graph():
    builder = StateGraph(SinaState)

    builder.add_node("plan", plan_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("answer", answer_node)

    builder.add_edge(START, "plan")
    builder.add_conditional_edges("plan", _route_from_plan)
    builder.add_edge("retrieve", "answer")
    builder.add_edge("answer", END)

    return builder.compile()
