import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from askdata.pipeline import AnswerResult
from askdata import web
from askdata import config
from askdata.web import AskDataHandler


class WebServerTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), AskDataHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.pipeline_patch = patch("askdata.web.pipeline.ask")
        self.ask = self.pipeline_patch.start()
        self.connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_address[1]
        )

    def tearDown(self):
        self.connection.close()
        self.pipeline_patch.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request_json(self, path, payload):
        body = json.dumps(payload)
        self.connection.request(
            "POST",
            path,
            body=body,
            headers={"Content-Type": "application/json"},
        )
        response = self.connection.getresponse()
        return response.status, json.loads(response.read())

    def test_serves_dashboard_and_status_from_same_server(self):
        self.connection.request("GET", "/")
        page = self.connection.getresponse()
        self.assertEqual(page.status, 200)
        self.assertIn(b"Latest answer", page.read())

        self.connection.request("GET", "/api/status")
        status = self.connection.getresponse()
        self.assertEqual(status.status, 200)
        self.assertEqual(json.loads(status.read())["status"], "ok")

    def test_question_response_contains_rows_and_metrics(self):
        self.ask.return_value = AnswerResult(
            status="ok",
            sql="SELECT subsidiary, COUNT(*) AS applications FROM applications",
            df=pd.DataFrame([{"subsidiary": "North", "applications": 3}]),
            narrative="North has 3 applications.",
        )

        status, response = self.request_json(
            "/api/ask",
            {"question": "How many applications are there?", "previous_sql": None},
        )

        self.assertEqual(status, 200)
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["rows"][0]["applications"], 3)
        self.assertEqual(response["metrics"]["row_count"], 1)
        self.assertEqual(response["metrics"]["column_count"], 2)
        self.assertGreaterEqual(response["metrics"]["duration_ms"], 0)

    def test_rejects_empty_question(self):
        status, response = self.request_json("/api/ask", {"question": " "})
        self.assertEqual(status, 400)
        self.assertIn("question", response["error"].lower())
        self.ask.assert_not_called()

    def test_returns_and_serves_generated_chart(self):
        with tempfile.TemporaryDirectory() as directory:
            chart_dir = Path(directory)
            chart_path = chart_dir / "chart_test.png"
            chart_path.write_bytes(b"png")
            self.ask.return_value = AnswerResult(
                status="ok",
                sql="SELECT subsidiary FROM applications",
                df=pd.DataFrame([{"subsidiary": "North"}]),
                chart_path=str(chart_path),
            )

            with patch("askdata.web.CHART_DIR", chart_dir):
                status, response = self.request_json(
                    "/api/ask", {"question": "Show applications by subsidiary"}
                )
                self.assertEqual(status, 200)
                self.assertEqual(response["chart_url"], "/charts/chart_test.png")

                self.connection.request("GET", response["chart_url"])
                chart = self.connection.getresponse()
                self.assertEqual(chart.status, 200)
                self.assertEqual(chart.read(), b"png")

    def test_unknown_chart_path_is_not_served(self):
        self.connection.request("GET", "/charts/../../README.md")
        response = self.connection.getresponse()
        self.assertEqual(response.status, 404)

    def test_server_binds_to_render_host_and_port(self):
        server = Mock()
        with patch.dict(os.environ, {"PORT": "10000"}):
            with patch.object(web, "ThreadingHTTPServer", return_value=server) as create_server:
                web.main()

        create_server.assert_called_once_with(("0.0.0.0", 10000), AskDataHandler)
        server.serve_forever.assert_called_once()
        server.server_close.assert_called_once()

    def test_model_name_must_come_from_environment_configuration(self):
        with patch.object(config, "MODEL_NAME", "gemini-test-model"):
            self.assertEqual(config.get_model_name(), "gemini-test-model")

        with patch.object(config, "MODEL_NAME", ""):
            with self.assertRaisesRegex(RuntimeError, "ASKDATA_MODEL"):
                config.get_model_name()


if __name__ == "__main__":
    unittest.main()
