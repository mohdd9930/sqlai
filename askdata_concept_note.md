# AskData — Conversational Text-to-SQL & Insights Agent

*Concept note for internal development at Axis Bank*

---

## 1. The idea in one line

An AI agent that lets business owners and project teams ask questions about *their own project's data* in plain language (English or Hinglish). The agent converts the question into a database query, fetches the data, and returns the answer as a chart, table, or narrative — with no SQL, no BI developer, and no ticket to IT.

> Product owner of the Group Mobility platform: "How many applications came in last quarter, and how many converted, by subsidiary?"
> → Agent generates SQL → runs it on that project's database → returns a bar chart by subsidiary with a two-line summary.

The same agent, pointed at a different project's database, answers that project's questions.

---

## 2. The problem today

Every internal platform or project in the bank generates data, but the business owner of that project cannot query it directly. The path today:

1. Business / product owner needs a number, a trend, or a status on their own project.
2. Raises a request to the dev team, MIS, or IT.
3. A developer writes SQL, pulls an Excel or builds a dashboard, sends it back.
4. Turnaround: hours to days. Every follow-up question → repeat the loop.

Consequences:

- **Developer bandwidth is consumed by ad-hoc data pulls** instead of building features.
- **Business owners fly blind between reporting cycles** — decisions wait for the next MIS.
- **Dashboards answer yesterday's questions.** Any new question needs a new build.
- **Ownership of the project doesn't come with access to its data.** The owner knows the business logic best but can't touch the tables.

---

## 3. What the agent does

| Step | What happens |
|---|---|
| Understand | Parses the natural-language question, resolves business terms ("attrition", "NPA", "active customer") using a semantic layer / data dictionary. |
| Generate | Produces a validated, read-only SQL query against the connected schema. |
| Execute | Runs the query through a governed connector with the user's own access rights. |
| Explain | Shows the query in plain English so the user can verify the logic. |
| Visualize | Picks the right chart automatically (trend → line, comparison → bar, share → donut, detail → table) and adds a short narrative insight. |
| Iterate | Supports follow-ups in context: "now split this by gender", "compare with last year", "export to Excel". |

---

## 4. Why this is revolutionary inside Axis Bank

- **Business owners get direct, governed access to their own project's data.** The people who understand the business logic best can finally ask the questions themselves, without SQL.
- **Collapses the question-to-answer cycle from days to seconds.** Dev and MIS teams stop being a reporting bottleneck and go back to building.
- **Every project gets analytics on day one.** No need to build a bespoke dashboard per platform — connect the database, add the data dictionary, and the project has a conversational analytics layer.
- **One familiar interface across all internal projects.** A business owner who runs three platforms uses the same agent for all three.
- **Governance built in, not bolted on.** Scoped to the owner's own project data, read-only execution, masked PII, and a full audit log of every question and query.
- **It compounds.** Every question asked enriches that project's semantic layer (synonyms, metric definitions, common joins), so the agent gets better with usage.
- **It is a platform, not a project.** Built once, plugged into many systems.

---

## 5. Use cases — one agent, many projects

Each internal platform has a business owner with questions only that project's database can answer. Examples:

**HR platforms** (e.g., Group Mobility, Skills Framework, careers portal)
- "How many internal applications were raised this quarter, by subsidiary and status?"
- "Which skills are most frequently tagged but least available in the talent pool?"
- "Show the drop-off funnel from job view → application → shortlist for the last 90 days."

**Automation platforms** (e.g., RPA / workflow tools)
- "Which bots failed most often last week and at which step?"
- "Total hours saved by automation, by department, month-on-month."

**Customer-facing digital products**
- "Daily active users vs. transactions completed, last 30 days, by channel."
- "Top 10 failure reasons in the onboarding journey."

**Operations & service platforms**
- "Average TAT for each request category, and which ones breached SLA."
- "Complaint volume by category and branch, trend over 6 months."

**Any new internal project**
- The day the database exists, the business owner can start asking questions — no dashboard build required.

The questions differ; the agent, the governance, and the interface are the same.

---

## 6. Designed to be generic and pluggable

The core is database-agnostic. Onboarding a new system requires configuration, not code.

