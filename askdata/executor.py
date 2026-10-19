"""Executes a validated SQL query against a read-only connection to the sample DB
(concept note section 3 "Execute" step)."""
import sqlite3
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from askdata.config import DB_PATH


@dataclass
class ExecutionResult:
    ok: bool
    df: Optional[pd.DataFrame] = None
    error: Optional[str] = None


def execute(sql: str) -> ExecutionResult:
    uri = f"file:{DB_PATH}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        try:
            df = pd.read_sql_query(sql, conn)
        finally:
            conn.close()
        return ExecutionResult(ok=True, df=df)
    except Exception as e:
        return ExecutionResult(ok=False, error=str(e))
