"""Exports a query result to Excel (concept note section 3 "Iterate": "export to Excel").

Two modes:
- export_plain: writes the DataFrame to a fresh .xlsx file.
- export_with_template: opens a user-supplied .xlsx template and writes the DataFrame's
  values into its first sheet (or a named sheet) starting at a given cell, preserving
  whatever formatting/headers/other sheets the template already has.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from openpyxl import load_workbook

from askdata.config import PROJECT_ROOT

EXPORTS_DIR = PROJECT_ROOT / "exports"


@dataclass
class ExportResult:
    ok: bool
    path: Optional[str] = None
    error: Optional[str] = None


def _default_path(question: str) -> Path:
    EXPORTS_DIR.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", question.lower()).strip("_")[:50] or "result"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return EXPORTS_DIR / f"{timestamp}_{slug}.xlsx"


def export_plain(df: pd.DataFrame, question: str) -> ExportResult:
    path = _default_path(question)
    try:
        df.to_excel(path, index=False)
        return ExportResult(ok=True, path=str(path))
    except Exception as e:
        return ExportResult(ok=False, error=str(e))


def export_with_template(
    df: pd.DataFrame,
    template_path: str,
    question: str,
    sheet_name: Optional[str] = None,
    start_row: int = 2,
    start_col: int = 1,
) -> ExportResult:
    template = Path(template_path).expanduser()
    if not template.exists():
        return ExportResult(ok=False, error=f"Template not found: {template}")
    if template.suffix.lower() not in (".xlsx", ".xltx", ".xlsm"):
        return ExportResult(ok=False, error="Template must be an .xlsx/.xlsm/.xltx file.")

    try:
        wb = load_workbook(template)
    except Exception as e:
        return ExportResult(ok=False, error=f"Couldn't open template: {e}")

    if sheet_name and sheet_name not in wb.sheetnames:
        return ExportResult(
            ok=False,
            error=f"Template has no sheet named '{sheet_name}'. Available: {wb.sheetnames}",
        )
    ws = wb[sheet_name] if sheet_name else wb.active

    for r_offset, row in enumerate(df.itertuples(index=False)):
        for c_offset, value in enumerate(row):
            ws.cell(row=start_row + r_offset, column=start_col + c_offset, value=value)

    path = _default_path(question)
    try:
        wb.save(path)
        return ExportResult(ok=True, path=str(path))
    except Exception as e:
        return ExportResult(ok=False, error=f"Couldn't save output: {e}")
