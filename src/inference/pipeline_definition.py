import logging

from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch

from src.config.settings import settings

logger = logging.getLogger(__name__)


class PipelineDefinition:
    analyzer_llm: ChatOpenAI
    contextualize_llm: ChatOpenAI
    assess_llm: ChatOpenAI
    generate_llm: ChatOpenAI
    clarify_llm: ChatOpenAI
    refuse_llm: ChatOpenAI
    search: TavilySearch

    def __init__(self) -> None:
        self._initialized = False

    def init(self) -> None:
        if self._initialized:
            return

        self.analyzer_llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.ANALYZER_MODEL,
        )
        self.contextualize_llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.CONTEXTUALIZE_MODEL,
            temperature=0,
        )
        self.assess_llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.ASSESS_MODEL,
        )
        self.generate_llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.GENERATE_MODEL,
            temperature=settings.GENERATE_TEMPERATURE,
            streaming=True,
        )
        self.clarify_llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.CLARIFY_MODEL,
            streaming=True,
        )
        self.refuse_llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.REFUSE_MODEL,
            streaming=True,
        )
        logger.info("pipeline | LLM clients initialized")

        # The whitelist is also passed on every call (see nodes/search.py) so the
        # restriction does not depend on this instance alone.
        self.search = TavilySearch(
            tavily_api_key=settings.TAVILY_API_KEY,
            max_results=settings.SEARCH_MAX_RESULTS,
            include_domains=settings.SEARCH_ALLOWED_DOMAINS,
            search_depth="advanced",
            include_raw_content=False,
        )
        logger.info(
            f"pipeline | search domains={settings.SEARCH_ALLOWED_DOMAINS} "
            f"max_results={settings.SEARCH_MAX_RESULTS}"
        )

        self._initialized = True


pipeline = PipelineDefinition()
