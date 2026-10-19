"""Orchestrates one question end-to-end (concept note section 8.3):
generate -> validate -> execute -> self-correct on error (max N retries) -> summarize -> chart.
"""
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from askdata import chart, executor, sql_generator, summarizer, validator
from askdata.config import MAX_SELF_CORRECTION_RETRIES


@dataclass
class AnswerResult:
    status: str  # "ok" | "refused" | "unmatched" | "blocked" | "error"
    sql: Optional[str] = None
    df: Optional[pd.DataFrame] = None
    narrative: Optional[str] = None
    chart_path: Optional[str] = None
    message: Optional[str] = None
    note: Optional[str] = None


def ask(question: str, previous_sql: Optional[str] = None) -> AnswerResult:
    error_feedback = None
    last_error = None
    last_sql = None

    for attempt in range(MAX_SELF_CORRECTION_RETRIES + 1):
        gen = sql_generator.generate_sql(
            question, previous_sql=previous_sql, error_feedback=error_feedback
        )
        if gen.refused:
            return AnswerResult(status="refused", message="This looks like a write/action request. AskData is read-only and can't do that.")
        if gen.unmatched:
            return AnswerResult(status="unmatched", message=gen.note)

        validation = validator.validate(gen.sql)
        if not validation.ok:
            return AnswerResult(
                status="blocked",
                sql=gen.sql,
                message=f"Guardrail blocked this query: {validation.error}",
            )

        last_sql = validation.sql
        exec_result = executor.execute(validation.sql)
        if exec_result.ok:
            df = exec_result.df
            narrative = summarizer.summarize(question, df)
            chart_path = chart.render(df)
            return AnswerResult(
                status="ok", sql=validation.sql, df=df, narrative=narrative,
                chart_path=chart_path, note=gen.note,
            )

        last_error = exec_result.error
        error_feedback = last_error

    return AnswerResult(
        status="error",
        sql=last_sql,
        message=f"Query failed after {MAX_SELF_CORRECTION_RETRIES} self-correction attempts: {last_error}",
    )