```
┌──────────────────────────────────────────────────────────────┐
│  Channels: Web chat UI · MS Teams bot · REST API · Embed SDK │
├──────────────────────────────────────────────────────────────┤
│  Agent Orchestrator (LangGraph state machine)                │
│  intent classifier → schema retrieval (RAG) → SQL generation │
│  → static validation → execution → self-correction loop      │
│  → visualization planner → narrative summarizer              │
├──────────────────────────────────────────────────────────────┤
│  Semantic Layer (per project, versioned)                     │
│  schema registry · data dictionary · metric definitions ·    │
│  synonyms · golden query bank · few-shot examples            │
├──────────────────────────────────────────────────────────────┤
│  Knowledge Store                                             │
│  Postgres (metadata, lineage, audit)  +  pgvector (embeddings)│
├──────────────────────────────────────────────────────────────┤
│  Governance & Guardrails                                     │
│  RBAC / row-level security · PII masking · read-only         │
│  execution · SQL AST validation · cost limits · audit log    │
├──────────────────────────────────────────────────────────────┤
│  Connector Layer (SQLAlchemy dialects)                       │
│  Oracle · SQL Server · PostgreSQL · MySQL · Snowflake /       │
│  data lake · REST / API sources                              │
└──────────────────────────────────────────────────────────────┘
```

**To onboard a new project:**
1. Register a read-only connection to the project's database.
2. Run the schema crawler; the data dictionary is auto-generated and the project team enriches it with business synonyms and metric definitions.
3. Map the project's business owners and their access scope.
4. Go live — no UI or agent changes required. The project team maintains its own semantic layer.

**Key design principles**
- Read-only by default; write operations never generated, and rejected at the AST level if they ever are.
- Every query is validated (syntax, allowed tables, row limits, cost estimate) before execution.
- Query and result are always shown alongside the chart for transparency.
- Model-agnostic: works with on-prem open-weight LLMs or approved cloud LLMs inside the bank's tenancy; no data leaves the bank boundary.
- Feedback loop: thumbs up/down on answers feeds the golden query bank and re-ranks retrieval.

---

## 7. Core technology stack

| Layer | Technology | Why |
|---|---|---|
| LLM (SQL generation, summarization) | Open-weight model served on-prem via **vLLM** (e.g., Qwen2.5-Coder / Llama-class 30–70B) — or an approved enterprise LLM within the bank's cloud tenancy | Strong code/SQL generation, full data residency, swappable behind a single interface |
| Intent classifier | Lightweight fine-tuned encoder (**DeBERTa / DistilBERT**) with LLM fallback for low-confidence cases | Sub-100 ms routing; keeps the big model out of trivial turns |
| Embeddings | **BGE-M3** or **e5-large** (multilingual, handles Hinglish) | Schema and question text embedded in the same space; open-weight, on-prem |
| Vector database | **pgvector** on PostgreSQL (recommended) — **Milvus** or **Qdrant** if scale exceeds ~10M vectors | Keeps metadata, vectors, and audit in one transactional store; HNSW index; already a supported DB in the bank; no new infra to certify |
| Agent orchestration | **LangGraph** (stateful multi-step graph with retries and branches) | Explicit control flow for validate → execute → self-correct loops |
| SQL parsing & guardrails | **sqlglot** (dialect-aware AST parsing/transpilation) | Block DML/DDL, enforce table allow-lists, inject row limits, rewrite across dialects |
| Database connectivity | **SQLAlchemy** + native drivers | One connector abstraction for Oracle, SQL Server, Postgres, MySQL, Snowflake |
| Visualization | **Vega-Lite** spec generated by the LLM, rendered client-side (Plotly as fallback) | Declarative chart spec = deterministic, auditable, exportable |
| API & services | **FastAPI** (Python), containerized on the bank's Kubernetes / OpenShift | Standard, horizontally scalable |
| Caching | **Redis** (query result cache, session memory, rate limiting) | Repeated questions answered instantly; conversation context across turns |
| Observability | **OpenTelemetry** traces + **Langfuse** (LLM tracing, prompt versioning, eval datasets) | Every step of every answer is traceable and replayable |
| Evaluation | Golden query bank + automated **execution-accuracy** tests in CI | Accuracy measured on every prompt or model change, not guessed |

---

