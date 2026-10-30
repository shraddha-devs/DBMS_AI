"""Generate concise answers from actual SQLite rows or concept explanations."""

from __future__ import annotations

from typing import Any

from query_engine import QueryResult


def format_inr(value: Any) -> str:
    """Format a numeric value using Indian digit grouping."""
    if value is None:
        return "not recorded"
    number = float(value)
    sign = "-" if number < 0 else ""
    number = abs(number)
    whole = int(number)
    fraction = round(number - whole, 2)
    digits = str(whole)
    if len(digits) > 3:
        last_three = digits[-3:]
        leading = digits[:-3]
        groups: list[str] = []
        while leading:
            groups.insert(0, leading[-2:])
            leading = leading[:-2]
        digits = ",".join(groups + [last_three])
    decimal = f".{round(fraction * 100):02d}" if fraction else ""
    return f"₹{sign}{digits}{decimal}"


def _column(rows: list[dict[str, Any]], name: str) -> list[Any]:
    return [row.get(name) for row in rows]


def generate_answer(result: QueryResult) -> str:
    """Create an answer without fabricating query results."""
    rows = result.rows
    intent = result.intent

    if intent == "rollback_explanation":
        return (
            "ROLLBACK cancels uncommitted changes in the current transaction. "
            "In Practical 1, the three sample inserts were visible before "
            "ROLLBACK, then were removed from the transaction. Only COMMIT "
            "would make those inserts persist."
        )
    if intent == "commit_rollback_difference":
        return (
            "COMMIT saves the transaction's changes permanently. ROLLBACK "
            "cancels changes that have not been committed. The Practical 1 "
            "sample inserts were rolled back, so they are not stored as rows."
        )
    if intent == "primary_key_explanation":
        columns = result.explanation_data.get("p1_columns", [])
        primary_keys = [
            column["name"] for column in columns if column["primary_key"]
        ]
        key_text = ", ".join(primary_keys) if primary_keys else "no declared column"
        return (
            "A primary key uniquely identifies each row and cannot contain "
            f"NULL. The live Practical 1 schema declares {key_text} as its "
            "primary key."
        )
    if intent == "p1_null_constraints":
        required = [
            row["name"] for row in rows if row.get("required") or row.get("pk")
        ]
        if not rows:
            return "The Practical 1 table has no readable column metadata."
        required_text = ", ".join(required) if required else "none"
        optional = [
            row["name"] for row in rows
            if not row.get("required") and not row.get("pk")
        ]
        optional_text = ", ".join(optional) if optional else "none"
        return (
            f"Based on the live P1_EMPLOYEE_TX schema, required columns are "
            f"{required_text}. Columns that may contain NULL are "
            f"{optional_text}. A missing value for a required column is "
            f"rejected by SQLite."
        )
    if intent == "sqlite_privileges":
        return (
            "SQLite is an embedded file database and does not implement "
            "Oracle-style CREATE USER or GRANT database privileges. Access is "
            "controlled by operating-system permissions on the database file. "
            "No Oracle user or grant commands were executed."
        )
    if intent == "insert_explanation":
        return (
            "INSERT adds a row to a table. Practical 1's sample INSERT "
            "statements run inside a transaction, and the later ROLLBACK "
            "cancels those uncommitted rows."
        )
    if intent == "p1_transaction_explanation":
        columns = result.explanation_data.get("p1_columns", [])
        names = ", ".join(column["name"] for column in columns)
        return (
            f"The live P1_EMPLOYEE_TX table has columns {names}. Practical 1 "
            "inserts three sample employees and rolls the transaction back. "
            "As a result, those rows do not persist in the database."
        )
    if intent == "p1_schema":
        if not rows:
            return "No column metadata was returned for P1_EMPLOYEE_TX."
        descriptions = []
        for row in rows:
            notes = []
            if row["pk"]:
                notes.append("primary key")
            if row["required"]:
                notes.append("NOT NULL")
            suffix = f" ({', '.join(notes)})" if notes else " (nullable)"
            descriptions.append(f"{row['name']} {row['type']}{suffix}")
        return "P1_EMPLOYEE_TX columns from the live schema: " + "; ".join(descriptions) + "."
    if intent == "p1_employees":
        if not rows:
            return (
                "The P1_EMPLOYEE_TX table currently has no persisted employee "
                "rows. The three Practical 1 inserts are rolled back, so they "
                "are not available as live records."
            )
        return f"The live Practical 1 table contains {len(rows)} employee record(s)."
    if intent == "p2_employee_105" and not rows:
        return (
            "Employee 105 is not present in the current Practical 2 table; "
            "the live lookup returned no row. The database does not retain "
            "the deleted employee's former details."
        )
    if intent in {"p2_employee_105", "p2_employee_by_id"}:
        if not rows:
            employee_id = result.explanation_data.get(
                "employee_id", result.rows[0].get("EMPNO") if result.rows else None
            )
            if employee_id is None:
                employee_id = 105 if intent == "p2_employee_105" else "requested"
            return f"No current Practical 2 employee row was found for ID {employee_id}."
        employee = rows[0]
        return (
            f"Employee {employee.get('EMPNO')} is currently present as {employee.get('ENAME')}. "
            "The live Practical 2 lookup returned this row."
        )
    if intent == "p1_employee_by_id":
        if not rows:
            return "No current Practical 1 employee row was found for that ID."
        row = rows[0]
        return f"{row['ENAME']} (EMPNO {row['EMPNO']}) is listed in Practical 1."
    if intent == "p2_operations_explanation":
        return (
            "Practical 2 adds COMMISSION, updates the jobs for the sample "
            "employees, renames MGR to MANAGER_NO, and deletes sample EMPNO "
            "105. The employee listing shows current database contents."
        )
    if intent == "trigger_cursor_difference":
        return (
            "A trigger runs automatically in response to table events such as "
            "INSERT, UPDATE, or DELETE. This SQLite project writes those events "
            "to CUSTOMERS_AUDIT. A cursor is an application/database interface "
            "for iterating over query rows; Practical 5 uses Python's "
            "sqlite3.Cursor, not an Oracle PL/SQL explicit cursor."
        )
    if intent == "trigger_explanation":
        return (
            "A SQLite trigger is database code that runs automatically when "
            "its table receives an INSERT, UPDATE, or DELETE. In this project, "
            "the CUSTOMERS triggers use OLD and NEW row values and store an "
            "audit record in CUSTOMERS_AUDIT. Unlike Oracle DBMS_OUTPUT, "
            "SQLite triggers do not print directly to a console."
        )
    if intent == "cursor_explanation":
        return (
            "A cursor provides a way to execute a query and fetch its rows. "
            "Practical 5 uses Python's sqlite3.Cursor: Python executes the "
            "SELECT, fetches the returned records, displays them, and closes "
            "the cursor. This is not an Oracle PL/SQL cursor block."
        )
    if intent == "p2_employees":
        if not rows:
            return "There are no employee rows currently stored in the Practical 2 table."
        return f"The live Practical 2 table contains {len(rows)} employee record(s)."
    if intent == "company_employees":
        if not rows:
            return "The company EMPLOYEE table currently contains no records."
        return f"The live company database contains {len(rows)} employee record(s)."
    if intent == "company_employee_by_id":
        if not rows:
            return (
                "No company employee has SSN/ID "
                f"{result.explanation_data.get('employee_id', 'requested')} in the live database."
            )
        row = rows[0]
        return (
            f"{row.get('Name')} (SSN {row.get('SSN')}) earns "
            f"{format_inr(row.get('Salary'))}."
        )
    if intent in {"company_highest_salary", "p2_highest_salary", "cursor_highest_salary"}:
        if not rows:
            return "No salary records are available to identify a highest-paid employee."
        name_key = "Name" if intent == "company_highest_salary" else (
            "ENAME" if intent == "p2_highest_salary" else "E_NAME"
        )
        salary_key = "Salary" if intent == "company_highest_salary" else (
            "SAL" if intent == "p2_highest_salary" else "SALARY"
        )
        people = ", ".join(
            f"{row.get(name_key)} ({format_inr(row.get(salary_key))})"
            for row in rows
        )
        return f"The highest salary in the selected practical is earned by {people}."
    if intent == "company_salary_aggregates":
        if not rows or rows[0].get("TOTAL_SALARY") is None:
            return "No company employee salary records are available."
        row = rows[0]
        return (
            f"Across the company EMPLOYEE table, total salary is "
            f"{format_inr(row['TOTAL_SALARY'])}, the maximum is "
            f"{format_inr(row['MAX_SALARY'])}, the minimum is "
            f"{format_inr(row['MIN_SALARY'])}, and the average is "
            f"{format_inr(row['AVG_SALARY'])}."
        )
    if intent == "projects_scott":
        projects = _column(rows, "PROJECT_NUMBER")
        if not projects:
            return "No projects involving an employee whose last name is Scott were found."
        return (
            "Projects involving Scott as a worker or as a controlling department "
            f"manager are: {', '.join(str(project) for project in projects)}."
        )
    if intent == "iot_salary_raise":
        if not rows:
            return "No employees working on that project were found in the live database."
        people = "; ".join(
            f"{row['Name']}: current {format_inr(row['CURRENT_SALARY'])}, "
            f"proposed {format_inr(row['PROPOSED_SALARY'])}"
            for row in rows
        )
        return (
            f"{len(rows)} employee(s) work on the IoT project. With a proposed "
            f"10% increase: {people}. Existing salaries were not modified."
        )
    if intent == "iot_employees":
        if not rows:
            return "No employees working on that project were found in the live database."
        people = "; ".join(
            f"{row['Name']} earns {format_inr(row['CURRENT_SALARY'])}"
            for row in rows
        )
        return f"The live database lists {len(rows)} IoT project employee(s): {people}."
    if intent == "department_salary_aggregates":
        if not rows:
            return "No salary records were found for that department."
        row = rows[0]
        return (
            f"The total salary in {row['DEPARTMENT_NAME']} is "
            f"{format_inr(row['TOTAL_SALARY'])}. The highest is "
            f"{format_inr(row['MAX_SALARY'])}, the lowest is "
            f"{format_inr(row['MIN_SALARY'])}, and the average is "
            f"{format_inr(row['AVG_SALARY'])}."
        )
    if intent == "department_highest_salary":
        if not rows:
            return "No employees were found in that department."
        return "; ".join(
            f"{row['Name']} earns {format_inr(row['Salary'])}"
            for row in rows
        ) + "."
    if intent == "employees_all_d5_projects":
        if not rows:
            return "No employees currently work on every project in that department."
        names = ", ".join(f"{row['Name']} (SSN {row['SSN']})" for row in rows)
        return (
            "Employees assigned to every project controlled by department "
            f"{result.explanation_data.get('department_id', 5)}: {names}."
        )
    if intent == "departments_salary_threshold":
        threshold = result.explanation_data.get("salary_threshold", 600000)
        floor = result.explanation_data.get("department_employee_floor", 5)
        if not rows:
            return (
                f"No department with more than {floor} employees has workers "
                f"earning over {format_inr(threshold)}."
            )
        details = ", ".join(
            f"department {row['DEPARTMENT_NUMBER']}: "
            f"{row['EMPLOYEES_ABOVE_THRESHOLD']} employee(s)"
            for row in rows
        )
        return (
            f"For departments with more than {floor} employees, counts earning "
            f"over {format_inr(threshold)} are {details}."
        )
    if intent == "customers":
        if not rows:
            return "There are currently no customer rows in CUSTOMERS."
        return f"The live CUSTOMERS table contains {len(rows)} record(s)."
    if intent in {"customer_audit", "customer_salary_difference"}:
        if not rows:
            return "No matching customer audit events were found."
        if intent == "customer_salary_difference":
            row = rows[0]
            old_salary = row.get("OLD_SALARY")
            new_salary = row.get("NEW_SALARY")
            difference = row.get("SALARY_DIFFERENCE")
            if old_salary is None or new_salary is None or difference is None:
                return "The latest update audit row does not contain both salary values."
            direction = "increased" if difference > 0 else "decreased" if difference < 0 else "did not change"
            return (
                f"The customer's salary {direction} from "
                f"{format_inr(old_salary)} to {format_inr(new_salary)}, a "
                f"difference of {format_inr(abs(difference))}."
            )
        action = result.explanation_data.get("action")
        sentences = []
        for row in rows:
            action_text = str(row["ACTION"]).lower()
            if row["ACTION"] == "UPDATE":
                sentences.append(
                    f"Update for customer {row['CUSTOMER_ID']}: old salary "
                    f"{format_inr(row['OLD_SALARY'])}, new salary "
                    f"{format_inr(row['NEW_SALARY'])}, difference "
                    f"{format_inr(row['SALARY_DIFFERENCE'])} "
                    f"({row['CHANGED_AT']})."
                )
            elif row["ACTION"] == "INSERT":
                sentences.append(
                    f"Insert for customer {row['CUSTOMER_ID']}: new salary "
                    f"{format_inr(row['NEW_SALARY'])}; old value unavailable "
                    f"({row['CHANGED_AT']})."
                )
            else:
                sentences.append(
                    f"Delete for customer {row['CUSTOMER_ID']}: old salary "
                    f"{format_inr(row['OLD_SALARY'])}; new value unavailable "
                    f"({row['CHANGED_AT']})."
                )
        prefix = f"Found {len(rows)} {action} audit event(s). " if action else (
            f"Latest {len(rows)} customer audit event(s). "
        )
        return prefix + " ".join(sentences)
    if intent == "cursor_count":
        count = int(rows[0]["EMPLOYEE_COUNT"]) if rows else 0
        noun = "employee" if count == 1 else "employees"
        return f"There are {count} {noun} in the cursor practical."
    if intent == "cursor_employees":
        if not rows:
            return "The cursor practical has no employee records."
        return f"The live cursor practical contains {len(rows)} employee record(s)."
    if intent == "cursor_oldest":
        if not rows:
            return "No age values are available in the cursor employee table."
        oldest = max(int(row["AGE"]) for row in rows if row.get("AGE") is not None)
        people = ", ".join(
            f"{row['E_NAME']} (age {row['AGE']})"
            for row in rows
        )
        return f"The oldest cursor employee(s) are {people}, age {oldest}."
    if intent == "cursor_employee_by_id":
        if not rows:
            return "No cursor employee with that ID was found."
        row = rows[0]
        return (
            f"{row['E_NAME']} (ID {row['E_ID']}) is age {row['AGE']} and "
            f"earns {format_inr(row['SALARY'])}."
        )

    return "I couldn't build an answer for that request. Please rephrase it."
