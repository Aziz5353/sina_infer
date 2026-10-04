import asyncio
import logging
import time
from urllib.parse import urlparse

from langchain_core.tools import ToolException

from src.config.settings import settings
from src.inference.pipeline_definition import pipeline
from src.inference.state import SinaState
from src.util.phi import scrub_phi

logger = logging.getLogger(__name__)

SEARCH_DEPTH = "advanced"


def _domain(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _is_allowed(url: str) -> bool:
    host = _domain(url)
    return any(
        host == d.lower() or host.endswith("." + d.lower())
        for d in settings.SEARCH_ALLOWED_DOMAINS
    )


async def _run(query: str) -> list[dict]:
    try:
        response = await pipeline.search.ainvoke(
            {
                "query": query,
                "include_domains": settings.SEARCH_ALLOWED_DOMAINS,
                "search_depth": SEARCH_DEPTH,
            }
        )
    except ToolException:
        # langchain-tavily raises when a search returns no results.
        return []
    if not isinstance(response, dict):
        return []
    if "error" in response:
        logger.warning(f"search | tavily error: {response['error']!r}")
        return []
    return response.get("results", [])


def _merge(existing: list[dict], new: list[dict], limit: int) -> list[dict]:
    by_url: dict[str, dict] = {}
    for result in [*existing, *new]:
        url = result.get("url")
        if not url:
            continue
        current = by_url.get(url)
        if current is None or (result.get("score") or 0.0) > (current.get("score") or 0.0):
            by_url[url] = result
    ranked = sorted(by_url.values(), key=lambda r: r.get("score") or 0.0, reverse=True)
    return ranked[:limit]


async def search_node(state: SinaState) -> dict:
    t0 = time.perf_counter()
    attempt = (state.get("search_attempts") or 0) + 1
    existing = state.get("web_results") or []

    if not settings.SEARCH_ALLOWED_DOMAINS:
        logger.error("search | SEARCH_ALLOWED_DOMAINS is empty, refusing to search")
        return {"search_attempts": attempt, "web_results": existing}

    queries: list[str] = []
    scrubbed: list[str] = []
    for raw in (state.get("search_queries") or [])[: settings.SEARCH_QUERIES_PER_TURN]:
        query, removed = scrub_phi(raw)
        scrubbed.extend(removed)
        if query:
            queries.append(query)
    if scrubbed:
        logger.warning(
            f"search | scrubbed {len(scrubbed)} identifier(s) from queries "
            f"kinds={sorted(set(scrubbed))}"
        )

    batches = await asyncio.gather(*(_run(q) for q in queries))
    new = [r for batch in batches for r in batch]
    allowed = [r for r in new if _is_allowed(r.get("url") or "")]
    if len(allowed) != len(new):
        logger.warning(f"search | dropped {len(new) - len(allowed)} result(s) outside whitelist")

    limit = settings.SEARCH_MAX_RESULTS * settings.SEARCH_QUERIES_PER_TURN
    merged = _merge(existing, allowed, limit)
    domains = sorted({_domain(r["url"]) for r in merged})
    took = time.perf_counter() - t0
    logger.info(
        f"search | attempt={attempt} queries={len(queries)} new_results={len(allowed)} "
        f"total_results={len(merged)} domains={domains} took={took:.2f}s"
    )
    logger.debug(f"search | queries={queries}")
    for i, r in enumerate(merged, start=1):
        logger.debug(f"search | result[{i}] score={r.get('score')} url={r.get('url')}")
    return {"web_results": merged, "search_attempts": attempt}
