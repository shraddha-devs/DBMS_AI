"""Lightweight, API-key-free natural-language intent recognition."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass


MAX_QUESTION_LENGTH = 500

TYPO_ALIASES = {
    "employe": "employee",
    "employes": "employees",
    "sallary": "salary",
    "salaries": "salary",
    "saleries": "salary",
    "acounts": "accounts",
    "acconts": "accounts",
    "rollbak": "rollback",
    "roolback": "rollback",
    "curser": "cursor",
    "triger": "trigger",
    "departmant": "department",
    "departments": "department",
    "projet": "project",
    "projets": "projects",
    "commision": "commission",
    "commissions": "commission",
    "maksimum": "maximum",
    "maximun": "maximum",
    "higest": "highest",
    "heighest": "highest",
    "employeeno": "empno",
}

CORRECTION_VOCABULARY = {
    "employee",
    "employees",
    "salary",
    "highest",
    "maximum",
    "department",
    "accounts",
    "rollback",
    "cursor",
    "trigger",
    "commission",
    "projects",
    "project",
    "average",
    "minimum",
    "maximum",
    "primary",
    "constraint",
    "deleted",
    "audit",
}


@dataclass(frozen=True)
class Intent:
    name: str
    practical: str
    entities: dict[str, str | int]
    normalized_question: str


def _normalize(question: str) -> str:
    text = question.casefold().replace("₹", " rupees ")
    text = re.sub(r"(\d),(\d)", r"\1\2", text)
    text = re.sub(r"[^a-z0-9_ ]+", " ", text)
    tokens = text.split()
    corrected: list[str] = []
    for token in tokens:
        token = TYPO_ALIASES.get(token, token)
        if token not in CORRECTION_VOCABULARY and len(token) >= 5:
            suggestion = difflib.get_close_matches(
                token, CORRECTION_VOCABULARY, n=1, cutoff=0.86
            )
            if suggestion:
                token = suggestion[0]
        corrected.append(token)

    normalized = " ".join(corrected)
    normalized = re.sub(r"\bp\s*1\b", " practical 1 ", normalized)
    normalized = re.sub(r"\bp\s*2\b", " practical 2 ", normalized)
    normalized = re.sub(r"\bp\s*3\b", " practical 3 ", normalized)
    normalized = re.sub(r"\bp\s*4\b", " practical 4 ", normalized)
    normalized = re.sub(r"\bp\s*5\b", " practical 5 ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _matching_entity(value: str, candidates: list[str]) -> str | None:
    lowered = value.casefold()
    for candidate in candidates:
        if candidate.casefold() in lowered:
            return candidate
    return None


def classify_question(
    question: str,
    *,
    department_names: list[str] | None = None,
    project_names: list[str] | None = None,
    employee_records: list[dict[str, str]] | None = None,
) -> Intent | None:
    """Map a natural-language question to a safe, finite intent vocabulary."""
    if not isinstance(question, str) or not question.strip():
        return None
    if len(question) > MAX_QUESTION_LENGTH:
        return None

    text = _normalize(question)
    entities: dict[str, str | int] = {}
    departments = department_names or ["Accounts", "Research", "Engineering"]
    projects = project_names or ["IoT", "Smart Grid"]

    id_search_text = re.sub(r"\b(?:practical|p)\s*\d+\b", " ", text)
    empno_match = re.search(
        r"\b(?:employee\s+)?(?:id|number|empno)?\s*(\d{1,8})\b",
        id_search_text,
    )
    if empno_match:
        entities["employee_id"] = int(empno_match.group(1))
    department_id_match = re.search(
        r"\bdepartment\s*(?:number|no)?\s*(\d{1,4})\b", text
    )
    if department_id_match:
        entities["department_id"] = int(department_id_match.group(1))

    dept_match = _matching_entity(text, departments)
    if dept_match:
        entities["department"] = dept_match
    project_match = _matching_entity(text, projects)
    if project_match:
        entities["project"] = project_match

    records = employee_records or []
    matched_employee = None
    requested_id = str(entities.get("employee_id", ""))
    if requested_id:
        matched_employee = next(
            (record for record in records if record["id"] == requested_id), None
        )
    if matched_employee is None:
        matched_name = _matching_entity(question, [record["name"] for record in records])
        if matched_name:
            matched_employee = next(
                record for record in records if record["name"].casefold() == matched_name.casefold()
            )
    if matched_employee:
        entities["employee_id"] = int(matched_employee["id"]) if matched_employee["id"].isdigit() else matched_employee["id"]
        entities["employee_name"] = matched_employee["name"]
        entities["employee_source"] = matched_employee["source"]

    # Concept comparisons must be considered before generic trigger/cursor hits.
    if "trigger" in text and "cursor" in text and any(
        term in text for term in ("difference", "versus", "vs", "compare")
    ):
        return Intent("trigger_cursor_difference", "Concepts", entities, text)

    if "fetched" in text and any(term in text for term in ("how many", "count", "number")):
        return Intent("cursor_count", "Practical 5", entities, text)

    if "salary difference" in text or "old salary" in text or "new salary" in text:
        return Intent("customer_salary_difference", "Practical 4", entities, text)

    if "commit" in text and "rollback" in text:
        return Intent("commit_rollback_difference", "Practical 1", entities, text)
    if "update" in text and "delete" in text and "difference" in text:
        return Intent("p2_operations_explanation", "Practical 2", entities, text)
    if any(term in text for term in ("rollback", "roll back")) and any(
        term in text for term in ("what is", "explain", "why", "how do", "operation", "practical")
    ):
        return Intent("rollback_explanation", "Practical 1", entities, text)
    if "primary key" in text:
        return Intent("primary_key_explanation", "Practical 1", entities, text)
    if "not null" in text or "nullable" in text or "null value" in text:
        return Intent("p1_null_constraints", "Practical 1", entities, text)
    if any(term in text for term in ("create user", "grant", "privilege", "permission")):
        return Intent("sqlite_privileges", "Practical 1", entities, text)
    if any(action in text for action in ("insert", "update", "delete")) and (
        "operation" in text or "happened" in text
    ):
        return Intent("customer_audit", "Practical 4", entities, text)
    if "insert" in text and any(term in text for term in ("operation", "practical", "employee")):
        return Intent("insert_explanation", "Practical 1", entities, text)

    is_p1 = "practical 1" in text or "p1 employee" in text
    is_p2 = (
        "practical 2" in text
        or "p2 employee" in text
        or "employee_source" in entities and entities["employee_source"] == "p2"
        or str(entities.get("employee_id", "")) == "105"
        or "commission" in text
        or "rename" in text
        or "alter table" in text
        or "updated jobs" in text
        or "after updating" in text
    )
    is_cursor = (
        "cursor" in text
        or "cursor_employee" in text
        or entities.get("employee_source") == "cursor"
    )
    is_customer = any(term in text for term in ("customer", "audit", "trigger"))

    if any(term in text for term in ("employee was deleted", "which employee deleted",
                                     "who was deleted", "what happened to employee")):
        entities.setdefault("employee_id", 105)
        return Intent("p2_employee_105", "Practical 2", entities, text)

    if is_p2 and str(entities.get("employee_id", "")) == "105":
        return Intent("p2_employee_105", "Practical 2", entities, text)

    if is_p2 and "employee_id" in entities and any(
        term in text for term in ("show", "find", "employee", "salary", "earns", "record")
    ):
        return Intent("p2_employee_by_id", "Practical 2", entities, text)

    if is_cursor:
        if any(term in text for term in ("oldest", "oldest age", "eldest")):
            return Intent("cursor_oldest", "Practical 5", entities, text)
        if "highest" in text or "maximum" in text or "most" in text:
            return Intent("cursor_highest_salary", "Practical 5", entities, text)
        if "how many" in text or "count" in text or "number of" in text:
            return Intent("cursor_count", "Practical 5", entities, text)
        if "id" in text or "number" in text:
            if "employee_id" in entities:
                return Intent("cursor_employee_by_id", "Practical 5", entities, text)
        if "employee_name" in entities and any(
            term in text for term in ("show", "find", "employee", "salary", "earns")
        ):
            return Intent("cursor_employee_by_id", "Practical 5", entities, text)
        if any(term in text for term in ("show", "display", "list", "all", "records", "employees")):
            return Intent("cursor_employees", "Practical 5", entities, text)
        if "what is" in text or "explain" in text or "practical" in text:
            return Intent("cursor_explanation", "Practical 5", entities, text)

    if is_customer:
        if "difference" in text or "increased" in text or "salary change" in text:
            return Intent("customer_salary_difference", "Practical 4", entities, text)
        if any(term in text for term in ("show", "display", "list")) and any(
            term in text for term in ("audit", "history", "records", "latest")
        ):
            return Intent("customer_audit", "Practical 4", entities, text)
        if any(term in text for term in ("customer records", "show customers", "list customers")):
            return Intent("customers", "Practical 4", entities, text)
        if any(term in text for term in ("insert", "update", "delete")):
            if "operation" in text or "happened" in text or "salary" in text:
                return Intent("customer_audit", "Practical 4", entities, text)
            return Intent("trigger_explanation", "Practical 4", entities, text)
        if "what is" in text or "explain" in text or "how does" in text:
            return Intent("trigger_explanation", "Practical 4", entities, text)

    if any(term in text for term in (
        "all department 5", "all projects", "every project", "all project assignment"
    )) and (
        "work" in text or "project" in text or "assigned" in text
    ):
        return Intent("employees_all_d5_projects", "Practical 3", entities, text)

    if "scott" in text and any(
        term in text for term in ("project", "manage", "involve", "works")
    ):
        return Intent("projects_scott", "Practical 3", entities, text)

    if project_match and "iot" in project_match.casefold():
        if any(term in text for term in ("raise", "increase", "proposed", "resulting")):
            return Intent("iot_salary_raise", "Practical 3", entities, text)
        if any(term in text for term in ("salary", "earn", "working", "employee", "who")):
            return Intent("iot_employees", "Practical 3", entities, text)
    if "iot" in text:
        if any(term in text for term in ("raise", "increase", "proposed", "resulting")):
            return Intent("iot_salary_raise", "Practical 3", entities, text)
        if any(term in text for term in ("salary", "earn", "working", "employee", "who")):
            return Intent("iot_employees", "Practical 3", entities, text)

    threshold_query = any(
        term in text for term in ("more than five", "more than 5", "above 600000",
                                  "above 600 000", "over 600000", "six lakh",
                                  "600000", "qualifying department",
                                  "more than five employee", "more than 5 employee")
    )
    if threshold_query and "department" in text:
        return Intent("departments_salary_threshold", "Practical 3", entities, text)

    if dept_match:
        if any(term in text for term in ("salary", "sum", "total", "average", "avg",
                                         "minimum", "maximum", "highest", "lowest")):
            if any(term in text for term in ("highest", "maximum", "most")) and not any(
                term in text for term in ("sum", "total", "average", "minimum")
            ):
                return Intent("department_highest_salary", "Practical 3", entities, text)
            return Intent("department_salary_aggregates", "Practical 3", entities, text)

    if entities.get("employee_source") == "company" and any(
        term in text for term in (
            "show", "find", "employee", "salary", "earns", "record", "ssn",
            "what is", "tell me", "address",
        )
    ):
        return Intent("company_employee_by_id", "Practical 3", entities, text)

    if entities.get("employee_source") == "p1" and any(
        term in text for term in ("show", "find", "employee", "salary", "record")
    ):
        return Intent("p1_employee_by_id", "Practical 1", entities, text)

    if is_p1:
        if any(term in text for term in ("column", "schema", "structure", "constraint")):
            return Intent("p1_schema", "Practical 1", entities, text)
        if any(term in text for term in ("show", "display", "list", "record", "employee")):
            return Intent("p1_employees", "Practical 1", entities, text)
        if any(term in text for term in ("what is", "explain")):
            return Intent("p1_transaction_explanation", "Practical 1", entities, text)

    if is_p2:
        if "highest" in text or "maximum" in text or "most" in text:
            return Intent("p2_highest_salary", "Practical 2", entities, text)
        if any(term in text for term in ("show", "display", "list", "employee", "record")):
            return Intent("p2_employees", "Practical 2", entities, text)
        if any(term in text for term in ("what is", "explain", "difference")):
            return Intent("p2_operations_explanation", "Practical 2", entities, text)

    if "salary" in text and any(
        term in text for term in ("minimum", "average", "sum", "total")
    ):
        return Intent("company_salary_aggregates", "Practical 3", entities, text)

    if "salary" in text or any(
        term in text for term in ("highest paid", "most paid", "earns most", "earns the most")
    ):
        if any(term in text for term in ("highest", "maximum", "most", "largest")):
            return Intent("company_highest_salary", "Practical 3", entities, text)

    if "employee_id" in entities and any(
        term in text for term in ("show", "find", "employee", "record", "number", "id")
    ):
        return Intent("company_employee_by_id", "Practical 3", entities, text)

    if any(term in text for term in ("show", "display", "list", "all")) and any(
        term in text for term in ("employee", "employees", "records", "staff")
    ):
        return Intent("company_employees", "Practical 3", entities, text)

    return None
