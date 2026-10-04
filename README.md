# Sina-infer

Inference service for **Sina**, an Arabic-poetry chatbot. FastAPI + LangGraph + OpenAI-compatible LLM, with PGVector retrieval over an indexed Arabic poems corpus and Tavily web search as a fallback.

## Structure

```
src/
  api/         # FastAPI routers (chat, health, web UI)
  config/      # prompts + filter keys (constants), env settings, logging
  inference/   # LangGraph: state, graph builder, pipeline clients, streaming, nodes/
    nodes/       contextualize, analyzer, retrieve, search, generate, refuse
  model/       # Pydantic request schemas
  util/        # arabic_normalization (must mirror the ingestion service)
  ui/          # single-file chat web UI served at /
  main.py      # FastAPI app + lifespan that initializes the pipeline and builds the graph
```

## Graph

```
START → contextualize → analyzer → route ∈ {retrieve, search, generate, refuse}
                                      │
             ┌──────────┬─────────────┼──────────┐
             ▼          ▼             ▼          ▼
          retrieve    search      generate    refuse → END
             │          │             │
             │ (no docs)│             │
             └────► search ──────► generate → END
```

- **contextualize** — when `history` is non-empty, rewrites the latest message into a standalone question (resolving pronouns/references from the last `CONTEXTUALIZE_HISTORY_TURNS` turns). Skipped when there is no history.
- **analyzer** — picks the route, produces a `rewritten_query` for retrieval, and extracts metadata (`poet_name`, `poet_era`, `poem_category`, `poem_meter`, `poem_rhyme`) used as PGVector filters. Supplies `refusal_reason` for the refuse route.
- **retrieve** — similarity search in PGVector (BGE-M3 embeddings) on the normalized `rewritten_query`, filtered by the analyzer fields. Docs with distance above `RETRIEVAL_SCORE_THRESHOLD` are dropped; if none remain, falls through to **search**.
- **search** — Tavily web search restricted to `SEARCH_ALLOWED_DOMAINS`. If the results fall below `SEARCH_MIN_RESULTS` / `SEARCH_MIN_TOP_SCORE`, an unrestricted search is also run and the better result set is kept.
- **generate** — final answer with a Markdown `## المصادر` sources section; uses `metadata["original_text"]` (diacritics-preserving form) when rendering retrieved poems.
- **refuse** — polite Arabic refusal for off-policy questions.

Only the `generate` and `refuse` nodes stream tokens to the client.

## Setup

```bash
uv sync
cp .env.example .env   # then fill in the values below
```

Torch is installed from the PyTorch CPU wheel index (see `pyproject.toml`).

### Environment variables

Required:

| Var | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | LLM credentials (works with any OpenAI-compatible backend) |
| `OPENAI_BASE_URL` | LLM base URL, e.g. `https://api.openai.com/v1` |
| `ANALYZER_MODEL` | Router model, e.g. `gpt-4o-mini` |
| `CONTEXTUALIZE_MODEL` | Follow-up question rewriter, e.g. `gpt-4o-mini` |
| `GENERATE_MODEL` | Answer model; use a strong model for classical Arabic |
| `REFUSE_MODEL` | Refusal model, e.g. `gpt-4o-mini` |
| `TAVILY_API_KEY` | Web-search credentials |
| `PGVECTOR_CONNECTION` | `postgresql+psycopg://user:pass@host:5432/db` |
| `PGVECTOR_COLLECTION` | Must match the collection populated by the ingestion service (e.g. `aldiwan_poems`) |

Optional:

| Var | Default | Purpose |
| --- | --- | --- |
| `GENERATE_TEMPERATURE` | `0.2` | Lower = more faithful to retrieved poems; raise toward `0.7` for more stylistic answers |
| `CONTEXTUALIZE_HISTORY_TURNS` | `6` | How many recent history turns the contextualize node sees |
| `HF_EMBEDDING_MODEL_NAME` | `BAAI/bge-m3` | Must match the ingestion service |
| `HF_EMBEDDING_DEVICE` | `cpu` | Embedding device |
| `TOP_K_RETRIEVAL` | `8` | Candidates PGVector returns per query |
| `RETRIEVAL_SCORE_THRESHOLD` | `0.60` | Cosine-distance cutoff (lower = stricter) |
| `SEARCH_ALLOWED_DOMAINS` | `shamela.ws` | Comma-separated whitelist for Tavily's `include_domains` |
| `SEARCH_MAX_RESULTS` | `5` | Tavily results per search |
| `SEARCH_MIN_RESULTS` | `2` | Below this, the unrestricted fallback search runs |
| `SEARCH_MIN_TOP_SCORE` | `0.50` | Below this top score, the unrestricted fallback search runs |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:4200` | Comma-separated allowed origins |
| `LOG_LEVEL` | `INFO` | Console log level |
| `LOG_TO_FILE` | `false` | Also write `logs/app-debug.log` and `logs/app-info.log` (rotating, 50 MB × 3) |

Do **not** commit `.env`; keys belong only in the local file.

## Run

Local:

```bash
uvicorn src.main:app --reload
```

Docker (container `sina-infer`, port 8000; the HF model cache is kept in the `hf-cache` volume and `./logs` is mounted):

```bash
docker compose up --build
```

`PGVECTOR_CONNECTION` must be reachable from inside the container. The compose file does not join any external network.

## Endpoints

- `GET /` — ChatGPT-style web UI (RTL Arabic, streaming, conversations saved in the browser's localStorage). Open http://localhost:8000 after starting the server.
- `POST /chat` — body `{ "message": "...", "history": [{ "role": "user" | "assistant", "content": "..." }] }`, returns an SSE stream of `data: {"content": "..."}` events terminated by `data: [DONE]`. `history` is optional.
- `GET /health` — `{"status": "ok"}` once the graph is built, `503` otherwise.

## Tuning

Retrieval and search knobs are env vars (see the optional table above). Code-level knobs live in `src/config/constants.py`:

- `RETRIEVAL_FILTER_KEYS` — analyzer fields applied as PGVector filters. Values must match the form stored at ingest time exactly (`poet_name` is normalized with `normalize_arabic`; a multi-value `poem_category` becomes an `$in` filter).
- `ANALYZER_PROMPT` — holds the allowed values for `poet_era`, `poem_category`, `poem_meter` and `poem_rhyme`. Keep them in sync with the ingested metadata.
- `CONTEXTUALIZE_PROMPT`, `GENERATE_PROMPT`, `REFUSAL_PROMPT` — the system prompts for the other nodes.

If filtered queries log `kept=0`, loosen `RETRIEVAL_SCORE_THRESHOLD` or check the filter values against the stored metadata.

## Logs

Each node writes one log line per request. Useful greps when debugging:

```bash
docker logs sina-infer | grep "contextualize |"  # original vs standalone question
docker logs sina-infer | grep "analyzer |"       # route, rewritten query, extracted metadata
docker logs sina-infer | grep "retrieve |"       # filter applied, returned/kept counts, top score
docker logs sina-infer | grep "search"           # primary/fallback queries, result domains, which was used
docker logs sina-infer | grep "generate |"       # docs/web counts, context size, answer length
```

Per-document retrieval scores and full prompts are logged at `DEBUG`.
