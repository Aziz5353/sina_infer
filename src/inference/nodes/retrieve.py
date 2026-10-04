import logging
import time

from langchain_core.documents import Document

from src.config.constants import RETRIEVAL_FILTER_KEYS
from src.config.settings import settings
from src.inference.pipeline_definition import pipeline
from src.inference.state import SinaState
from src.util.arabic_normalization import normalize_arabic

logger = logging.getLogger(__name__)


def _build_filter(state: SinaState) -> dict[str, object]:
    filter_: dict[str, object] = {}
    for key in RETRIEVAL_FILTER_KEYS:
        value = state.get(key)
        if not value:
            continue
        if key == "poem_category" and isinstance(value, list):
            filter_[key] = value[0] if len(value) == 1 else {"$in": value}
        elif key == "poet_name":
            filter_[key] = normalize_arabic(value)
        else:
            filter_[key] = value
    return filter_


async def retrieve_node(state: SinaState) -> dict:
    t0 = time.perf_counter()
    query = normalize_arabic(state.get("rewritten_query") or state["question"])
    filter_ = _build_filter(state)
    search_kwargs: dict = {"k": settings.TOP_K_RETRIEVAL}
    if filter_:
        search_kwargs["filter"] = filter_
    scored = await pipeline.vector_store.asimilarity_search_with_score(query, **search_kwargs)
    docs: list[Document] = [
        doc for doc, score in scored if score <= settings.RETRIEVAL_SCORE_THRESHOLD
    ]
    top_score = scored[0][1] if scored else float("inf")
    took = time.perf_counter() - t0
    logger.info(
        f"retrieve | query={query!r} k={settings.TOP_K_RETRIEVAL} "
        f"filter={filter_ or '-'} "
        f"returned={len(scored)} kept={len(docs)} top_score={top_score:.3f} "
        f"threshold={settings.RETRIEVAL_SCORE_THRESHOLD:.2f} took={took:.2f}s"
    )
    for i, (doc, score) in enumerate(scored, start=1):
        kept = "Y" if score <= settings.RETRIEVAL_SCORE_THRESHOLD else "N"
        snippet = doc.page_content[:200].replace("\n", " ⏎ ")
        logger.debug(
            f"retrieve | doc[{i}] score={score:.3f} kept={kept} "
            f"meta={doc.metadata} content={snippet!r}"
        )
    return {"retrieved_docs": docs}
