"""Picks a chart type from the result's shape and renders it to a PNG
(concept note section 3/8.3 "Viz planner": time-series -> line, categorical -> bar,
single value -> KPI, otherwise -> table only)."""
import re
import uuid
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from askdata.config import PROJECT_ROOT

OUTPUT_DIR = PROJECT_ROOT / "charts"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _is_date_series(series: pd.Series) -> bool:
    if series.dtype == object:
        sample = series.dropna().astype(str).head(5)
        return bool(len(sample)) and all(DATE_RE.match(v) for v in sample)
    return False


def render(df: pd.DataFrame) -> Optional[str]:
    """Returns a path to a saved PNG, or None if a table-only view is more appropriate."""
    if df.empty:
        return None

    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    non_numeric_cols = [c for c in df.columns if c not in numeric_cols]

    if len(df) == 1 and len(df.columns) <= 3:
        return None  # single-row KPI: printed as text, no chart needed

    if not numeric_cols or not non_numeric_cols:
        return None  # nothing sensible to plot; leave it as a table

    OUTPUT_DIR.mkdir(exist_ok=True)
    label_col = non_numeric_cols[0]
    value_cols = numeric_cols[:3]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    if len(df) > 1 and _is_date_series(df[label_col]):
        x = pd.to_datetime(df[label_col])
        for col in value_cols:
            ax.plot(x, df[col], marker="o", label=col)
        ax.set_xlabel(label_col)
        fig.autofmt_xdate()
    else:
        x = range(len(df))
        width = 0.8 / max(len(value_cols), 1)
        for i, col in enumerate(value_cols):
            ax.bar([xi + i * width for xi in x], df[col], width=width, label=col)
        ax.set_xticks([xi + width * (len(value_cols) - 1) / 2 for xi in x])
        ax.set_xticklabels(df[label_col].astype(str), rotation=30, ha="right")

    ax.legend()
    ax.set_ylabel(", ".join(value_cols))
    fig.tight_layout()

    out_path = OUTPUT_DIR / f"chart_{uuid.uuid4().hex[:8]}.png"
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return str(out_path)
