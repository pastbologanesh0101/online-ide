"""Integration tests for the Flask app, via Flask's test client."""

from __future__ import annotations

import os
import tempfile
import unittest

from app import create_app


class TestOnlineIdeApp(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.app = create_app(db_path=self.db_path)
        self.client = self.app.test_client()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_index_page_loads(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Online IDE", resp.data)

    def test_run_endpoint_executes_code_and_returns_stdout(self):
        resp = self.client.post(
            "/api/run", json={"source_code": "print('via flask')"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["exit_code"], 0)
        self.assertIn("via flask", data["stdout"])

    def test_run_endpoint_rejects_empty_source(self):
        resp = self.client.post("/api/run", json={"source_code": ""})
        self.assertEqual(resp.status_code, 400)

    def test_run_endpoint_reports_syntax_errors_without_crashing_server(self):
        resp = self.client.post("/api/run", json={"source_code": "def x(:\n"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertNotEqual(data["exit_code"], 0)
        self.assertIn("SyntaxError", data["stderr"])

    def test_snippet_save_and_load_round_trip_via_api(self):
        source = "print('round trip via http')"
        save_resp = self.client.post(
            "/api/snippets", json={"name": "http-snippet", "source_code": source}
        )
        self.assertEqual(save_resp.status_code, 200)

        load_resp = self.client.get("/api/snippets/http-snippet")
        self.assertEqual(load_resp.status_code, 200)
        self.assertEqual(load_resp.get_json()["source_code"], source)

    def test_load_nonexistent_snippet_returns_404(self):
        resp = self.client.get("/api/snippets/nope")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
