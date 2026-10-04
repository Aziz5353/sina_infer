import logging
import time

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_postgres import PGVector
from langchain_tavily import TavilySearch

from src.config.settings import settings

logger = logging.getLogger(__name__)


class PipelineDefinition:
    analyzer_llm: ChatOpenAI
    contextualize_llm: ChatOpenAI
    generate_llm: ChatOpenAI
    refuse_llm: ChatOpenAI
    embeddings: HuggingFaceEmbeddings
    vector_store: PGVector
    search_primary: TavilySearch
    search_fallback: TavilySearch

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
        self.generate_llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.GENERATE_MODEL,
            temperature=settings.GENERATE_TEMPERATURE,
            streaming=True,
        )
        self.refuse_llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.REFUSE_MODEL,
            streaming=True,
        )
        logger.info("pipeline | LLM clients initialized")

        t0 = time.perf_counter()
        self.embeddings = HuggingFaceEmbeddings(
            model_name=settings.HF_EMBEDDING_MODEL_NAME,
            model_kwargs={"device": settings.HF_EMBEDDING_DEVICE},
            encode_kwargs={"normalize_embeddings": True},
        )
        logger.info(f"pipeline | embeddings loaded in {time.perf_counter() - t0:.2f}s")

        t1 = time.perf_counter()
        self.vector_store = PGVector(
            embeddings=self.embeddings,
            collection_name=settings.PGVECTOR_COLLECTION,
            connection=settings.PGVECTOR_CONNECTION,
            use_jsonb=True,
            async_mode=True,
        )
        logger.info(f"pipeline | vector store ready in {time.perf_counter() - t1:.2f}s")

        base_kwargs: dict = {
            "max_results": settings.SEARCH_MAX_RESULTS,
            "include_raw_content": False,
        }
        primary_kwargs = dict(base_kwargs)
        if settings.SEARCH_ALLOWED_DOMAINS:
            primary_kwargs["include_domains"] = settings.SEARCH_ALLOWED_DOMAINS

        self.search_primary = TavilySearch(**primary_kwargs)
        self.search_fallback = TavilySearch(**base_kwargs)
        logger.info(
            f"pipeline | search domains={settings.SEARCH_ALLOWED_DOMAINS or '-'} "
            f"max_results={settings.SEARCH_MAX_RESULTS}"
        )

        self._initialized = True


pipeline = PipelineDefinition()
