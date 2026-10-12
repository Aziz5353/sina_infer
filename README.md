# Sina-infer

Inference service for **Sina**, a clinical decision-support assistant for physicians. A doctor describes a patient case or asks a clinical question. Sina searches **only** a whitelist of trusted medical sites (Tavily) and answers with inline citations, in the doctor's language (Arabic or English), using a layout that fits the request: consult, calculation, clinical document, patient explanation or teaching material.

Stack: FastAPI + LangGraph + an OpenAI-compatible LLM (Qwen3.5 on vLLM, or OpenAI) + Tavily, streamed over SSE.

> Sina is decision support only. The treating physician's clinical judgment prevails.

## Structure

```
src/
  api/         # FastAPI routers (chat, health, web UI)
  config/      # prompts, answer layouts and headings (constants), env settings, logging
  inference/
    nodes/       plan, retrieve, answer
    graph.py, state.py, stream.py, pipeline_definition.py
  model/       # Pydantic request schemas
  util/        # phi.scrub_phi (strips identifiers from outgoing queries), conversation CSV log
  ui/          # single-file chat web UI served at /
  main.py      # FastAPI app + lifespan that initializes the pipeline and builds the graph
scripts/
  retrieval_eval.py  # search-only evaluation (see below)
```

## Graph

Three nodes and at most two model calls per turn:

```
START → plan ─┬─ (clarify / refuse: plan's own reply) ──────────▶ END
              └─ answer route → retrieve → answer ──────────────▶ END
                                (code only)  (streamed + code post-processing)
```

- **plan** (one structured model call, temperature 0) does what four nodes used to do:
  - `standalone_question`: folds the last `HISTORY_TURNS` turns into one standalone request, merging the doctor's answers to earlier clarifying questions.
  - `route` (`answer` | `clarify` | `refuse`), `query_type` (`patient_case` | `clinical_question`) and `task` (`consult` | `calculation` | `documentation` | `patient_education` | `teaching`).
  - `case`, `missing_critical_info`, `red_flags`: only what the doctor stated.
  - `queries` (English, de-identified, the first one aimed at the current guideline).
  - `reply`: the message to the doctor for clarify or refuse, in their language. If it is empty, a fixed localized reply is used.

  Code guards: clarify is only allowed for a `consult` about a specific patient with something missing; anything else is answered with stated assumptions. Queries in a non-Latin script are dropped. The reply language is detected in code from the doctor's message.
- **retrieve** (no model):
  - Runs the queries in parallel on Tavily with `include_domains=SEARCH_ALLOWED_DOMAINS` and `search_depth="advanced"`. Every query first goes through `scrub_phi()`. Results outside the whitelist are dropped. There is no unrestricted search.
  - Removes duplicates (same URL, or the same title from a mirror site), ranks by Tavily score and keeps the top `SEARCH_MAX_SOURCES`.
  - For the top `SEARCH_EXTRACT_TOP_K` pages, fetches the passages most relevant to the first query (Tavily Extract) and appends up to `SEARCH_EXTRACT_MAX_CHARS` characters to the snippet.
- **answer** (one streamed model call):
  - The sections come from code, per task and in the reply language (see below). The red-flag section is included only when red flags exist.
  - Grounding: every claim cited `[n]` from the sources; no dose, frequency or threshold that is not in a source; formulas from the sources applied with the arithmetic shown; uncovered parts named in place while covered parts are still answered; most recent major guideline wins when sources disagree.
  - The model's text is streamed as is. Code then appends the **Sources** list (only the sources actually cited `[n]`) and the closing line.
  - If retrieval found nothing, a fixed localized message is returned and the model is not called.

Nodes send client-facing text through LangGraph's custom stream; plan's structured output never reaches the client.

## Output layouts

Headings are written in the reply language; drug names, lab tests and diagnoses stay in English.

| Task | Sections |
| --- | --- |
| consult, patient case | ⚠️ Red flags (if any) · Case summary · Differential diagnosis · Suggestions |
| consult, clinical question | ⚠️ Red flags (if any) · Answer · Practical points |
| calculation | ⚠️ Red flags (if any) · Working · Result · Next steps |
| documentation | ⚠️ Red flags (if any) · S — Subjective · O — Objective · A — Assessment · P — Plan |
| patient_education | ⚠️ Red flags (if any) · For the patient (no citations) · For the physician |
| teaching | ⚠️ Red flags (if any) · Material |

Every answer ends with **Sources** (`[n] Title — URL`, cited sources only) and the decision-support line, both added by code.

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
| `PLAN_MODEL` | Planning step (structured output: routing, case, queries, clarify/refuse reply), e.g. `qwen3` or `gpt-4o-mini` |
| `ANSWER_MODEL` | Final cited answer. Use the strongest model available. |
| `TAVILY_API_KEY` | Web-search credentials |
| `SEARCH_ALLOWED_DOMAINS` | JSON list whitelist, e.g. `'["ncbi.nlm.nih.gov", "who.int", "cdc.gov"]'`. Wrap it in single quotes so it can span several lines. **The app fails at startup if it is empty.** Subdomains are allowed (`pubmed.ncbi.nlm.nih.gov` matches `ncbi.nlm.nih.gov`). |

