"""Local web interface for AskData, served from the same process as its API."""
import json
import logging
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse

from askdata import pipeline
from askdata.config import DB_PATH, OFFLINE_MODE, PROJECT_ROOT

STATIC_DIR = Path(__file__).resolve().parent / "static"
CHART_DIR = PROJECT_ROOT / "charts"
MAX_REQUEST_BYTES = 1_000_000


class AskDataHandler(BaseHTTPRequestHandler):
    server_version = "AskData/1.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send_file(STATIC_DIR / "index.html")
        elif path == "/static/app.js":
            self._send_file(STATIC_DIR / "app.js")
        elif path == "/static/styles.css":
            self._send_file(STATIC_DIR / "styles.css")
        elif path.startswith("/charts/"):
            self._send_chart(path.removeprefix("/charts/"))
        elif path == "/api/status":
            self._send_json(
                200,
                {
                    "status": "ok",
                    "offline_mode": OFFLINE_MODE,
                },
            )
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/ask":
            self._send_json(404, {"error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "Invalid Content-Length header"})
            return
        if content_length <= 0:
            self._send_json(400, {"error": "Request body is required"})
            return
        if content_length > MAX_REQUEST_BYTES:
            self._send_json(413, {"error": "Request body is too large"})
            return

        try:
            payload = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "Request body must be valid JSON"})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "Request body must be a JSON object"})
            return

        question = payload.get("question")
        if not isinstance(question, str) or not question.strip():
            self._send_json(400, {"error": "Enter a question before submitting"})
            return
        previous_sql = payload.get("previous_sql")
        if previous_sql is not None and not isinstance(previous_sql, str):
            self._send_json(400, {"error": "previous_sql must be a string"})
            return

        started = perf_counter()
        try:
            result = pipeline.ask(question.strip(), previous_sql=previous_sql)
        except Exception as error:
            logging.exception("AskData request failed")
            self._send_json(500, {"error": f"Question could not be processed: {error}"})
            return

        dataframe = result.df
        rows = (
            json.loads(dataframe.to_json(orient="records", date_format="iso"))
            if dataframe is not None
            else []
        )
        chart_url = None
        if result.chart_path:
            chart_path = Path(result.chart_path).resolve()
            if chart_path.parent == CHART_DIR.resolve() and chart_path.is_file():
                chart_url = f"/charts/{chart_path.name}"

        duration_ms = round((perf_counter() - started) * 1000, 1)
        self._send_json(
            200,
            {
                "status": result.status,
                "question": question.strip(),
                "sql": result.sql,
                "rows": rows,
                "columns": list(dataframe.columns) if dataframe is not None else [],
                "narrative": result.narrative,
                "message": result.message,
                "note": result.note,
                "chart_url": chart_url,
                "metrics": {
                    "row_count": len(rows),
                    "column_count": len(dataframe.columns) if dataframe is not None else 0,
                    "duration_ms": duration_ms,
                },
            },
        )

    def _send_chart(self, filename: str) -> None:
        if not filename.startswith("chart_") or Path(filename).name != filename:
            self._send_json(404, {"error": "Chart not found"})
            return
        chart_path = (CHART_DIR / filename).resolve()
        if chart_path.parent != CHART_DIR.resolve() or not chart_path.is_file():
            self._send_json(404, {"error": "Chart not found"})
            return
        self._send_file(chart_path)

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self._send_json(404, {"error": "Not found"})
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        logging.info("%s - %s", self.address_string(), format % args)


def main() -> None:
    if not Path(DB_PATH).exists():
        raise SystemExit(
            f"Sample database not found at {DB_PATH}. "
            "Run: python -m askdata.data.seed_db"
        )

    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), AskDataHandler)
    print(f"AskData UI listening on {host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAskData server stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
