"""Read-only access and schema inspection for the existing practicals database."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


DATABASE_PATH = Path(__file__).resolve().with_name("practicals.db")


class DatabaseUnavailable(RuntimeError):
    """Raised when the existing database cannot be read."""


def connect_readonly(path: Path | str = DATABASE_PATH) -> sqlite3.Connection:
    """Open an existing SQLite file without permitting writes."""
    database_path = Path(path).resolve()
    if not database_path.is_file():
        raise DatabaseUnavailable("The practicals database file is unavailable.")

    try:
        connection = sqlite3.connect(
            f"{database_path.as_uri()}?mode=ro",
            uri=True,
            timeout=5,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA query_only = ON")
        return connection
    except sqlite3.Error as error:
        raise DatabaseUnavailable(
            "The practicals database could not be opened for reading."
        ) from error


def database_overview(connection: sqlite3.Connection) -> dict[str, Any]:
    """Return actual table names and row counts from SQLite metadata."""
    tables = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    table_details: list[dict[str, Any]] = []
    for row in tables:
        name = str(row["name"])
        columns = [
            str(column["name"])
            for column in connection.execute(
                "SELECT name FROM pragma_table_info(?) ORDER BY cid",
                (name,),
            ).fetchall()
        ]
        quoted_name = '"' + name.replace('"', '""') + '"'
        row_count = int(
            connection.execute(f"SELECT COUNT(*) FROM {quoted_name}").fetchone()[0]
        )
        table_details.append(
            {"name": name, "rows": row_count, "columns": columns}
        )
    return {
        "filename": DATABASE_PATH.name,
        "tables": table_details,
        "table_count": len(table_details),
    }


def available_entities(
    connection: sqlite3.Connection,
) -> dict[str, list[str] | list[dict[str, str]]]:
    """Load live lookup terms used for safe natural-language entity matching."""
    department_names = [
        str(row[0])
        for row in connection.execute(
            "SELECT DName FROM DEPARTMENT ORDER BY DName"
        ).fetchall()
    ]
    project_names = [
        str(row[0])
        for row in connection.execute(
            "SELECT PName FROM PROJECT ORDER BY PName"
        ).fetchall()
    ]
    employee_records: list[dict[str, str]] = []
    for query, source in (
        ("SELECT EMPNO, ENAME FROM P1_EMPLOYEE_TX", "p1"),
        ("SELECT EMPNO, ENAME FROM P2_EMPLOYEE_ALT", "p2"),
        ("SELECT SSN, Name FROM EMPLOYEE", "company"),
        ("SELECT E_ID, E_NAME FROM CURSOR_EMPLOYEE", "cursor"),
    ):
        employee_records.extend(
            {
                "id": str(row[0]),
                "name": str(row[1]),
                "source": source,
            }
            for row in connection.execute(query).fetchall()
        )
    return {
        "department_names": department_names,
        "project_names": project_names,
        "employee_records": employee_records,
    }


def table_columns(
    connection: sqlite3.Connection, table_name: str
) -> list[dict[str, Any]]:
    """Read table columns and SQLite constraint metadata safely."""
    rows = connection.execute(
        """
        SELECT name, type, "notnull" AS required, pk
        FROM pragma_table_info(?)
        ORDER BY cid
        """,
        (table_name,),
    ).fetchall()
    return [
        {
            "name": str(row["name"]),
            "type": str(row["type"]),
            "not_null": bool(row["required"]),
            "primary_key": bool(row["pk"]),
        }
        for row in rows
    ]


def readonly_error_message(error: sqlite3.Error) -> str:
    """Translate database failures into a message safe to show in the UI."""
    message = str(error).lower()
    if "readonly" in message or "read-only" in message:
        return "This assistant is read-only and cannot change database records."
    return "The database could not complete that read request. Please try again."
