# Sina-infer

Inference service for **Sina**, an Arabic-poetry chatbot. FastAPI + LangGraph + OpenAI-compatible LLM, with PGVector retrieval over an indexed Arabic poems corpus and Tavily web search as a fallback.

## Structure

```
api/         # FastAPI routers (chat, health, web UI)
config/      # constants, settings, logging
inference/   # LangGraph: state, graph builder, streaming, nodes/
  nodes/       analyzer, retrieve, search, generate, refuse
model/       # Pydantic request/response schemas
util/        # arabic_normalization, shared helpers
ui/          # single-file chat web UI served at /
main.py      # FastAPI app + lifespan that builds the graph
```

## Graph

```
        ┌────────┐
START → │analyzer│ → route ∈ {retrieve, search, generate, refuse}
        └────────┘
              │
   ┌──────────┼──────────┬──────────┐
   ▼          ▼          ▼          ▼
retrieve    search    generate    refuse → END
   │          │          │
   │ (no docs)│          │
   └────► search ────► generate → END
```

- **analyzer** — classifies the question and extracts metadata (`poet_name`, `poet_era`, `poem_category`) used as PGVector filters.
- **retrieve** — similarity search in PGVector (BGE-M3 embeddings), filtered by analyzer fields. Empty results fall through to **search**.
- **search** — Tavily web search restricted to `SEARCH_ALLOWED_DOMAINS`.
- **generate** — final answer; uses `metadata["original_text"]` (diacritics-preserving form) when rendering retrieved poems.
- **refuse** — polite Arabic refusal for off-policy questions.

## Setup

```bash
uv sync
cp .env.example .env   # then fill in the values below
```

### Required environment variables

| Var | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | LLM credentials (works with any OpenAI-compatible backend) |
| `OPENAI_BASE_URL` | LLM base URL, e.g. `https://api.openai.com/v1` |
| `ANALYZER_MODEL` | Router model — `gpt-4o-mini` is sufficient |
| `GENERATE_MODEL` | Answer model — `gpt-4o` or `gpt-4.1` recommended for classical Arabic |
| `GENERATE_TEMPERATURE` | optional, default `0.2`. Lower = more faithful to retrieved poems; raise toward `0.7` for more stylistic answers |
| `REFUSE_MODEL` | Refusal model — `gpt-4o-mini` is sufficient |
| `HF_EMBEDDING_MODEL_NAME` | Must match the ingestion service. Default: `BAAI/bge-m3` |
| `HF_EMBEDDING_DEVICE` | `cpu` or `cuda` |
| `TAVILY_API_KEY` | Web-search fallback credentials |
| `PGVECTOR_CONNECTION` | `postgresql+psycopg://user:pass@host:5432/db` |
| `PGVECTOR_COLLECTION` | Must match the collection populated by the ingestion service (e.g. `aldiwan_poems_v1`) |
| `LOG_LEVEL` | optional, default `INFO` |

Do **not** commit `.env` — keys belong only in the local file.

## Run

Local:

```bash
uvicorn main:app --reload
```

Docker (joins the `sina_rag_default` network so it can reach `sina-postgres`):

```bash
docker compose up --build
```

## Endpoints

- `GET /` — ChatGPT-style web UI (RTL Arabic, streaming, conversations saved in the browser's localStorage). Open http://localhost:8000 after starting the server.
- `POST /chat` — body `{ "message": "...", "history": [{ "role": "user" | "assistant", "content": "..." }] }`, returns an SSE stream of the generated answer. `history` is optional.

## Tuning

Key knobs live in `config/constants.py`:

- `TOP_K_RETRIEVAL` — how many candidates PGVector returns per query.
- `RETRIEVAL_SCORE_THRESHOLD` — cosine-distance cutoff (lower = stricter). Docs above this are dropped, which triggers the web-search fallback. Loosen if filtered queries return `kept=0`.
- `RETRIEVAL_FILTER_KEYS` — analyzer fields applied as PGVector equality filters. Values must match the form stored at ingest time exactly.
- `SEARCH_ALLOWED_DOMAINS` — whitelist passed to Tavily's `include_domains`.

## Logs

Per-request lines are emitted by each node. Useful greps when debugging:

```bash
docker logs sina-infer-api-1 | grep "analyzer |"   # route + extracted metadata
docker logs sina-infer-api-1 | grep "retrieve |"   # filter applied, returned/kept counts, top score
docker logs sina-infer-api-1 | grep "search |"     # tavily query + result domains
docker logs sina-infer-api-1 | grep "generate |"   # final prompt size + answer length
```
