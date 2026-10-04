from src.config.settings import settings
from src.inference.nodes.search import search_node


async def test_tavily_always_called_with_whitelist(fakes):
    state = {"message": "m", "search_queries": ["q1", "q2", "q3"], "search_attempts": 0}
    await search_node(state)
    calls = fakes["search"].calls
    assert len(calls) == 3
    for call in calls:
        assert call["include_domains"] == settings.SEARCH_ALLOWED_DOMAINS
        assert call["include_domains"]  # never empty
        assert call["search_depth"] == "advanced"


async def test_queries_are_capped_per_turn(fakes, monkeypatch):
    monkeypatch.setattr(settings, "SEARCH_QUERIES_PER_TURN", 2)
    await search_node({"message": "m", "search_queries": ["a", "b", "c", "d"]})
    assert len(fakes["search"].calls) == 2


async def test_queries_are_scrubbed_before_tavily(fakes, caplog):
    query = "chest pain patient 1023456789 call 0551234567 john@example.com"
    with caplog.at_level("WARNING"):
        await search_node({"message": "m", "search_queries": [query]})
    sent = fakes["search"].calls[0]["query"]
    assert "1023456789" not in sent
    assert "0551234567" not in sent
    assert "john@example.com" not in sent
    assert "chest pain" in sent
    assert any("scrubbed 3 identifier" in r.message for r in caplog.records)
    # The identifiers themselves must not be logged.
    assert not any("1023456789" in r.message for r in caplog.records)


async def test_results_outside_whitelist_are_dropped(fakes):
    fakes["search"]._results_per_call = lambda n, q: [
        {"url": "https://pubmed.ncbi.nlm.nih.gov/1", "score": 0.9},
        {"url": "https://evil-ncbi.nlm.nih.gov.example.com/2", "score": 0.95},
        {"url": "https://randomblog.com/3", "score": 0.99},
    ]
    out = await search_node({"message": "m", "search_queries": ["q"]})
    assert [r["url"] for r in out["web_results"]] == ["https://pubmed.ncbi.nlm.nih.gov/1"]
    assert out["search_attempts"] == 1


async def test_refuses_to_search_without_whitelist(fakes, monkeypatch):
    monkeypatch.setattr(settings, "SEARCH_ALLOWED_DOMAINS", [])
    out = await search_node({"message": "m", "search_queries": ["q"], "search_attempts": 1})
    assert fakes["search"].calls == []
    assert out["search_attempts"] == 2