Optional:

| Var | Default | Purpose |
| --- | --- | --- |
| `ANSWER_TEMPERATURE` | `0.1` | Keep low for faithful, source-grounded answers (plan always runs at 0) |
| `HISTORY_TURNS` | `6` | How many recent history turns plan sees |
| `SEARCH_MAX_RESULTS` | `5` | Tavily results per query |
| `SEARCH_QUERIES_PER_TURN` | `3` | Max queries per search round |
| `SEARCH_MAX_SOURCES` | `10` | Sources passed to the answer after dedupe and ranking |
| `SEARCH_EXTRACT_TOP_K` | `4` | Top sources whose relevant passages are fetched (0 disables Tavily Extract) |
| `SEARCH_EXTRACT_MAX_CHARS` | `3000` | Max characters of fetched passages per source |
| `MAX_CLARIFYING_QUESTIONS` | `4` | Max numbered questions in a clarify reply |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:4200` | Comma-separated allowed origins |
| `LOG_LEVEL` | `INFO` | Console log level |
| `LOG_TO_FILE` | `false` | Also write `logs/app-debug.log` and `logs/app-info.log` (rotating, 50 MB × 3) |
| `SAVE_CONVERSATIONS` | `false` | Append one row per `/chat` turn to a CSV for offline evaluation (see [Conversation dataset](#conversation-dataset)) |
| `GENERATION_MODEL_NAME` | | Names the CSV `data/conversations_<name>.csv` |
| `CONVERSATIONS_CSV_PATH` | `data/conversations.csv` | Where that CSV is written (overrides the name above) |

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

- Prompts: `PLAN_PROMPT` (routing, case, red flags, queries, clarify/refuse reply) and `ANSWER_PROMPT` (grounding and writing rules) in `src/config/constants.py`.
- Answer layouts and their headings in both languages: `ANSWER_SECTIONS` and `HEADINGS` in the same file.

If answers often say the sources did not cover something, widen `SEARCH_ALLOWED_DOMAINS` or raise `SEARCH_MAX_SOURCES`. If too many cases are clarified instead of answered, tighten the clarify rule in `PLAN_PROMPT`.

## Privacy and logs

- `INFO` logs carry no clinical text: only route, task, language, counts (case fields, missing items, red flags, queries, sources, citations), search domains, answer length and durations.
- Full messages, case objects, queries, prompts and answers are logged only at `DEBUG`. With `LOG_TO_FILE=true`, `logs/app-debug.log` contains them, so treat that file as sensitive.
- With `SAVE_CONVERSATIONS=true`, the conversations CSV stores full messages and answers. Treat it as sensitive.

Each node writes one log line per request. Useful greps:

```bash
docker logs sina-infer | grep "plan |"      # route (and the model's route), task, language, counts
docker logs sina-infer | grep "retrieve |"  # queries, results, sources, domains, PHI scrubs
docker logs sina-infer | grep "answer |"    # sections, sources vs cited, context size, answer length
```

## Conversation dataset

With `SAVE_CONVERSATIONS=true`, every `/chat` turn is appended to `CONVERSATIONS_CSV_PATH` once the stream ends (also when the client disconnects or the graph fails; `error` then holds the exception name). Columns:

`timestamp`, `message`, `history`, `standalone_message`, `language`, `route`, `query_type`, `task`, `case`, `missing_critical_info`, `red_flags`, `search_queries`, `sources` (`url`, `title`, `score`), `answer`, `latency_s`, `error`.

If the configured file already exists with different columns (written by an older version), rows go to the first sibling `<name>_v2.csv`, `<name>_v3.csv`, ... that is new or has the current columns.

List and dict columns are JSON strings:

```python
import json, pandas as pd
df = pd.read_csv("data/conversations.csv")
df["sources"] = df["sources"].fillna("[]").map(json.loads)
```

## Search evaluation

`scripts/retrieval_eval.py` measures search quality on its own. It runs only `plan` and `retrieve` (no answer model) for a fixed set of 10 questions and checks whether the retrieved sources (snippets plus fetched passages) contain the facts a good answer needs, e.g. "80–90 mg/kg/day" for pediatric otitis media.

```bash
uv run python -m scripts.retrieval_eval               # one pass, about 1 minute
uv run python -m scripts.retrieval_eval --repeats 3   # several passes
uv run python -m scripts.retrieval_eval --only 4 7    # selected questions
```

It prints the queries, the facts found or missing per question, and the source domains, and appends a JSON summary to `data/retrieval_eval.jsonl` so runs can be compared. Edit `QUESTIONS` in the script to add questions or facts.
