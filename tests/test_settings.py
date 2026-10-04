import pytest

from src.config.settings import Settings


@pytest.mark.parametrize("value", ["", " ", " , ,"])
def test_startup_fails_without_allowed_domains(monkeypatch, value):
    monkeypatch.setenv("SEARCH_ALLOWED_DOMAINS", value)
    with pytest.raises(ValueError, match="SEARCH_ALLOWED_DOMAINS"):
        Settings()


def test_allowed_domains_are_parsed(monkeypatch):
    monkeypatch.setenv("SEARCH_ALLOWED_DOMAINS", " who.int , cdc.gov,")
    assert Settings().SEARCH_ALLOWED_DOMAINS == ["who.int", "cdc.gov"]


def test_retrieval_settings_are_gone():
    keys = vars(Settings())
    for removed in (
        "PGVECTOR_CONNECTION",
        "PGVECTOR_COLLECTION",
        "HF_EMBEDDING_MODEL_NAME",
        "TOP_K_RETRIEVAL",
        "RETRIEVAL_SCORE_THRESHOLD",
        "SEARCH_MIN_TOP_SCORE",
    ):
        assert removed not in keys