## 8. The semantic layer: how RAG makes text-to-SQL accurate

Text-to-SQL fails when the model doesn't know the schema, the business vocabulary, or the house conventions. We solve all three with **Retrieval-Augmented Generation over a curated schema knowledge base** — the LLM never sees the whole database; it sees only the handful of tables, columns, metrics and example queries relevant to the question.

### 8.1 What gets indexed

Each project's semantic layer is decomposed into typed, individually embedded documents:

| Document type | Content | Granularity |
|---|---|---|
| **Table card** | Table name, description, grain (one row = ?), row count, primary key, owner, tags | 1 per table |
| **Column card** | Column name, data type, description, sample values, enum/code mappings, PII flag, synonyms | 1 per column |
| **Relationship card** | FK / join paths (explicit and inferred), cardinality | 1 per join |
| **Metric definition** | Business metric → canonical SQL fragment (e.g., `conversion_rate = shortlisted / applied`) | 1 per metric |
| **Synonym map** | Business terms → columns/values ("subsidiary", "sub", "entity" → `org_entity_cd`) | 1 per term |
| **Golden query** | Verified NL question ↔ SQL pair, tagged by tables used | 1 per example |

Every document carries structured metadata (`project_id`, `table`, `doc_type`, `schema_version`, `last_verified`) so retrieval can be filtered before similarity search.

### 8.2 Storage

- **Schema registry (Postgres):** authoritative, versioned copy of every crawled schema — tables, columns, constraints, DDL hash, timestamps. This is the source of truth; the vector index is derived from it.
- **Vector index (pgvector, HNSW):** one embedding per document above, partitioned by `project_id`. Hybrid retrieval combines vector similarity with **BM25 keyword search** (exact column names matter) and a **cross-encoder re-ranker** on the top-k.
- **Golden query bank (Postgres):** verified NL↔SQL pairs with execution results, used for both few-shot retrieval and regression testing.

### 8.3 The retrieval-to-SQL pipeline

```
user question
   │
   ▼
[Intent classifier] ── data_question / follow_up / clarify / out_of_scope / export
   │
   ▼
[Query rewriter] ── resolves "this", "last quarter", "same but by gender" using session memory
   │
   ▼
[Hybrid retrieval] ── vector + BM25, filtered by project_id → top-k tables/columns/metrics/golden queries
   │
   ▼
[Schema linker] ── expands to required join paths via relationship cards; prunes irrelevant columns
   │
   ▼
[SQL generator (LLM)] ── prompt = pruned schema + metrics + 3–5 nearest golden queries + dialect + house rules
   │
   ▼
[Static validator (sqlglot)] ── parse → block DML/DDL → allow-list tables → inject LIMIT → cost estimate
   │
   ▼
[Execute (read-only role)] ── on error → feed error back to LLM → regenerate (max 2 retries)
   │
   ▼
[Result validator] ── empty / suspicious result → ask clarifying question instead of guessing
   │
   ▼
[Viz planner + narrative] ── chart type from result shape (time-series → line, categorical → bar,
                             single value → KPI card, >2 dims → pivot table) → Vega-Lite spec + 2-line insight
```

### 8.4 Intent classification

A small fine-tuned classifier routes every turn before the LLM is invoked:

- `data_question` → full pipeline
- `follow_up` → reuse previous SQL as context, modify rather than regenerate
- `clarification_needed` → ambiguity detected (e.g., two "status" columns) → ask, don't guess
- `export / action` → deterministic handler (Excel, share, schedule)
- `out_of_scope` → politely decline (questions about other projects, non-data chit-chat, prompt-injection attempts)

Training data: a few hundred labelled utterances per project seeded during onboarding, grown continuously from real usage and thumbs-down feedback.

### 8.5 "Training" the RAG — how the knowledge base gets built and improves

There is no fine-tuning of the base LLM in phase 1. Accuracy comes from the **quality of the retrieved context**, which we build in layers:

