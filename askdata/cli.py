"""AskData CLI REPL — conversational text-to-SQL prototype.

Run with: python -m askdata.cli
"""
import sys

from askdata import exporter, pipeline
from askdata.config import DB_PATH, OFFLINE_MODE
from pathlib import Path

FOLLOW_UP_KEYWORDS = ("this", "that", "same", "split", "also", "now", "instead", "compare", "again")

WELCOME = """AskData prototype — ask questions about the sample Group Mobility data in plain English.
Type 'exit' or 'quit' to leave.

Example questions:
  How many applications came in last quarter, and how many joined, by subsidiary?
  now split this by gender
  Show the number of applications at each stage of the funnel for the last 90 days.
  How many applications are there in total?
  What is the overall conversion rate?
  How many interview rounds ended in a reject, by subsidiary?
  How many candidates are offered but have not yet joined?
  What is the offer-to-join rate?
"""

OFFLINE_BANNER = """[offline demo mode] No GEMINI_API_KEY set — running with rule-based
SQL matching against the golden-query bank instead of a real LLM. The
guardrails, execution, chart, and follow-up logic are all real; only SQL
generation and the narrative are stubbed. Add a key to .env for real NL->SQL.
Stick close to the example questions above; anything else will say it
couldn't match.
"""


def looks_like_follow_up(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in FOLLOW_UP_KEYWORDS)


def _prompt_yes_no(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def maybe_export_to_excel(result: pipeline.AnswerResult, question: str) -> None:
    if result.df is None or result.df.empty:
        return
    if not _prompt_yes_no("Save this result to Excel? [y/N]: "):
        return

    if _prompt_yes_no("Use a specific Excel template? [y/N]: "):
        try:
            template_path = input("Template file path: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not template_path:
            print("No template path given, skipping export.\n")
            return
        export = exporter.export_with_template(result.df, template_path, question)
    else:
        export = exporter.export_plain(result.df, question)

    if export.ok:
        print(f"Saved to: {export.path}\n")
    else:
        print(f"[export failed] {export.error}\n")


def print_result(result: pipeline.AnswerResult) -> None:
    if result.status == "refused":
        print(f"\n[refused] {result.message}\n")
        return
    if result.status == "unmatched":
        print(f"\n[unmatched] {result.message}\n")
        return
    if result.status == "blocked":
        print(f"\n[blocked] {result.message}")
        print(f"Generated SQL:\n{result.sql}\n")
        return
    if result.status == "error":
        print(f"\n[error] {result.message}")
        if result.sql:
            print(f"Last attempted SQL:\n{result.sql}\n")
        return

    if result.note:
        print(f"\n[{result.note}]")
    print(f"\nSQL:\n{result.sql}\n")
    df = result.df
    if df is not None:
        print(df.to_string(index=False, max_rows=20))
    if result.chart_path:
        print(f"\nChart saved to: {result.chart_path}")
    if result.narrative:
        print(f"\nInsight: {result.narrative}")
    print()


def main() -> None:
    if not Path(DB_PATH).exists():
        print(f"Sample database not found at {DB_PATH}. Run: python -m askdata.data.seed_db", file=sys.stderr)
        sys.exit(1)

    print(WELCOME)
    if OFFLINE_MODE:
        print(OFFLINE_BANNER)
    last_sql = None
    while True:
        try:
            question = input("ask> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in ("exit", "quit"):
            break

        previous_sql = last_sql if looks_like_follow_up(question) else None
        result = pipeline.ask(question, previous_sql=previous_sql)
        print_result(result)
        if result.status == "ok":
            last_sql = result.sql
            maybe_export_to_excel(result, question)


if __name__ == "__main__":
    main()
