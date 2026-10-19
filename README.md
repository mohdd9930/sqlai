# AskData — Prototype

A working proof-of-concept of the conversational text-to-SQL agent described in
`askdata_concept_note.md`. Ask questions in plain English about a sample "Group
Mobility" (internal job applications) dataset stored in SQLite; the agent generates
SQL with Gemini, validates it against read-only/allow-list guardrails, executes it,
and returns a table, a chart, and a 2-line narrative insight.

The sample data models a hiring funnel: each `applications` row moves through
`screening -> assessment -> interview -> decision -> offered -> joined`, or drops
out as `rejected` at any point. Per-round interview verdicts (`select`/`reject`)
are recorded separately in `interview_feedback`; `joining_date` is set once an
application reaches `joined`.

Runs without an API key too — see "Offline demo mode" below. The local web UI
uses plain HTML, CSS, and JavaScript and is served by the Python app at
`http://localhost:8000`.

## What this proves

- NL question → SQL generation grounded in a semantic layer (`semantic_layer.yaml`)
- Guardrails: only `SELECT`, table allow-list, auto-injected row limit
- Self-correction: execution errors are fed back to the model (up to 2 retries)
- Follow-up questions reuse the previous SQL as context
- Automatic chart type selection (line / bar / table) + narrative summary

## What's deliberately simplified vs. the full concept note

- No pgvector/RAG retrieval — the (small) schema is passed to the LLM in full.
- No trained intent classifier — follow-ups are detected with a keyword heuristic.
- No Vega-Lite — charts render to local PNG files and are displayed in the web UI.
- No RBAC/row-level security — this is a single-user local demo.

## Setup

On Windows, run `run.bat` from the project folder (or double-click it). It creates
the virtual environment, installs dependencies, creates `.env` if needed, seeds
the sample database if it is missing, and starts the web UI at
`http://localhost:8000`. Add your Gemini API key
to `.env` as `GEMINI_API_KEY` and select the model with `ASKDATA_MODEL` to enable
Gemini; without a key, the app runs in offline demo mode. The model setting has
no code default: local `.env` or the hosting provider's environment variables are
the source of truth.

To set things up manually:

```bash
cd <project-folder>
python -m pip install -r requirements.txt
cp .env.example .env   # then edit .env and set GEMINI_API_KEY / ASKDATA_MODEL
python -m askdata.data.seed_db
python -m askdata.web
```

The UI, API, and charts are served from the same local server and port. To use the
command-line interface instead, run `python -m askdata.cli`.
For Render, configure both `GEMINI_API_KEY` and `ASKDATA_MODEL` in the service's
environment settings, then redeploy.

## Example session

```
ask> How many applications came in last quarter, and how many joined, by subsidiary?
ask> now split this by gender
ask> How many interview rounds ended in a reject, by subsidiary?
ask> What is the offer-to-join rate?
ask> delete all applications
```

The last one should be refused or blocked by the guardrails rather than executed.

## Offline demo mode

If `GEMINI_API_KEY` isn't set in `.env`, the CLI still runs — it falls back to
a rule-based demo (`OFFLINE_MODE` in `askdata/config.py`) that matches your question
against the golden-query bank in `semantic_layer.yaml` by keyword overlap instead of
calling an LLM, and generates a stats-based narrative instead of a real one. It only
handles questions close to the golden queries (and a "split by gender/department"
follow-up on the previous query) — anything else reports as unmatched. Add a real
key any time to switch to full LLM-driven generation.

## Layout

- `semantic_layer.yaml` — table/column/metric/synonym cards (section 8.1 of the concept note)
- `askdata/data/seed_db.py` — builds the sample SQLite database
- `askdata/schema_context.py` — renders the semantic layer into the LLM prompt
- `askdata/sql_generator.py` — Gemini call that produces SQL
- `askdata/validator.py` — sqlglot-based guardrails
- `askdata/executor.py` — read-only SQLite execution
- `askdata/summarizer.py` — Gemini call that produces the narrative insight
- `askdata/chart.py` — chart-type heuristic + matplotlib rendering
- `askdata/exporter.py` — saves a result to a new `.xlsx`, or into a user-supplied Excel template
- `askdata/pipeline.py` — orchestrates the full generate→validate→execute→summarize loop
- `askdata/web.py` — serves the HTML interface, question API, and generated charts on port 8000
- `askdata/static/` — vanilla HTML, CSS, and JavaScript for the local dashboard
- `askdata/cli.py` — REPL entrypoint; after each answer, offers to save it to Excel (plain or into a template)