1. **Automatic crawl:** `INFORMATION_SCHEMA` / catalog views → table & column cards, FK relationships, sample values, row counts.
2. **LLM-assisted enrichment:** the LLM drafts descriptions for undocumented tables/columns from names, samples and existing queries in logs; project owners review and approve.
3. **Human curation:** project team adds synonyms, metric definitions, and 20–50 golden NL↔SQL pairs covering their most common questions.
4. **Query-log mining:** existing reporting SQL (dashboards, MIS extracts) is parsed with sqlglot to infer join paths and common filters.
5. **Continuous learning:** every thumbs-up answer becomes a candidate golden query; thumbs-down answers go to a review queue where the owner corrects the SQL — the corrected pair is then indexed. Retrieval gets sharper with every question asked.
6. **Optional (phase 3):** LoRA fine-tune of the SQL generator on the bank's accumulated golden query bank for dialect-specific idioms.

### 8.6 Keeping the index in sync when schemas change

Schema drift is the #1 silent killer of text-to-SQL. We treat the index as a **derived artifact of the schema registry** and keep it in sync automatically:

| Event | Detection | Action |
|---|---|---|
| **New table added** | Scheduled crawler (e.g., every 6 hrs) diffs catalog against registry; or DDL trigger / CDC event where the DB supports it | Create table + column cards, auto-draft descriptions, embed, mark `unverified`, notify project owner for enrichment |
| **Column added / renamed / type changed** | Per-table **DDL hash** comparison | Re-embed only the affected cards (incremental upsert, not full rebuild); renamed columns keep synonym history so old questions still resolve |
| **Table / column dropped** | Missing in crawl | Soft-delete cards, tombstone in index, flag golden queries that reference them for review |
| **Data drift (new enum values, new code mappings)** | Sample-value profiling on crawl | Update column card sample values; refresh synonym map |
| **Metric or synonym edited by project owner** | Semantic-layer UI save event | Re-embed that document immediately; bump `schema_version` |
| **Golden query invalidated** | Nightly execution-accuracy regression run against live DB | Failing queries quarantined from few-shot retrieval until fixed |

Design choices that make this safe:

- **Versioned schema registry:** every crawl produces a new `schema_version`; the index stores the version on each document, so a query can always be replayed against the schema it was generated for.
- **Incremental upserts:** embeddings are keyed by a stable `doc_id` (`project.table.column`), so only changed documents are re-embedded — a 500-table schema with one new column re-embeds one document, not 5,000.
- **Verified vs. unverified tiers:** auto-generated cards are retrievable but ranked lower until a human verifies them; the agent tells the user when it has relied on unverified metadata.
- **Regression gate:** golden query bank runs in CI on every schema version bump and every prompt/model change; accuracy drops block the release.

---

## 9. Suggested rollout

| Phase | Scope | Outcome |
|---|---|---|
| Pilot (6–8 weeks) | One internal platform, its database, and its business owners (5–10 users) | Prove accuracy, governance, and that owners actually use it |
| Expand | 2–3 more projects across different tech stacks, Teams integration | Validate the pluggable model on unrelated schemas |
| Platform | Self-serve project onboarding portal, usage analytics, shared connector library | Any new internal project gets conversational analytics by default |

---

## 10. Success metrics

- Time from question to answer (target: minutes → seconds)
- % of ad-hoc data requests deflected from dev / MIS teams
- Query accuracy rate (validated by project owners)
- Weekly active business owners and questions per project
- Number of projects onboarded per quarter, and time to onboard each

---

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Wrong SQL / misleading answer | RAG-grounded generation; sqlglot AST validation; execution-error self-correction; query shown in plain English; confidence score; golden-query regression in CI |
| Data leakage | User-level RBAC and row-level security, PII masking at the column-card level, on-prem LLM — no data leaves bank infrastructure |
| Ambiguous business terms | Curated synonym map and metric definitions per project; intent classifier routes to clarification instead of guessing |
| Schema drift breaking answers | Versioned schema registry, incremental re-indexing, nightly golden-query regression, unverified-metadata warnings |
| Prompt injection via user input | Intent classifier `out_of_scope` gate; LLM output constrained to SQL + Vega-Lite spec; AST-level block on anything non-SELECT |
| Runaway queries | LIMIT injection, statement timeouts, cost estimation before execution, read-only replica where available |

---

*Bottom line: a RAG-grounded, governed text-to-SQL agent that gives every internal project a conversational analytics layer for its business owners — built once, plugged into any database, and self-maintaining as schemas evolve.*
