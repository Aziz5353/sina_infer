import pytest

from src.config.settings import settings
from src.inference.graph import build_graph
from src.inference.nodes.analyzer import AnalyzerOutput, Case
from src.inference.nodes.assess_evidence import AssessOutput
from src.inference.state import SinaState
from src.inference.stream import run_model_stream

CHEST_PAIN = "45M, 2h crushing chest pain radiating to left arm, diaphoretic, BP 150/95"


def _result(url: str, score: float = 0.9) -> dict:
    return {"url": url, "title": "t", "content": "c", "score": score}


def _search_ok(call_no: int, query: str) -> list[dict]:
    return [
        _result(f"https://www.ncbi.nlm.nih.gov/a{call_no}", 0.9),
        _result(f"https://www.who.int/b{call_no}", 0.8),
    ]


async def _run(message: str = CHEST_PAIN, history=None) -> dict:
    graph = build_graph()
    return await graph.ainvoke(SinaState(message=message, history=history or []))


# --- analyzer routing ---------------------------------------------------------


async def test_refuse_route_ends_in_refuse(fakes):
    fakes["analyzer"].queue(
        AnalyzerOutput(route="refuse", query_type="clinical_question", refusal_reason="non-medical")
    )
    state = await _run("write me a poem")
    assert state["answer"] == "REFUSE_ANSWER"
    assert fakes["search"].calls == []


async def test_clarify_route_ends_in_clarify_with_case_gap(fakes):
    fakes["analyzer"].queue(
        AnalyzerOutput(
            route="clarify",
            query_type="patient_case",
            case=Case(symptoms=["cough"]),
            missing_critical_info=["age", "duration"],
        )
    )
    state = await _run("patient has a cough")
    assert state["answer"] == "CLARIFY_ANSWER"
    assert state["clarify_reason"] == "case_gap"
    assert fakes["search"].calls == []


async def test_search_route_with_sufficient_evidence_generates(fakes):
    fakes["search"]._results_per_call = _search_ok
    fakes["analyzer"].queue(
        AnalyzerOutput(
            route="search",
            query_type="patient_case",
            case=Case(age="45", sex="male", chief_complaint="chest pain"),
            red_flags=["possible ACS"],
            search_queries=["acute chest pain ACS initial management"],
        )
    )
    fakes["assess"].queue(AssessOutput(sufficient=True))
    state = await _run()
    assert state["answer"] == "GENERATE_ANSWER"
    assert state["search_attempts"] == 1
    assert len(fakes["search"].calls) == 1


async def test_clinical_question_is_never_clarified(fakes):
    fakes["search"]._results_per_call = _search_ok
    fakes["analyzer"].queue(
        AnalyzerOutput(
            route="clarify",
            query_type="clinical_question",
            missing_critical_info=["age"],
            search_queries=["amoxicillin dosing community acquired pneumonia"],
        )
    )
    fakes["assess"].queue(AssessOutput(sufficient=True))
    state = await _run("amoxicillin dose for CAP?")
    assert state["route"] == "search"
    assert state["answer"] == "GENERATE_ANSWER"


# --- assess → search loop -----------------------------------------------------


@pytest.mark.parametrize("max_attempts", [1, 2, 3])
async def test_retry_loop_stops_at_max_attempts_then_clarifies(fakes, monkeypatch, max_attempts):
    monkeypatch.setattr(settings, "MAX_SEARCH_ATTEMPTS", max_attempts)
    fakes["search"]._results_per_call = _search_ok
    fakes["analyzer"].queue(
        AnalyzerOutput(route="search", query_type="patient_case", search_queries=["q0"])
    )
    # Always insufficient, always offers a fresh refined query.
    fakes["assess"].queue(
        *[
            AssessOutput(sufficient=False, gaps=["no management"], refined_queries=[f"q{i}"])
            for i in range(1, 10)
        ]
    )
    state = await _run()
    assert state["search_attempts"] == max_attempts
    assert len(fakes["search"].calls) == max_attempts
    assert state["clarify_reason"] == "evidence_gap"
    assert state["evidence_gaps"] == ["no management"]
    assert state["answer"] == "CLARIFY_ANSWER"


async def test_no_refined_queries_goes_straight_to_clarify(fakes):
    fakes["search"]._results_per_call = _search_ok
    fakes["analyzer"].queue(
        AnalyzerOutput(route="search", query_type="patient_case", search_queries=["q0"])
    )
    fakes["assess"].queue(AssessOutput(sufficient=False, gaps=["gap"], refined_queries=[]))
    state = await _run()
    assert state["search_attempts"] == 1
    assert state["answer"] == "CLARIFY_ANSWER"


async def test_too_few_results_is_insufficient_even_if_llm_says_sufficient(fakes, monkeypatch):
    monkeypatch.setattr(settings, "MAX_SEARCH_ATTEMPTS", 1)
    fakes["search"]._results_per_call = lambda n, q: [_result("https://who.int/only")]
    fakes["analyzer"].queue(
        AnalyzerOutput(route="search", query_type="clinical_question", search_queries=["q0"])
    )
    fakes["assess"].queue(AssessOutput(sufficient=True))
    state = await _run("q")
    assert state["clarify_reason"] == "evidence_gap"
    assert state["answer"] == "CLARIFY_ANSWER"


async def test_retry_accumulates_and_dedupes_results(fakes):
    def results(call_no, query):
        return [
            _result("https://www.ncbi.nlm.nih.gov/shared", 0.5 + call_no / 10),
            _result(f"https://www.who.int/only{call_no}", 0.4),
        ]

    fakes["search"]._results_per_call = results
    fakes["analyzer"].queue(
        AnalyzerOutput(route="search", query_type="patient_case", search_queries=["q0"])
    )
    fakes["assess"].queue(
        AssessOutput(sufficient=False, gaps=["g"], refined_queries=["q1"]),
        AssessOutput(sufficient=True),
    )
    state = await _run()
    urls = [r["url"] for r in state["web_results"]]
    assert len(urls) == len(set(urls)) == 3
    assert state["web_results"][0]["url"].endswith("/shared")
    assert state["web_results"][0]["score"] == pytest.approx(0.7)
    assert state["answer"] == "GENERATE_ANSWER"


# --- streaming ----------------------------------------------------------------


async def test_only_answer_nodes_stream(fakes):
    fakes["search"]._results_per_call = _search_ok
    fakes["analyzer"].queue(
        AnalyzerOutput(route="search", query_type="patient_case", search_queries=["q0"])
    )
    fakes["assess"].queue(AssessOutput(sufficient=True))
    chunks = [
        c
        async for c in run_model_stream(
            build_graph(),
            SinaState(message=CHEST_PAIN, history=[{"role": "user", "content": "hi"}]),
        )
    ]
    body = "".join(chunks)
    assert "GENERATE" in body
    assert "STANDALONE" not in body  # contextualize must not leak
    assert chunks[-1] == "data: [DONE]\n\n"
