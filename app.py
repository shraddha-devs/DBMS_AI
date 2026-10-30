"""Local Flask website for read-only natural-language SQLite questions."""

from __future__ import annotations

import logging
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, session

from database import (
    DATABASE_PATH,
    DatabaseUnavailable,
    connect_readonly,
    database_overview,
    readonly_error_message,
)
from query_engine import run_question
from response_generator import generate_answer


MAX_HISTORY = 12
MAX_REQUEST_SIZE = 16_384
UNSAFE_SQL_PATTERN = re.compile(
    r"(?:;\s*(?:select|insert|update|delete|drop|alter|create|attach|pragma)\b"
    r"|\b(?:drop|attach|pragma|vacuum)\s+(?:table|database|index|trigger)\b"
    r"|--|/\*)",
    re.IGNORECASE,
)

SUGGESTIONS = [
    {
        "practical": "Explore the data",
        "questions": [
            "Show all employees.",
            "What is the highest salary?",
            "Find employees working on the IoT project.",
            "What is the total salary in the Accounts department?",
        ],
    },
    {
        "practical": "Practical 1 · Transactions",
        "questions": [
            "Explain the rollback operation in Practical 1.",
            "Which columns have NOT NULL constraints?",
        ],
    },
    {
        "practical": "Practical 2 · Employees",
        "questions": [
            "Show all employees in Practical 2.",
            "What happened when employee 105 was deleted?",
        ],
    },
    {
        "practical": "Practical 3 · Company queries",
        "questions": [
            "Which projects involve Scott?",
            "Show employees working on all department 5 projects.",
            "Which departments have more than five employees?",
        ],
    },
    {
        "practical": "Practical 4 · Customer trigger",
        "questions": [
            "Show the latest customer salary audit records.",
            "What was the salary difference after the customer update?",
        ],
    },
    {
        "practical": "Practical 5 · Cursor",
        "questions": [
            "Display all cursor employee records.",
            "Who is the oldest cursor employee?",
        ],
    },
]


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
        DATABASE_PATH=str(DATABASE_PATH),
        MAX_CONTENT_LENGTH=MAX_REQUEST_SIZE,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    logging.basicConfig(level=logging.INFO)

    @contextmanager
    def database_connection():
        connection = connect_readonly(Path(app.config["DATABASE_PATH"]))
        try:
            yield connection
        finally:
            connection.close()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/database-status")
    def database_status():
        try:
            with database_connection() as connection:
                overview = database_overview(connection)
            return jsonify(
                {
                    "success": True,
                    "connected": True,
                    "database": Path(app.config["DATABASE_PATH"]).name,
                    "tables": overview["tables"],
                    "table_count": overview["table_count"],
                }
            )
        except (DatabaseUnavailable, sqlite3.Error):
            app.logger.exception("Database status lookup failed")
            return (
                jsonify(
                    {
                        "success": False,
                        "connected": False,
                        "database": Path(app.config["DATABASE_PATH"]).name,
                        "tables": [],
                        "table_count": 0,
                        "error": (
                            "The existing practicals database is unavailable. "
                            "Check that practicals.db is present and readable."
                        ),
                    }
                ),
                503,
            )

    @app.get("/api/suggestions")
    def suggestions():
        return jsonify({"success": True, "groups": SUGGESTIONS})

    @app.get("/api/history")
    def history():
        return jsonify({"success": True, "messages": session.get("messages", [])})

    @app.delete("/api/history")
    def clear_history():
        session.pop("messages", None)
        return jsonify({"success": True, "messages": []})

    @app.post("/api/chat")
    def chat():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"success": False, "error": "Send a JSON request."}), 400
        question = payload.get("question")
        if not isinstance(question, str):
            return jsonify(
                {"success": False, "error": "Enter a question as plain text."}
            ), 400
        question = question.strip()
        if not question:
            return jsonify(
                {"success": False, "error": "Type a question before sending."}
            ), 400
        if len(question) > 500:
            return jsonify(
                {
                    "success": False,
                    "error": "Please keep questions under 500 characters.",
                }
            ), 413
        if UNSAFE_SQL_PATTERN.search(question):
            return jsonify(
                {
                    "success": False,
                    "clarification": True,
                    "question": question,
                    "intent": None,
                    "practical": None,
                    "answer": (
                        "I can answer questions about the practicals, but I "
                        "cannot accept SQL commands or database-changing "
                        "instructions. Please ask a read-only question in plain English."
                    ),
                    "query": None,
                    "columns": [],
                    "rows": [],
                    "result_count": 0,
                }
            ), 200

        try:
            with database_connection() as connection:
                result = run_question(connection, question)
                if result is None:
                    return jsonify(
                        {
                            "success": False,
                            "clarification": True,
                            "question": question,
                            "intent": None,
                            "practical": None,
                            "answer": (
                                "I couldn't confidently map that to one of the "
                                "five practicals. Try asking about employees, "
                                "salary, Scott's projects, the IoT raise, "
                                "Accounts, department 5, customer audit, "
                                "rollback, or cursor employees."
                            ),
                            "query": None,
                            "columns": [],
                            "rows": [],
                            "result_count": 0,
                        }
                    ), 200
                answer = generate_answer(result)
                response = {
                    "success": True,
                    "question": question,
                    "intent": result.intent,
                    "practical": result.practical,
                    "answer": answer,
                    "query": result.sql,
                    "columns": result.columns,
                    "rows": result.rows,
                    "result_count": result.row_count,
                    "explanation_data": result.explanation_data,
                }
                messages = session.get("messages", [])
                messages.append(
                    {
                        "question": question[:200],
                        "answer": answer[:300],
                        "intent": result.intent,
                        "practical": result.practical,
                    }
                )
                session["messages"] = messages[-MAX_HISTORY:]
                return jsonify(response)
        except DatabaseUnavailable as error:
            app.logger.warning("Database unavailable: %s", error)
            return jsonify(
                {
                    "success": False,
                    "error": (
                        "The practicals database is unavailable. Confirm the "
                        "existing database file is present and readable."
                    ),
                }
            ), 503
        except sqlite3.Error as error:
            app.logger.exception("Read-only database query failed")
            return jsonify(
                {"success": False, "error": readonly_error_message(error)}
            ), 500
        except (ValueError, KeyError) as error:
            app.logger.warning("Question could not be processed: %s", error)
            return jsonify(
                {
                    "success": False,
                    "error": "That question could not be processed safely.",
                }
            ), 400

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify(
            {"success": False, "error": "The request is too large."}
        ), 413

    @app.errorhandler(500)
    def internal_error(_error):
        return jsonify(
            {
                "success": False,
                "error": "An unexpected server error occurred. Please try again.",
            }
        ), 500

    return app


app = create_app()


if __name__ == "__main__":
    print("DATABASE AI ASSISTANT is starting at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
