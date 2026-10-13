import logging

from langchain_openai import ChatOpenAI
from langchain_tavily import TavilyExtract, TavilySearch

from src.config.settings import settings

logger = logging.getLogger(__name__)


class PipelineDefinition:
    plan_llm: ChatOpenAI
    answer_llm: ChatOpenAI
    search: TavilySearch
    extract: TavilyExtract

    def init(self) -> None:
        # Qwen3/3.5 on vLLM otherwise writes its chain of thought into `content`.
        # OpenAI rejects `chat_template_kwargs`, so it is only sent when enabled.
        extra_body = (
            {"chat_template_kwargs": {"enable_thinking": False}}
            if settings.DISABLE_THINKING
            else None
        )

        # Routing and query writing must be stable from run to run.
        self.plan_llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            extra_body=extra_body,
            model=settings.PLAN_MODEL,
            temperature=0,
        )
        self.answer_llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            extra_body=extra_body,
            model=settings.ANSWER_MODEL,
            temperature=settings.ANSWER_TEMPERATURE,
            streaming=True,
        )
        logger.info("pipeline | LLM clients initialized")

        # Results are also checked against the whitelist in nodes/retrieve.py.
        self.search = TavilySearch(
            tavily_api_key=settings.TAVILY_API_KEY,
            max_results=settings.SEARCH_MAX_RESULTS,
            include_domains=settings.SEARCH_ALLOWED_DOMAINS,
            search_depth="advanced",
            include_raw_content=False,
        )
        # Pulls the passages most relevant to the query from the top-ranked pages,
        # so the answer is not limited to the short search snippets.
        self.extract = TavilyExtract(
            tavily_api_key=settings.TAVILY_API_KEY,
            extract_depth="basic",
            chunks_per_source=3,
        )
        logger.info(
            f"pipeline | search domains={settings.SEARCH_ALLOWED_DOMAINS} "
            f"max_results={settings.SEARCH_MAX_RESULTS}"
        )


pipeline = PipelineDefinition()
