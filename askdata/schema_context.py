"""Builds the schema/semantic-layer context passed to the LLM (concept note section 8.1/8.3).

In the full system this context would come from hybrid RAG retrieval (vector + BM25)
filtered to the tables relevant to the question. The prototype's schema is small
enough to pass in full every time, but this module is the seam where retrieval
would plug in later.
"""
from functools import lru_cache

import yaml

from askdata.config import SEMANTIC_LAYER_PATH


@lru_cache(maxsize=1)
def load_semantic_layer() -> dict:
    with open(SEMANTIC_LAYER_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def allowed_tables() -> list[str]:
    return [t["name"] for t in load_semantic_layer()["tables"]]


def build_prompt_context() -> str:
    """Renders the semantic layer into a compact text block for the LLM prompt."""
    layer = load_semantic_layer()
    lines: list[str] = []

    lines.append("## Tables")
    for table in layer["tables"]:
        lines.append(f"\n### {table['name']} — {table['description']} (grain: {table['grain']})")
        for col in table["columns"]:
            syns = col.get("synonyms")
            syn_str = f" [synonyms: {', '.join(syns)}]" if syns else ""
            enum = col.get("enum_values")
            enum_str = f" [values: {', '.join(enum)}]" if enum else ""
            lines.append(f"- {col['name']} ({col['type']}): {col['description']}{syn_str}{enum_str}")

    lines.append("\n## Relationships")
    for rel in layer.get("relationships", []):
        lines.append(f"- {rel['from']} -> {rel['to']} ({rel['cardinality']})")

    lines.append("\n## Metric definitions")
    for metric in layer.get("metrics", []):
        lines.append(f"- {metric['name']}: {metric['description']} => {metric['sql_fragment'].strip()}")

    lines.append("\n## Business term synonyms")
    for term, target in (layer.get("synonyms") or {}).items():
        if target:
            lines.append(f"- \"{term}\" -> {target}")

    lines.append("\n## Verified example questions (golden queries)")
    for gq in layer.get("golden_queries", []):
        lines.append(f"- Q: {gq['question']}\n  SQL: {gq['sql'].strip()}")

    return "\n".join(lines)
