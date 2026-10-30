"""Registry of approved read-only SQL templates for chatbot intents."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from database import available_entities, table_columns
from nlp_processor import Intent, classify_question


@dataclass(frozen=True)
class QueryResult:
    intent: str
    practical: str
    sql: str | None
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int | None
    explanation_data: dict[str, Any]


def _result(
    connection: sqlite3.Connection,
    intent: Intent,
    sql: str | None = None,
    parameters: tuple[Any, ...] = (),
    *,
    explanation_data: dict[str, Any] | None = None,
) -> QueryResult:
    if sql is None:
        return QueryResult(
            intent.name, intent.practical, None, [], [], None,
            explanation_data or {},
        )

    statement = sql.lstrip().upper()
    if not statement.startswith("SELECT"):
        raise ValueError("Only registered read-only SELECT queries are permitted.")
    cursor = connection.execute(sql, parameters)
    if cursor.description is None:
        raise ValueError("Registered database queries must return rows.")
    columns = [str(column[0]) for column in cursor.description]
    rows = [dict(row) for row in cursor.fetchall()]
    return QueryResult(
        intent.name,
        intent.practical,
        sql.strip(),
        columns,
        rows,
        len(rows),
        explanation_data or {},
    )


def _actual_columns(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    return table_columns(connection, table)


def run_question(connection: sqlite3.Connection, question: str) -> QueryResult | None:
    """Classify a question and execute only a registered read-only query."""
    entities = available_entities(connection)
    intent = classify_question(
        question,
        department_names=entities["department_names"],
        project_names=entities["project_names"],
        employee_records=entities["employee_records"],
    )
    if intent is None:
        return None

    if intent.name in {
        "rollback_explanation",
        "commit_rollback_difference",
        "primary_key_explanation",
        "sqlite_privileges",
        "insert_explanation",
        "p1_transaction_explanation",
        "p2_operations_explanation",
        "trigger_explanation",
        "trigger_cursor_difference",
        "cursor_explanation",
    }:
        detail = {
            "p1_columns": _actual_columns(connection, "P1_EMPLOYEE_TX"),
            "p2_columns": _actual_columns(connection, "P2_EMPLOYEE_ALT"),
        } if intent.name in {
            "p1_transaction_explanation", "primary_key_explanation"
        } else {}
        return _result(connection, intent, explanation_data=detail)

    if intent.name == "p1_schema":
        return _result(
            connection,
            intent,
            """
            SELECT name, type, "notnull" AS required, pk
            FROM pragma_table_info(?)
            ORDER BY cid
            """,
            ("P1_EMPLOYEE_TX",),
        )
    if intent.name == "p1_null_constraints":
        return _result(
            connection,
            intent,
            """
            SELECT name, type, "notnull" AS required, pk
            FROM pragma_table_info(?)
            ORDER BY cid
            """,
            ("P1_EMPLOYEE_TX",),
        )
    if intent.name == "p1_employees":
        return _result(
            connection,
            intent,
            """SELECT EMPNO, ENAME, JOB, MANAGER_NO, SAL, COMMISSION
               FROM P1_EMPLOYEE_TX ORDER BY EMPNO""",
        )
    if intent.name == "p1_employee_by_id":
        return _result(
            connection,
            intent,
            """SELECT EMPNO, ENAME, JOB, MANAGER_NO, SAL, COMMISSION
               FROM P1_EMPLOYEE_TX WHERE EMPNO = ?""",
            (intent.entities.get("employee_id"),),
            explanation_data={"employee_id": intent.entities.get("employee_id")},
        )
    if intent.name == "p2_employee_105":
        return _result(
            connection,
            intent,
            """SELECT EMPNO, ENAME, JOB, MANAGER_NO, SAL, COMMISSION
               FROM P2_EMPLOYEE_ALT WHERE EMPNO = ?""",
            (105,),
        )
    if intent.name == "p2_employees":
        return _result(
            connection,
            intent,
            """SELECT EMPNO, ENAME, JOB, MANAGER_NO, SAL, COMMISSION
               FROM P2_EMPLOYEE_ALT ORDER BY EMPNO""",
        )
    if intent.name == "p2_employee_by_id":
        return _result(
            connection,
            intent,
            """SELECT EMPNO, ENAME, JOB, MANAGER_NO, SAL, COMMISSION
               FROM P2_EMPLOYEE_ALT WHERE EMPNO = ?""",
            (intent.entities.get("employee_id"),),
            explanation_data={"employee_id": intent.entities.get("employee_id")},
        )
    if intent.name == "company_employees":
        return _result(
            connection,
            intent,
            """SELECT SSN, Name, Address, Sex, Salary, SuperSSN, DNo
               FROM EMPLOYEE ORDER BY SSN""",
        )
    if intent.name == "company_employee_by_id":
        return _result(
            connection,
            intent,
            """SELECT SSN, Name, Address, Sex, Salary, SuperSSN, DNo
               FROM EMPLOYEE WHERE SSN = ?""",
            (str(intent.entities.get("employee_id", "")),),
            explanation_data={"employee_id": intent.entities.get("employee_id")},
        )
    if intent.name == "company_highest_salary":
        return _result(
            connection,
            intent,
            """SELECT SSN, Name, Salary
               FROM EMPLOYEE
               WHERE Salary = (SELECT MAX(Salary) FROM EMPLOYEE)
               ORDER BY Name""",
        )
    if intent.name == "company_salary_aggregates":
        return _result(
            connection,
            intent,
            """
            SELECT SUM(Salary) AS TOTAL_SALARY,
                   MAX(Salary) AS MAX_SALARY,
                   MIN(Salary) AS MIN_SALARY,
                   ROUND(AVG(Salary), 2) AS AVG_SALARY
            FROM EMPLOYEE
            """,
        )
    if intent.name == "p2_highest_salary":
        return _result(
            connection,
            intent,
            """SELECT EMPNO, ENAME, SAL
               FROM P2_EMPLOYEE_ALT
               WHERE SAL = (SELECT MAX(SAL) FROM P2_EMPLOYEE_ALT)
               ORDER BY EMPNO""",
        )
    if intent.name == "projects_scott":
        return _result(
            connection,
            intent,
            """
            SELECT p.PNo AS PROJECT_NUMBER
            FROM PROJECT AS p
            WHERE EXISTS (
                SELECT 1
                FROM WORKS_ON AS w
                JOIN EMPLOYEE AS e ON e.SSN = w.SSN
                WHERE w.PNo = p.PNo AND TRIM(e.Name) LIKE ?
            )
            OR EXISTS (
                SELECT 1
                FROM DEPARTMENT AS d
                JOIN EMPLOYEE AS e ON e.SSN = d.MgrSSN
                WHERE d.DNo = p.DNo AND TRIM(e.Name) LIKE ?
            )
            ORDER BY p.PNo
            """,
            ("% Scott", "% Scott"),
        )
    if intent.name == "iot_salary_raise":
        project = str(intent.entities.get("project", "IoT"))
        return _result(
            connection,
            intent,
            """
            SELECT e.SSN, e.Name, e.Salary AS CURRENT_SALARY,
                   ROUND(e.Salary * 1.10, 2) AS PROPOSED_SALARY
            FROM EMPLOYEE AS e
            WHERE EXISTS (
                SELECT 1
                FROM WORKS_ON AS w
                JOIN PROJECT AS p ON p.PNo = w.PNo
                WHERE w.SSN = e.SSN AND lower(p.PName) = lower(?)
            )
            ORDER BY e.SSN
            """,
            (project,),
        )
    if intent.name == "iot_employees":
        project = str(intent.entities.get("project", "IoT"))
        return _result(
            connection,
            intent,
            """
            SELECT e.SSN, e.Name, e.Salary AS CURRENT_SALARY
            FROM EMPLOYEE AS e
            WHERE EXISTS (
                SELECT 1
                FROM WORKS_ON AS w
                JOIN PROJECT AS p ON p.PNo = w.PNo
                WHERE w.SSN = e.SSN AND lower(p.PName) = lower(?)
            )
            ORDER BY e.SSN
            """,
            (project,),
        )
    if intent.name == "department_salary_aggregates":
        department = str(intent.entities.get("department", "Accounts"))
        return _result(
            connection,
            intent,
            """
            SELECT d.DName AS DEPARTMENT_NAME,
                   SUM(e.Salary) AS TOTAL_SALARY,
                   MAX(e.Salary) AS MAX_SALARY,
                   MIN(e.Salary) AS MIN_SALARY,
                   ROUND(AVG(e.Salary), 2) AS AVG_SALARY
            FROM DEPARTMENT AS d
            JOIN EMPLOYEE AS e ON e.DNo = d.DNo
            WHERE lower(d.DName) = lower(?)
            GROUP BY d.DName
            """,
            (department,),
        )
    if intent.name == "department_highest_salary":
        department = str(intent.entities.get("department", "Accounts"))
        return _result(
            connection,
            intent,
            """
            SELECT e.SSN, e.Name, e.Salary
            FROM EMPLOYEE AS e
            JOIN DEPARTMENT AS d ON d.DNo = e.DNo
            WHERE lower(d.DName) = lower(?)
              AND e.Salary = (
                  SELECT MAX(e2.Salary)
                  FROM EMPLOYEE AS e2
                  WHERE e2.DNo = d.DNo
              )
            ORDER BY e.Name
            """,
            (department,),
        )
    if intent.name == "employees_all_d5_projects":
        department_id = int(intent.entities.get("department_id", 5))
        return _result(
            connection,
            intent,
            """
            SELECT e.SSN, e.Name
            FROM EMPLOYEE AS e
            WHERE NOT EXISTS (
                SELECT 1 FROM PROJECT AS p
                WHERE p.DNo = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM WORKS_ON AS w
                      WHERE w.SSN = e.SSN AND w.PNo = p.PNo
                  )
            )
            ORDER BY e.SSN
            """,
            (department_id,),
        )
    if intent.name == "departments_salary_threshold":
        threshold = 600000
        threshold_match = re.search(
            r"\b(?:above|over|more than|earning|earn|salary)\s+"
            r"(?:rs\s*)?(\d{5,7})\b",
            intent.normalized_question,
        )
        if threshold_match:
            threshold = int(threshold_match.group(1))
        department_floor = 5
        floor_match = re.search(
            r"(?:more than|over|at least)\s+(\d+)\s+employees?",
            intent.normalized_question,
        )
        if floor_match:
            department_floor = int(floor_match.group(1))
        return _result(
            connection,
            intent,
            """
            SELECT e.DNo AS DEPARTMENT_NUMBER,
                   COUNT(*) AS EMPLOYEES_ABOVE_THRESHOLD
            FROM EMPLOYEE AS e
            WHERE e.Salary > ?
              AND e.DNo IN (
                  SELECT DNo
                  FROM EMPLOYEE
                  GROUP BY DNo
                  HAVING COUNT(*) > ?
              )
            GROUP BY e.DNo
            ORDER BY e.DNo
            """,
            (threshold, department_floor),
            explanation_data={
                "salary_threshold": threshold,
                "department_employee_floor": department_floor,
            },
        )
    if intent.name == "customers":
        return _result(
            connection,
            intent,
            "SELECT ID, NAME, AGE, ADDRESS, SALARY FROM CUSTOMERS ORDER BY ID",
        )
    if intent.name in {"customer_audit", "customer_salary_difference"}:
        if intent.name == "customer_salary_difference":
            action = "UPDATE"
            limit = 1
        else:
            action_match = re.search(r"\b(insert|update|delete)\b", intent.normalized_question)
            action = action_match.group(1).upper() if action_match else None
            limit = 1000 if "all" in intent.normalized_question else 10
            latest_match = re.search(r"\b(?:latest|last|recent)\s+(\d+)\b", intent.normalized_question)
            if latest_match:
                limit = min(max(int(latest_match.group(1)), 1), 100)
        if action:
            sql = """
                SELECT AUDIT_ID, CUSTOMER_ID, ACTION, OLD_SALARY,
                       NEW_SALARY, SALARY_DIFFERENCE, CHANGED_AT
                FROM CUSTOMERS_AUDIT
                WHERE ACTION = ?
                ORDER BY AUDIT_ID DESC
                LIMIT ?
            """
            params: tuple[Any, ...] = (action, limit)
        else:
            sql = """
                SELECT AUDIT_ID, CUSTOMER_ID, ACTION, OLD_SALARY,
                       NEW_SALARY, SALARY_DIFFERENCE, CHANGED_AT
                FROM CUSTOMERS_AUDIT
                ORDER BY AUDIT_ID DESC
                LIMIT ?
            """
            params = (limit,)
        return _result(connection, intent, sql, params, explanation_data={"action": action})
    if intent.name == "cursor_employees":
        return _result(
            connection,
            intent,
            """SELECT E_ID, E_NAME, AGE, SALARY
               FROM CURSOR_EMPLOYEE ORDER BY E_ID""",
        )
    if intent.name == "cursor_count":
        return _result(
            connection,
            intent,
            "SELECT COUNT(*) AS EMPLOYEE_COUNT FROM CURSOR_EMPLOYEE",
        )
    if intent.name == "cursor_oldest":
        return _result(
            connection,
            intent,
            """SELECT E_ID, E_NAME, AGE, SALARY
               FROM CURSOR_EMPLOYEE
               WHERE AGE = (SELECT MAX(AGE) FROM CURSOR_EMPLOYEE)
               ORDER BY E_ID""",
        )
    if intent.name == "cursor_highest_salary":
        return _result(
            connection,
            intent,
            """SELECT E_ID, E_NAME, AGE, SALARY
               FROM CURSOR_EMPLOYEE
               WHERE SALARY = (SELECT MAX(SALARY) FROM CURSOR_EMPLOYEE)
               ORDER BY E_ID""",
        )
    if intent.name == "cursor_employee_by_id":
        return _result(
            connection,
            intent,
            """SELECT E_ID, E_NAME, AGE, SALARY
               FROM CURSOR_EMPLOYEE WHERE E_ID = ?""",
            (int(intent.entities.get("employee_id", 0)),),
        )

    return None
