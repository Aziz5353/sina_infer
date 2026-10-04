import logging
import time
from urllib.parse import urlparse

from langchain_tavily import TavilySearch

from src.config.settings import settings
from src.inference.pipeline_definition import pipeline
from src.inference.state import SinaState

logger = logging.getLogger(__name__)


async def _run(search: TavilySearch, query: str) -> list[dict]:
    response = await search.ainvoke({"query": query})
    return response.get("results", []) if isinstance(response, dict) else []


def _top_score(results: list[dict]) -> float:
    return max((r.get("score") or 0.0) for r in results) if results else 0.0


def _is_relevant(results: list[dict]) -> bool:
    return (
        len(results) >= settings.SEARCH_MIN_RESULTS
        and _top_score(results) >= settings.SEARCH_MIN_TOP_SCORE
    )


def _summarize(results: list[dict]) -> tuple[list[str], float]:
    urls = [r.get("url") for r in results[:3]]
    domains = [urlparse(u).netloc for u in urls if u]
    return domains, _top_score(results)


async def search_node(state: SinaState) -> dict:
    t0 = time.perf_counter()
    query = state["question"]

    results = await _run(pipeline.search_primary, query)
    domains, top_score = _summarize(results)
    logger.info(
        f"search[primary] | query={query!r} results={len(results)} "
        f"top_score={top_score:.3f} domains={domains}"
    )

    used = "primary"
    if not _is_relevant(results) and settings.SEARCH_ALLOWED_DOMAINS:
        logger.info(
            f"search[primary] | below thresholds "
            f"(min_results={settings.SEARCH_MIN_RESULTS}, "
            f"min_top_score={settings.SEARCH_MIN_TOP_SCORE:.2f}) → fallback"
        )
        fb_results = await _run(pipeline.search_fallback, query)
        fb_domains, fb_top = _summarize(fb_results)
        logger.info(
            f"search[fallback] | query={query!r} results={len(fb_results)} "
            f"top_score={fb_top:.3f} domains={fb_domains}"
        )
        if len(fb_results) > len(results) or fb_top > top_score:
            results, used = fb_results, "fallback"

    took = time.perf_counter() - t0
    logger.info(f"search | used={used} final_results={len(results)} took={took:.2f}s")
    logger.debug(f"search results:\n{results}")
    return {"search_results": results}
