# Sina-infer

Inference service for **Sina**, a clinical decision-support assistant for physicians. A doctor describes a patient case or asks a clinical question. Sina builds a structured picture of the case and searches **only** a whitelist of trusted medical sites (Tavily). It then answers with a cited differential and suggestions, or asks for the information it needs.

Stack: FastAPI + LangGraph + an OpenAI-compatible LLM + Tavily, streamed over SSE.

> Sina is decision support only. The treating physician's clinical judgment prevails.

## Structure

```
src/
  api/         # FastAPI routers (chat, health, web UI)
  config/      # prompts (constants), env settings, logging
  inference/   # LangGraph: state, graph builder, pipeline clients, prompt context, streaming, nodes/
    nodes/       contextualize, analyzer, search, assess_evidence, generate, clarify, refuse
  model/       # Pydantic request schemas
  util/        # phi.scrub_phi (strips identifiers from outgoing search queries)
  ui/          # single-file chat web UI served at /
  main.py      # FastAPI app + lifespan that initializes the pipeline and builds the graph
tests/         # pytest; LLMs and Tavily are mocked
```

## Graph

```
START → contextualize → analyzer ─┬─ refuse → END
                                  ├─ clarify → END
                                  └─ search → assess_evidence ─┬─ generate → END
                                       ▲                       ├─ clarify → END
                                       └──── retry ────────────┘
```

- **contextualize**: runs only when `history` is non-empty. It folds the last `CONTEXTUALIZE_HISTORY_TURNS` turns into one standalone message carrying the **full clinical picture**: demographics, symptoms, findings, results, and the doctor's answers to earlier clarifying questions. It also resolves references.
- **analyzer**: produces structured output with these fields:
  - `route`: `search` | `clarify` | `refuse`
  - `query_type`: `patient_case` | `clinical_question`
  - `case`: age, sex, pregnancy status, complaint, symptoms, duration, vitals, exam, labs/imaging, meds, allergies, comorbidities. Only stated values are filled; nothing is invented.
  - `missing_critical_info`, `red_flags`, `refusal_reason`
  - 1..`SEARCH_QUERIES_PER_TURN` de-identified English `search_queries`

  Routing rules:
  - **refuse** non-medical or clearly harmful requests. Frank clinical questions such as overdose thresholds, controlled drugs or end-of-life care are *not* refused.
  - **clarify** only a patient case whose missing details would materially change the assessment.
  - **search** everything else. A `clinical_question` is never sent to clarify.
- **search**: sends each query to Tavily with `include_domains=SEARCH_ALLOWED_DOMAINS` and `search_depth="advanced"`. `max_results=SEARCH_MAX_RESULTS` is set on the client.
  - Every query first goes through `scrub_phi()`, which strips emails, phone numbers, 10-digit Saudi national/Iqama IDs and dates of birth. A `WARNING` is logged when something is removed.
  - Any result whose host is not on the whitelist is dropped.
  - Results accumulate across attempts, are deduped by URL, and are capped at the top `SEARCH_MAX_RESULTS × SEARCH_QUERIES_PER_TURN` by score. There is **no** unrestricted fallback search.
- **assess_evidence**: decides whether the results support a differential and recommendations, or a direct answer for a clinical question.
  - Fewer than `SEARCH_MIN_RESULTS` results is always insufficient.
  - Sufficient → **generate**.
  - Insufficient, with refined queries and `search_attempts < MAX_SEARCH_ATTEMPTS` → **search** again with the refined queries.
  - Otherwise → **clarify** with `clarify_reason="evidence_gap"`.
- **generate**: the cited answer, grounded strictly in the web results. Doses appear only if a retrieved source states them. Unsupported sections say so instead of being filled in.
- **clarify**: depends on the reason.
  - `case_gap`: one line on why more information is needed, then up to `MAX_CLARIFYING_QUESTIONS` numbered questions, most decision-changing first.
  - `evidence_gap`: says the configured sources did not cover the request, lists what was missing, and asks for details that would allow a narrower search.

  Neither variant gives a diagnosis or management. Red flags, when present, always come first.
- **refuse**: a short, polite out-of-scope message.

Only `generate`, `clarify` and `refuse` stream tokens to the client.

## Output format

The answer is written in the language the doctor used (Arabic or English), including the headings. Drug names, lab tests and diagnoses stay in English.

1. **⚠️ Red flags / urgent action**: only when red flags exist, and then always first.
2. **Case summary**: 1–2 lines, plus any assumptions made because information was missing.
3. **Differential diagnosis** (patient case): ranked, each item with supporting features, features against and inline citations `[1][2]`.
   **Answer** (clinical question): the direct answer with citations.
4. **Suggestions**: investigations; management (doses only if sourced and cited); referral/follow-up; what would change the assessment.
5. **Sources**: `[n] Title — URL`, matching the inline citations.
6. One closing line: decision support only, and the treating physician's clinical judgment prevails.

## Setup

```bash
uv sync
cp .env.example .env   # then fill in the values below
```

### Environment variables

Required:

| Var | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | LLM credentials (works with any OpenAI-compatible backend) |
| `OPENAI_BASE_URL` | LLM base URL, e.g. `https://api.openai.com/v1` |
| `ANALYZER_MODEL` | Router / case extractor (structured output), e.g. `gpt-4o-mini` |
| `CONTEXTUALIZE_MODEL` | Multi-turn case merger, e.g. `gpt-4o-mini` |
| `ASSESS_MODEL` | Evidence-sufficiency judge (structured output), e.g. `gpt-4o-mini` |
| `GENERATE_MODEL` | Final cited answer. Use a strong model. |
| `CLARIFY_MODEL` | Clarifying questions, e.g. `gpt-4o-mini` |
| `REFUSE_MODEL` | Refusal message, e.g. `gpt-4o-mini` |
| `TAVILY_API_KEY` | Web-search credentials |
| `SEARCH_ALLOWED_DOMAINS` | JSON list whitelist, e.g. `'["ncbi.nlm.nih.gov", "who.int", "cdc.gov"]'`. Wrap it in single quotes so it can span several lines. **The app fails at startup if it is empty.** Subdomains are allowed (`pubmed.ncbi.nlm.nih.gov` matches `ncbi.nlm.nih.gov`). |

