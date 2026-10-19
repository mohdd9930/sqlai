
"""Turns a natural-language question into a SQLite SELECT query
using Google Gemini, with a rule-based offline fallback.
"""
import re
from dataclasses import dataclass
from typing import Optional

import sqlglot
from google import genai
from google.genai import types

from askdata.config import GEMINI_API_KEY, MODEL_NAME, OFFLINE_MODE
from askdata.schema_context import build_prompt_context, load_semantic_layer

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


SYSTEM_PROMPT = """You are AskData, a text-to-SQL agent for an internal bank platform.
You translate a business user's question into a single read-only SQLite SELECT query.

Rules:
- Output ONLY the SQL query. No markdown fences, no commentary, no explanation.
- Use only the tables and columns given in the schema context below.
- Never generate INSERT, UPDATE, DELETE, DROP, ALTER, or any other write/DDL statement.
- Requests to show, list, find, count, or retrieve information are read-only, even
  when they ask for sensitive-sounding fields such as phone numbers.
  Refuse only when the user explicitly asks to change, add, or delete database data.
  In that case respond with exactly: REFUSE: read-only agent
- If the user asks for information that cannot be answered using the provided
  tables and columns, respond with: UNMATCHED: followed by a brief explanation
  of which requested information is unavailable. Never invent columns or values.
- Treat "hired" as applications whose stage is 'joined'.
- Prefer explicit JOINs and column aliases that match the question's wording.
- Always qualify ambiguous columns with the table name.
- If the question is a follow-up, the previous SQL is given — modify it rather than
  starting over, unless the follow-up clearly needs a different query.

Schema context:
{schema_context}
"""


@dataclass
class GenerationResult:
    sql: str
    refused: bool
    unmatched: bool = False
    note: Optional[str] = None


def generate_sql(
    question: str,
    previous_sql: Optional[str] = None,
    error_feedback: Optional[str] = None,
) -> GenerationResult:
    if OFFLINE_MODE:
        return _generate_sql_offline(question, previous_sql)

    client = _get_client()
    system = SYSTEM_PROMPT.format(schema_context=build_prompt_context())

    user_parts = []
    if previous_sql:
        user_parts.append(
            f"Previous SQL (this is a follow-up question):\n{previous_sql}"
        )
    if error_feedback:
        user_parts.append(
            f"The previous attempt failed to execute with this error:\n"
            f"{error_feedback}\nFix the query."
        )
    user_parts.append(f"Question: {question}")

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents="\n\n".join(user_parts),
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
            max_output_tokens=1024,
        ),
    )

    text = (response.text or "").strip()

    if text.upper().startswith("REFUSE"):
        return GenerationResult(sql="", refused=True)
    if text.upper().startswith("UNMATCHED:"):
        return GenerationResult(
            sql="",
            refused=False,
            unmatched=True,
            note=text[len("UNMATCHED:"):].strip(),
        )

    sql = _strip_markdown_fences(text)
    return GenerationResult(sql=sql, refused=False)


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


# --- Offline demo mode -------------------------------------------------------

_STOPWORDS = {
    "a", "an", "the", "is", "are", "of", "in", "by", "and", "for", "to", "on",
    "this", "that", "now", "please", "show", "what", "how", "many", "much",
    "last", "give", "me", "with", "split",
}

_DIMENSION_COLUMNS = {
    "gender": "gender",
    "sex": "gender",
    "department": "department",
    "dept": "department",
}


def _tokenize(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _best_golden_match(question: str, golden_queries: list) -> tuple:
    q_tokens = _tokenize(question)
    best, best_score = None, 0.0
    for gq in golden_queries:
        g_tokens = _tokenize(gq["question"])
        if not g_tokens:
            continue
        score = len(q_tokens & g_tokens) / len(g_tokens)
        if score > best_score:
            best, best_score = gq, score
    return best, best_score


def _detect_dimension(question: str) -> Optional[str]:
    q = question.lower()
    for keyword, column in _DIMENSION_COLUMNS.items():
        if re.search(r"\b" + re.escape(keyword) + r"\b", q):
            return column
    return None


def _add_dimension_breakdown(sql: str, column: str) -> str:
    """Rewrites a query joined on applications to group by employees.<column>."""
    from sqlglot import exp

    parsed = sqlglot.parse_one(sql, read="sqlite")
    if not isinstance(parsed, exp.Select):
        raise ValueError("can only add a breakdown to a plain SELECT")

    tables = {t.name.lower(): t.alias_or_name for t in parsed.find_all(exp.Table)}
    app_alias = tables.get("applications")
    if app_alias is None:
        raise ValueError("previous query does not reference applications")

    if "employees" not in tables:
        parsed = parsed.join(
            "employees AS e",
            on=f"{app_alias}.employee_id = e.id",
            join_type="inner",
        )
        emp_alias = "e"
    else:
        emp_alias = tables["employees"]

    parsed = parsed.select(f"{emp_alias}.{column}", append=True)
    parsed = parsed.group_by(f"{emp_alias}.{column}", append=True)
    return parsed.sql(dialect="sqlite")


def _generate_sql_offline(
    question: str, previous_sql: Optional[str]
) -> GenerationResult:
    if any(
        re.search(r"\b" + re.escape(kw.strip()) + r"\b", question.lower())
        for kw in ("delete", "drop", "update", "insert", "truncate")
    ):
        return GenerationResult(sql="", refused=True)

    dimension = _detect_dimension(question)
    if previous_sql and dimension:
        try:
            sql = _add_dimension_breakdown(previous_sql, dimension)
            return GenerationResult(
                sql=sql,
                refused=False,
                note=f"Offline demo mode: added a breakdown by {dimension}.",
            )
        except Exception as e:
            return GenerationResult(
                sql="",
                refused=False,
                unmatched=True,
                note=f"Offline demo mode couldn't apply the breakdown: {e}",
            )

    golden_queries = load_semantic_layer().get("golden_queries", [])
    match, score = _best_golden_match(question, golden_queries)

    if match and score >= 0.35:
        return GenerationResult(
            sql=match["sql"].strip(),
            refused=False,
            note=f"Offline demo mode: matched golden query \"{match['question']}\"",
        )

    examples = "\n".join(f"  - {gq['question']}" for gq in golden_queries)
    return GenerationResult(
        sql="",
        refused=False,
        unmatched=True,
        note=(
            "Offline demo mode couldn't match this question to a known query "
            "(no GEMINI_API_KEY set). Try one of:\n"
            f"{examples}"
        ),
    )
