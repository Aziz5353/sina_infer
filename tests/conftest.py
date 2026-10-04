import itertools
import os

# Settings are read at import time; set dummy values before anything imports src.
# load_dotenv() does not override variables that are already set, so a local .env
# cannot leak into the tests.
_TEST_ENV = {
    "OPENAI_API_KEY": "test-key",
    "OPENAI_BASE_URL": "http://localhost:9/v1",
    "ANALYZER_MODEL": "test-model",
    "CONTEXTUALIZE_MODEL": "test-model",
    "ASSESS_MODEL": "test-model",
    "GENERATE_MODEL": "test-model",
    "CLARIFY_MODEL": "test-model",
    "REFUSE_MODEL": "test-model",
    "TAVILY_API_KEY": "test-key",
    "SEARCH_ALLOWED_DOMAINS": "ncbi.nlm.nih.gov,who.int",
    "SEARCH_MAX_RESULTS": "5",
    "SEARCH_MIN_RESULTS": "2",
    "SEARCH_QUERIES_PER_TURN": "3",
    "MAX_SEARCH_ATTEMPTS": "2",
    "MAX_CLARIFYING_QUESTIONS": "4",
    "LOG_TO_FILE": "false",
}
os.environ.update(_TEST_ENV)

import pytest  # noqa: E402
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402

from src.inference.pipeline_definition import pipeline  # noqa: E402


class FakeStructuredLLM:
    """Stands in for ChatOpenAI; with_structured_output() returns queued results in order."""

    def __init__(self, *results):
        self._results = list(results)
        self.calls: list = []

    def queue(self, *results):
        self._results.extend(results)

    def with_structured_output(self, _schema):
        return self

    async def ainvoke(self, messages):
        self.calls.append(messages)
        if not self._results:
            raise AssertionError("FakeStructuredLLM called more times than results queued")
        result = self._results.pop(0) if len(self._results) > 1 else self._results[0]
        return result


class FakeSearch:
    """Stands in for TavilySearch; records every invocation."""

    def __init__(self, results_per_call=None):
        self.calls: list[dict] = []
        self._results_per_call = results_per_call or (lambda call_no, query: [])

    async def ainvoke(self, args):
        self.calls.append(args)
        return {"results": self._results_per_call(len(self.calls), args["query"])}


def fake_chat(text: str) -> GenericFakeChatModel:
    return GenericFakeChatModel(messages=itertools.cycle([AIMessage(content=text)]))


@pytest.fixture
def fakes(monkeypatch):
    analyzer = FakeStructuredLLM()
    assess = FakeStructuredLLM()
    search = FakeSearch()
    monkeypatch.setattr(pipeline, "analyzer_llm", analyzer, raising=False)
    monkeypatch.setattr(pipeline, "assess_llm", assess, raising=False)
    monkeypatch.setattr(pipeline, "contextualize_llm", fake_chat("STANDALONE"), raising=False)
    monkeypatch.setattr(pipeline, "generate_llm", fake_chat("GENERATE_ANSWER"), raising=False)
    monkeypatch.setattr(pipeline, "clarify_llm", fake_chat("CLARIFY_ANSWER"), raising=False)
    monkeypatch.setattr(pipeline, "refuse_llm", fake_chat("REFUSE_ANSWER"), raising=False)
    monkeypatch.setattr(pipeline, "search", search, raising=False)
    return {"analyzer": analyzer, "assess": assess, "search": search}
