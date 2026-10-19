"""Turns a result set into a short plain-English narrative insight
(concept note section 3 "Explain"/"Visualize" narrative).

Falls back to a rule-based summary (no LLM call) when OFFLINE_MODE is on."""
from typing import Optional

import pandas as pd
from google import genai
from google.genai import types

from askdata.config import GEMINI_API_KEY, OFFLINE_MODE, get_model_name

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def summarize(question: str, df: pd.DataFrame) -> str:
    if df.empty:
        return "No rows matched this question."

    if OFFLINE_MODE:
        return _summarize_offline(df)

    model_name = get_model_name()
    preview = df.head(20).to_csv(index=False)
    prompt = (
        f"Question: {question}\n\n"
        f"Result (CSV, up to 20 rows shown, {len(df)} total):\n{preview}\n\n"
        "Write a 2-line plain-English insight summarizing this result for a business "
        "user. Be specific with numbers. No preamble, no markdown."
    )
    response = _get_client().models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=200,
        ),
    )
    return (response.text or "").strip()


def _summarize_offline(df: pd.DataFrame) -> str:
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

    if len(df) == 1:
        parts = [f"{c}={df.iloc[0][c]}" for c in df.columns]
        return "Result: " + ", ".join(parts) + ". (offline demo narrative — no LLM call)"

    lines = [f"Returned {len(df)} rows."]
    label_cols = [c for c in df.columns if c not in numeric_cols]
    if numeric_cols and label_cols:
        sort_col = numeric_cols[0]
        top_row = df.loc[df[sort_col].idxmax()]
        lines.append(f"Highest {sort_col}: {top_row[label_cols[0]]} ({top_row[sort_col]}).")
    lines.append("(offline demo narrative — no LLM call)")
    return " ".join(lines)