Optional:

| Var | Default | Purpose |
| --- | --- | --- |
| `GENERATE_TEMPERATURE` | `0.1` | Keep low for faithful, source-grounded answers |
| `CONTEXTUALIZE_HISTORY_TURNS` | `6` | How many recent history turns the contextualize node sees |
| `SEARCH_MAX_RESULTS` | `5` | Tavily results per query |
| `SEARCH_MIN_RESULTS` | `2` | Below this many accumulated results, evidence is insufficient |
| `SEARCH_QUERIES_PER_TURN` | `3` | Max queries per search attempt |
| `MAX_SEARCH_ATTEMPTS` | `2` | Search rounds before falling back to an evidence-gap clarification |
| `MAX_CLARIFYING_QUESTIONS` | `4` | Max numbered questions in a clarify response |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:4200` | Comma-separated allowed origins |
| `LOG_LEVEL` | `INFO` | Console log level |
| `LOG_TO_FILE` | `false` | Also write `logs/app-debug.log` and `logs/app-info.log` (rotating, 50 MB × 3) |
| `SAVE_CONVERSATIONS` | `false` | Append one row per `/chat` turn to a CSV for offline evaluation (see [Conversation dataset](#conversation-dataset)) |
| `CONVERSATIONS_CSV_PATH` | `data/conversations.csv` | Where that CSV is written |

Do **not** commit `.env`; keys belong only in the local file.

## Run

Local:

```bash
uvicorn src.main:app --reload
```

Docker (container `sina-infer`, port 8000, `./logs` and `./data` mounted):

```bash
docker compose up --build
```

## Endpoints

- `GET /`: chat web UI (Arabic chrome; every message and Markdown block uses `dir="auto"` for mixed Arabic/English; conversations are saved in the browser's localStorage). Open http://localhost:8000 after starting the server.
- `POST /chat`: body `{ "message": "...", "history": [{ "role": "user" | "assistant", "content": "..." }] }`. Returns an SSE stream of `data: {"content": "..."}` events terminated by `data: [DONE]`. `history` is optional; send the previous turns, including Sina's clarifying questions, so answers to them are merged into the case.
- `GET /health`: `{"status": "ok"}` once the graph is built, `503` otherwise.

Example:

```bash
curl -N -X POST localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"message": "45M, 2h crushing chest pain radiating to left arm, diaphoretic, BP 150/95"}'
```

## Tuning

The prompts live in `src/config/constants.py`:

- `CONTEXTUALIZE_PROMPT`: how history is folded into the standalone case
- `ANALYZER_PROMPT`: routing rules, case extraction, red flags, query writing
- `ASSESS_PROMPT`: what counts as sufficient evidence
- `GENERATE_PROMPT`: grounding rules and output format
- `CLARIFY_PROMPT` and `REFUSAL_PROMPT`

If many requests end in `clarify reason=evidence_gap`, widen `SEARCH_ALLOWED_DOMAINS` or raise `MAX_SEARCH_ATTEMPTS`. If too many cases are clarified instead of answered, tighten the clarify rule in `ANALYZER_PROMPT`.

## Privacy and logs

- `INFO` logs carry no clinical text: only route, query type, counts (case fields filled, missing items, red flags, queries, results), search domains, attempts, sufficiency, answer length and durations.
- Full messages, case objects, queries, prompts and answers are logged only at `DEBUG`. With `LOG_TO_FILE=true`, `logs/app-debug.log` contains them, so treat that file as sensitive.

- With `SAVE_CONVERSATIONS=true`, `data/conversations.csv` stores full messages and answers. It is git-ignored; treat it as sensitive.

Each node writes one log line per request. Useful greps:

```bash
docker logs sina-infer | grep "contextualize |"    # history turns, message sizes
docker logs sina-infer | grep "analyzer |"         # route, query_type, case/missing/red-flag/query counts
docker logs sina-infer | grep "search |"           # attempt, queries, new/total results, domains, PHI scrubs
docker logs sina-infer | grep "assess_evidence |"  # results, sufficient, gaps, refined queries
docker logs sina-infer | grep "generate |"         # web results, context size, answer length
docker logs sina-infer | grep "clarify |"          # reason (case_gap / evidence_gap), counts, answer length
```

## Conversation dataset

With `SAVE_CONVERSATIONS=true`, every `/chat` turn is appended to `CONVERSATIONS_CSV_PATH` once the stream ends (also when the client disconnects or the graph fails; `error` then holds the exception name). Columns:

`timestamp`, `message`, `history`, `standalone_message`, `route`, `query_type`, `clarify_reason`, `refusal_reason`, `case`, `missing_critical_info`, `red_flags`, `search_queries`, `search_attempts`, `evidence_gaps`, `sources` (`url`, `title`, `score`), `answer`, `latency_s`, `error`.

List and dict columns are JSON strings:

```python
import json, pandas as pd
df = pd.read_csv("data/conversations.csv")
df["sources"] = df["sources"].fillna("[]").map(json.loads)
```

## Tests

```bash
uv run pytest
```

The tests mock the LLMs and Tavily. They cover analyzer routing, the assess→search retry loop and its stop condition, the whitelist on every Tavily call, `scrub_phi`, and the startup failure on an empty whitelist.
