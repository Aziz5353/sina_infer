import asyncio
import logging
import re
import time
from urllib.parse import urlparse

from langchain_core.tools import ToolException

from src.config.settings import settings
from src.inference.pipeline_definition import pipeline
from src.inference.state import SinaState
from src.util.phi import scrub_phi

logger = logging.getLogger(__name__)

EXTRACT_TIMEOUT_S = 20


def _domain(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _is_allowed(url: str) -> bool:
    host = _domain(url)
    return any(host == d or host.endswith("." + d) for d in settings.SEARCH_ALLOWED_DOMAINS)


def _title_key(title: str) -> str:
    # Drop a site suffix ("Title | Site", "Title - Site") and punctuation, so the same
    # article served from mirror URLs collapses into one source.
    main = re.split(r"\s[|–-]\s", title, maxsplit=1)[0]
    return re.sub(r"[^a-z0-9]+", " ", main.lower()).strip()


def dedupe(results: list[dict], limit: int) -> list[dict]:
    """Best-scored first; one source per URL and per title."""
    seen: set[str] = set()
    kept: list[dict] = []
    for r in sorted(results, key=lambda r: r.get("score") or 0.0, reverse=True):
        keys = {_domain(r["url"]) + urlparse(r["url"]).path.rstrip("/"), _title_key(r.get("title") or "")}
        keys.discard("")
        if keys & seen:
            continue
        seen |= keys
        kept.append(r)
        if len(kept) == limit:
            break
    return kept


async def _search(query: str) -> list[dict]:
    try:
        response = await pipeline.search.ainvoke({"query": query})
    except ToolException:
        # langchain-tavily raises when a search returns no results.
        return []
    if "error" in response:
        logger.warning(f"retrieve | tavily search error: {response['error']!r}")
        return []
    return response.get("results", [])


async def _add_excerpts(results: list[dict], query: str) -> None:
    """Append the passages most relevant to the query from the top pages to their snippets."""
    top = results[: settings.SEARCH_EXTRACT_TOP_K]
    if not top:
        return
    try:
        response = await asyncio.wait_for(
            pipeline.extract.ainvoke({"urls": [r["url"] for r in top], "query": query}),
            timeout=EXTRACT_TIMEOUT_S,
        )
    except (ToolException, TimeoutError) as exc:
        logger.warning(f"retrieve | extract skipped: {type(exc).__name__}")
        return
    by_url = {item.get("url"): item.get("raw_content") or "" for item in response.get("results", [])}
    for r in top:
        if excerpt := by_url.get(r["url"], "").strip():
            r["content"] = f"{r.get('content', '')}\n[Excerpt] {excerpt[: settings.SEARCH_EXTRACT_MAX_CHARS]}"


async def retrieve_node(state: SinaState) -> dict:
    t0 = time.perf_counter()
    queries = []
    for raw in state.get("search_queries") or []:
        query, removed = scrub_phi(raw)
        if removed:
            logger.warning(f"retrieve | scrubbed identifier(s) from a query kinds={sorted(set(removed))}")
        if query:
            queries.append(query)

    batches = await asyncio.gather(*(_search(q) for q in queries))
    results = [r for batch in batches for r in batch if r.get("url")]
    allowed = [r for r in results if _is_allowed(r["url"])]
    if len(allowed) != len(results):
        logger.warning(f"retrieve | dropped {len(results) - len(allowed)} result(s) outside whitelist")

    sources = dedupe(allowed, settings.SEARCH_MAX_SOURCES)
    if queries:
        await _add_excerpts(sources, queries[0])

    logger.info(
        f"retrieve | queries={len(queries)} results={len(results)} sources={len(sources)} "
        f"domains={sorted({_domain(r['url']) for r in sources})} took={time.perf_counter() - t0:.2f}s"
    )
    logger.debug(f"retrieve | queries={queries} urls={[r['url'] for r in sources]}")
    return {"web_results": sources}
