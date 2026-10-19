"""Static SQL guardrails (concept note section 6/11): block DML/DDL, allow-list
tables, inject a row limit. Everything here runs before a query ever touches the
database, and it's the layer that makes a read-only agent actually read-only even
if the LLM tries to generate a write statement.
"""
from dataclasses import dataclass
from typing import Optional

import sqlglot
from sqlglot import exp

from askdata.config import DEFAULT_ROW_LIMIT
from askdata.schema_context import allowed_tables

DIALECT = "sqlite"


@dataclass
class ValidationResult:
    ok: bool
    sql: str = ""
    error: Optional[str] = None


def validate(sql: str) -> ValidationResult:
    sql = sql.strip().rstrip(";")
    if not sql:
        return ValidationResult(ok=False, error="Empty query.")

    try:
        parsed = sqlglot.parse_one(sql, read=DIALECT)
    except Exception as e:
        return ValidationResult(ok=False, error=f"SQL failed to parse: {e}")

    if not isinstance(parsed, (exp.Select, exp.Union)):
        return ValidationResult(
            ok=False,
            error=f"Only SELECT queries are allowed; got {type(parsed).__name__}.",
        )

    write_node_types = (
        exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter,
        exp.Create, exp.TruncateTable, exp.Merge,
    )
    if list(parsed.find_all(*write_node_types)):
        return ValidationResult(ok=False, error="Write/DDL statements are not permitted.")

    allowed = set(t.lower() for t in allowed_tables())
    used_tables = {t.name.lower() for t in parsed.find_all(exp.Table)}
    disallowed = used_tables - allowed
    if disallowed:
        return ValidationResult(
            ok=False,
            error=f"Query references tables outside the allow-list: {sorted(disallowed)}",
        )

    parsed = _inject_limit(parsed)
    return ValidationResult(ok=True, sql=parsed.sql(dialect=DIALECT))


def _inject_limit(parsed: exp.Expression) -> exp.Expression:
    target = parsed
    if isinstance(parsed, exp.Union):
        # Row-limit the overall result, not each branch.
        if parsed.args.get("limit") is None:
            parsed = parsed.limit(DEFAULT_ROW_LIMIT)
        return parsed

    existing_limit = target.args.get("limit")
    if existing_limit is None:
        target = target.limit(DEFAULT_ROW_LIMIT)
    return target
