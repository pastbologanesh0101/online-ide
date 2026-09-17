"""
app.py
======

Flask routes for the Online IDE. All actual code-execution logic lives in
sandbox.py (kept separate so it's independently importable/testable); all
snippet persistence lives in db.py. This module just wires HTTP <-> those
two modules.
"""

from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request

import db
import sandbox

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.environ.get("ONLINE_IDE_DB_PATH", os.path.join(BASE_DIR, "snippets.db"))

# Hard ceiling a client can never exceed, regardless of what they request.
MAX_ALLOWED_TIMEOUT = 15


def create_app(db_path: str = DB_PATH) -> Flask:
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path
    db.init_db(db_path)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/run", methods=["POST"])
    def run_code():
        payload = request.get_json(silent=True) or {}
        source_code = payload.get("source_code", "")
        stdin_input = payload.get("stdin", "") or ""
        requested_timeout = payload.get("timeout", sandbox.DEFAULT_TIMEOUT_SECONDS)

        if not isinstance(source_code, str) or not source_code.strip():
            return jsonify({"error": "source_code must be a non-empty string"}), 400

        try:
            timeout = int(requested_timeout)
        except (TypeError, ValueError):
            timeout = sandbox.DEFAULT_TIMEOUT_SECONDS
        timeout = max(1, min(timeout, MAX_ALLOWED_TIMEOUT))

        result = sandbox.run_python_code(
            source_code=source_code,
            stdin_input=stdin_input,
            timeout=timeout,
        )
        return jsonify(result.to_dict())

    @app.route("/api/snippets", methods=["GET"])
    def api_list_snippets():
        return jsonify(db.list_snippets(app.config["DB_PATH"]))

    @app.route("/api/snippets", methods=["POST"])
    def api_save_snippet():
        payload = request.get_json(silent=True) or {}
        name = payload.get("name", "")
        source_code = payload.get("source_code", "")

        if not isinstance(name, str) or not name.strip():
            return jsonify({"error": "name must be a non-empty string"}), 400
        if not isinstance(source_code, str):
            return jsonify({"error": "source_code must be a string"}), 400

        db.save_snippet(name.strip(), source_code, app.config["DB_PATH"])
        return jsonify({"status": "saved", "name": name.strip()})

    @app.route("/api/snippets/<name>", methods=["GET"])
    def api_load_snippet(name: str):
        source_code = db.load_snippet(name, app.config["DB_PATH"])
        if source_code is None:
            return jsonify({"error": f"snippet '{name}' not found"}), 404
        return jsonify({"name": name, "source_code": source_code})

    @app.route("/api/snippets/<name>", methods=["DELETE"])
    def api_delete_snippet(name: str):
        deleted = db.delete_snippet(name, app.config["DB_PATH"])
        if not deleted:
            return jsonify({"error": f"snippet '{name}' not found"}), 404
        return jsonify({"status": "deleted", "name": name})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
