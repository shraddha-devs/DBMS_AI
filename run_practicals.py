"""Initialize and run all five SQLite practicals using Python's stdlib."""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "practicals.db"
SCRIPT_ORDER = (
    "01_employee_transactions.sql",
    "02_employee_alter_update_delete.sql",
    "03_company_queries.sql",
    "04_customer_trigger.sql",
    "05_employee_cursor.sql",
)

EXPECTED_COLUMNS: dict[str, tuple[str, ...]] = {
    "P1_EMPLOYEE_TX": (
        "EMPNO", "ENAME", "JOB", "MANAGER_NO", "SAL", "COMMISSION"
    ),
    "P2_EMPLOYEE_ALT": (
        "EMPNO", "ENAME", "JOB", "MGR", "SAL"
    ),
    "EMPLOYEE": ("SSN", "Name", "Address", "Sex", "Salary", "SuperSSN", "DNo"),
    "DEPARTMENT": ("DNo", "DName", "MgrSSN", "MgrStartDate"),
    "PROJECT": ("PNo", "PName", "PLocation", "DNo"),
    "DLOCATION": ("DNo", "DLoc"),
    "WORKS_ON": ("SSN", "PNo", "Hours"),
    "CUSTOMERS": ("ID", "NAME", "AGE", "ADDRESS", "SALARY"),
    "CUSTOMERS_AUDIT": (
        "AUDIT_ID",
        "CUSTOMER_ID",
        "ACTION",
        "OLD_SALARY",
        "NEW_SALARY",
        "SALARY_DIFFERENCE",
        "CHANGED_AT",
    ),
    "CURSOR_EMPLOYEE": ("E_ID", "E_NAME", "AGE", "SALARY"),
}


def fail(message: str) -> None:
    raise RuntimeError(message)


def table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )
    return {str(row[0]).upper() for row in rows}


def columns_for(connection: sqlite3.Connection, table: str) -> tuple[str, ...]:
    escaped = table.replace('"', '""')
    rows = connection.execute(f'PRAGMA table_info("{escaped}")')
    return tuple(str(row[1]).upper() for row in rows)


def validate_existing_schema(connection: sqlite3.Connection) -> None:
    """Reject conflicting lab object names before running any modifications."""
    for table in table_names(connection):
        if table not in EXPECTED_COLUMNS:
            continue
        actual = columns_for(connection, table)
        expected = tuple(name.upper() for name in EXPECTED_COLUMNS[table])
        if table == "P2_EMPLOYEE_ALT":
            accepted = {
                expected,
                ("EMPNO", "ENAME", "JOB", "MGR", "SAL", "COMMISSION"),
                ("EMPNO", "ENAME", "JOB", "MANAGER_NO", "SAL", "COMMISSION"),
            }
            if actual not in accepted:
                fail(
                    f"Existing table {table} has incompatible columns {actual}; "
                    "it was not changed."
                )
        elif actual != expected:
            fail(
                f"Existing table {table} has incompatible columns {actual}; "
                "expected {expected}. No practicals were run."
            )

    objects = {
        str(row[0]).upper(): str(row[1]).lower()
        for row in connection.execute(
            "SELECT name, type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        )
    }
    for name in EXPECTED_COLUMNS:
        if name.upper() in objects and objects[name.upper()] != "table":
            fail(
                f"Existing SQLite object {name} is a {objects[name.upper()]}, "
                "not a table; no practicals were run."
            )


def process_runner_directives(
    connection: sqlite3.Connection, script_name: str, script: str
) -> str:
    """Apply SQLite ALTER TABLE operations only when their change is needed."""
    if script_name != "02_employee_alter_update_delete.sql":
        return script

    replacements: dict[str, str] = {}
    columns = set(columns_for(connection, "P2_EMPLOYEE_ALT"))
    if not columns:
        columns = {"EMPNO", "ENAME", "JOB", "MGR", "SAL"}

    marker = "-- RUNNER: ADD COMMISSION IF MISSING"
    if marker in script:
        if "COMMISSION" not in columns:
            replacements[marker] = (
                "ALTER TABLE P2_EMPLOYEE_ALT ADD COLUMN COMMISSION REAL;"
            )
            columns.add("COMMISSION")
        else:
            replacements[marker] = "-- COMMISSION already exists."

    marker = "-- RUNNER: RENAME MGR TO MANAGER_NO IF NEEDED"
    if marker in script:
        if "MGR" in columns and "MANAGER_NO" not in columns:
            replacements[marker] = (
                "ALTER TABLE P2_EMPLOYEE_ALT "
                "RENAME COLUMN MGR TO MANAGER_NO;"
            )
            columns.remove("MGR")
            columns.add("MANAGER_NO")
        elif "MANAGER_NO" in columns and "MGR" not in columns:
            replacements[marker] = "-- Column already renamed."
        else:
            fail(
                "P2_EMPLOYEE_ALT must contain exactly one of MGR or MANAGER_NO."
            )

    for marker, replacement in replacements.items():
        script = script.replace(marker, replacement)
    if "MANAGER_NO" in columns and "MGR" not in columns:
        script = re.sub(r"\bMGR\b", "MANAGER_NO", script)
    return script


def execute_script(
    connection: sqlite3.Connection, script_name: str
) -> None:
    script_path = ROOT / script_name
    if not script_path.is_file():
        fail(f"Required practical script is missing: {script_path}")
    script = script_path.read_text(encoding="utf-8")
    script = process_runner_directives(connection, script_name, script)
    if script_name == "02_employee_alter_update_delete.sql":
        delete_section = "-- Q2(e):"
        before_delete, delete_and_verify = script.split(delete_section, maxsplit=1)
        connection.executescript(before_delete)
        inserted_rows = show_rows(
            connection,
            "P2: five sample rows after insert, updates, and column rename",
            "SELECT EMPNO, ENAME, JOB, MANAGER_NO, SAL, COMMISSION "
            "FROM P2_EMPLOYEE_ALT WHERE EMPNO BETWEEN 101 AND 105 "
            "ORDER BY EMPNO",
        )
        actual_keys = [(row[0], row[1], row[2]) for row in inserted_rows]
        expected_keys = [
            (101, "Arun Sen", "SUPPORT"),
            (102, "Bela Roy", "ANALYST"),
            (103, "Chirag Jain", "MANAGER"),
            (104, "Diya Nair", "ASSOCIATE"),
            (105, "Eshan Paul", "TRAINEE"),
        ]
        if actual_keys != expected_keys:
            raise AssertionError(
                f"Practical 2 expected five sample rows before deletion; "
                f"received {actual_keys!r}"
            )
        connection.executescript(delete_section + delete_and_verify)
    else:
        # executescript handles trigger bodies containing internal semicolons.
        connection.executescript(script)


def show_rows(
    connection: sqlite3.Connection,
    title: str,
    query: str,
    parameters: tuple[Any, ...] = (),
) -> list[tuple[Any, ...]]:
    rows = connection.execute(query, parameters).fetchall()
    print(f"\n{title}")
    if not rows:
        print("(no rows)")
        return rows
    for row in rows:
        print(" | ".join("NULL" if value is None else str(value) for value in row))
    return rows


def probe_expected_null_failure(
    connection: sqlite3.Connection,
    savepoint: str,
    insert_sql: str,
    values: tuple[Any, ...],
    expected_fragment: str,
) -> None:
    connection.execute(f"SAVEPOINT {savepoint}")
    try:
        connection.execute(insert_sql, values)
    except sqlite3.IntegrityError as error:
        connection.execute(f"ROLLBACK TO {savepoint}")
        connection.execute(f"RELEASE {savepoint}")
        if expected_fragment not in str(error).lower():
            raise AssertionError(
                f"Expected constraint error containing {expected_fragment!r}; "
                f"received {error!s}"
            ) from error
        print(f"PASS: rejected invalid insert as expected ({error}).")
    else:
        connection.execute(f"ROLLBACK TO {savepoint}")
        connection.execute(f"RELEASE {savepoint}")
        raise AssertionError(f"Expected insert to fail: {insert_sql}")


def run_practical_1(connection: sqlite3.Connection) -> None:
    before = connection.execute(
        "SELECT EMPNO, ENAME FROM P1_EMPLOYEE_TX "
        "WHERE EMPNO BETWEEN 91001 AND 91003 ORDER BY EMPNO"
    ).fetchall()
    show_rows(
        connection,
        "P1: existing transaction sample rows before the rollback demonstration",
        "SELECT EMPNO, ENAME FROM P1_EMPLOYEE_TX "
        "WHERE EMPNO BETWEEN 91001 AND 91003 ORDER BY EMPNO",
    )

    sample_rows = (
        (91001, "Asha Rao", "ANALYST", None, 72000, 5000),
        (91002, "Dev Shah", "CLERK", 91001, 48000, None),
        (91003, "Mina Das", "MANAGER", None, 95000, 12000),
    )
    connection.execute("BEGIN TRANSACTION")
    connection.executemany(
        """INSERT OR IGNORE INTO P1_EMPLOYEE_TX
           (EMPNO, ENAME, JOB, MANAGER_NO, SAL, COMMISSION)
           VALUES (?, ?, ?, ?, ?, ?)""",
        sample_rows,
    )
    during = show_rows(
        connection,
        "P1: three sample inserts visible inside the transaction",
        "SELECT EMPNO, ENAME, JOB, SAL FROM P1_EMPLOYEE_TX "
        "WHERE EMPNO BETWEEN 91001 AND 91003 ORDER BY EMPNO",
    )
    expected_visible = [
        (91001, "Asha Rao", "ANALYST", 72000.0),
        (91002, "Dev Shah", "CLERK", 48000.0),
        (91003, "Mina Das", "MANAGER", 95000.0),
    ]
    if during != expected_visible:
        connection.rollback()
        raise AssertionError(
            "The reserved Practical 1 sample IDs contain different existing "
            f"rows; no rows were overwritten. Found {during!r}."
        )
    connection.rollback()
    after = show_rows(
        connection,
        "P1: sample rows after ROLLBACK",
        "SELECT EMPNO, ENAME FROM P1_EMPLOYEE_TX "
        "WHERE EMPNO BETWEEN 91001 AND 91003 ORDER BY EMPNO",
    )
    if before != after:
        raise AssertionError("Practical 1 rollback changed pre-existing sample rows.")
    print("PASS: Practical 1 rollback preserved the pre-existing sample-ID rows.")

    connection.execute("SAVEPOINT p1_nullable_probe")
    next_empno = int(
        connection.execute(
            "SELECT COALESCE(MAX(EMPNO), 0) + 1 FROM P1_EMPLOYEE_TX"
        ).fetchone()[0]
    )
    connection.execute(
        "INSERT INTO P1_EMPLOYEE_TX "
        "(EMPNO, ENAME, JOB, MANAGER_NO, SAL, COMMISSION) "
        "VALUES (?, ?, NULL, NULL, NULL, NULL)",
        (next_empno, "Nullable Fields Test"),
    )
    nullable = connection.execute(
        "SELECT EMPNO, ENAME, JOB, MANAGER_NO, SAL, COMMISSION "
        "FROM P1_EMPLOYEE_TX WHERE EMPNO = ?",
        (next_empno,),
    ).fetchone()
    if nullable != (next_empno, "Nullable Fields Test", None, None, None, None):
        raise AssertionError(f"Optional NULL test returned unexpected row: {nullable}")
    print(f"PASS: nullable non-key fields accepted: {nullable}")
    connection.execute("ROLLBACK TO p1_nullable_probe")
    connection.execute("RELEASE p1_nullable_probe")

    probe_expected_null_failure(
        connection,
        "p1_null_empno",
        "INSERT INTO P1_EMPLOYEE_TX (EMPNO, ENAME) VALUES (?, ?)",
        (None, "Null EMPNO Test"),
        "not null",
    )
    next_empno = int(
        connection.execute(
            "SELECT COALESCE(MAX(EMPNO), 0) + 1 FROM P1_EMPLOYEE_TX"
        ).fetchone()[0]
    )
    probe_expected_null_failure(
        connection,
        "p1_null_ename",
        "INSERT INTO P1_EMPLOYEE_TX (EMPNO, ENAME) VALUES (?, ?)",
        (next_empno, None),
        "not null",
    )
    constraints = connection.execute(
        "PRAGMA table_info('P1_EMPLOYEE_TX')"
    ).fetchall()
    empno = next(row for row in constraints if str(row[1]).upper() == "EMPNO")
    ename = next(row for row in constraints if str(row[1]).upper() == "ENAME")
    if empno[5] != 1 or empno[3] != 1 or ename[3] != 1:
        raise AssertionError("EMPNO primary key or required NOT NULL was not found.")
    print("PASS: EMPNO primary key and EMPNO/ENAME NOT NULL constraints verified.")
    show_rows(
        connection,
        "P1: verification that the nullable probe rolled back",
        "SELECT COUNT(*) AS NULLABLE_TEST_REMAINING "
        "FROM P1_EMPLOYEE_TX WHERE ENAME = 'Nullable Fields Test'",
    )


def run_practical_2(connection: sqlite3.Connection) -> None:
    show_rows(
        connection,
        "P2: remaining sample employees after updates and the EMPNO 105 delete",
        "SELECT EMPNO, ENAME, JOB, MANAGER_NO, SAL, COMMISSION "
        "FROM P2_EMPLOYEE_ALT WHERE EMPNO BETWEEN 101 AND 105 "
        "ORDER BY EMPNO",
    )
    row_105 = connection.execute(
        "SELECT COUNT(*) FROM P2_EMPLOYEE_ALT "
        "WHERE EMPNO = 105 AND ENAME = 'Eshan Paul' AND JOB = 'TRAINEE'"
    ).fetchone()[0]
    if row_105 != 0:
        raise AssertionError("Practical 2 did not remove the identified sample EMPNO 105.")
    show_rows(
        connection,
        "P2: EMPNO 105 deletion verification",
        "SELECT COUNT(*) AS SAMPLE_105_REMAINING FROM P2_EMPLOYEE_ALT "
        "WHERE EMPNO = 105 AND ENAME = 'Eshan Paul' AND JOB = 'TRAINEE'",
    )
    columns = columns_for(connection, "P2_EMPLOYEE_ALT")
    if "COMMISSION" not in columns or "MANAGER_NO" not in columns or "MGR" in columns:
        raise AssertionError(f"Practical 2 ALTER/RENAME failed: columns are {columns}")
    print("PASS: COMMISSION was added and MGR was renamed to MANAGER_NO.")


COMPANY_QUERIES: tuple[tuple[str, str], ...] = (
    (
        "P3 Q1: projects involving Scott as worker or department manager "
        "(expected 501, 502, 701)",
        """SELECT p.PNo
           FROM PROJECT AS p
           WHERE EXISTS (
               SELECT 1 FROM WORKS_ON AS w
               JOIN EMPLOYEE AS e ON e.SSN = w.SSN
               WHERE w.PNo = p.PNo
                 AND TRIM(e.Name) LIKE '% Scott'
           )
           OR EXISTS (
               SELECT 1 FROM DEPARTMENT AS d
               JOIN EMPLOYEE AS e ON e.SSN = d.MgrSSN
               WHERE d.DNo = p.DNo
                 AND TRIM(e.Name) LIKE '% Scott'
           )
           ORDER BY p.PNo""",
    ),
    (
        "P3 Q2: proposed 10% raise for IoT workers "
        "(expected 2001=990000, 5001=825000, 5002=715000)",
        """SELECT e.SSN, e.Name, e.Salary,
                  ROUND(e.Salary * 1.10, 2) AS PROPOSED_SALARY
           FROM EMPLOYEE AS e
           WHERE EXISTS (
               SELECT 1 FROM WORKS_ON AS w
               JOIN PROJECT AS p ON p.PNo = w.PNo
               WHERE w.SSN = e.SSN AND p.PName = 'IoT'
           )
           ORDER BY e.SSN""",
    ),
    (
        "P3 Q3: Accounts salary aggregates "
        "(expected 1620000 / 900000 / 720000 / 810000)",
        """SELECT d.DName, SUM(e.Salary), MAX(e.Salary), MIN(e.Salary),
                  ROUND(AVG(e.Salary), 2)
           FROM DEPARTMENT AS d
           JOIN EMPLOYEE AS e ON e.DNo = d.DNo
           WHERE d.DName = 'Accounts'
           GROUP BY d.DName""",
    ),
    (
        "P3 Q4: employees working on every department-5 project (expected 5001)",
        """SELECT e.SSN, e.Name
           FROM EMPLOYEE AS e
           WHERE NOT EXISTS (
               SELECT 1 FROM PROJECT AS p
               WHERE p.DNo = 5
                 AND NOT EXISTS (
                     SELECT 1 FROM WORKS_ON AS w
                     WHERE w.SSN = e.SSN AND w.PNo = p.PNo
                 )
           )
           ORDER BY e.SSN""",
    ),
    (
        "P3 Q5: departments with >5 employees and count earning >600000 "
        "(expected department 5, count 4)",
        """SELECT e.DNo, COUNT(*)
           FROM EMPLOYEE AS e
           WHERE e.Salary > 600000
             AND e.DNo IN (
                 SELECT DNo FROM EMPLOYEE
                 GROUP BY DNo HAVING COUNT(*) > 5
             )
           GROUP BY e.DNo
           ORDER BY e.DNo""",
    ),
)


EXPECTED_COMPANY_RESULTS: tuple[list[tuple[Any, ...]], ...] = (
    [(501,), (502,), (701,)],
    [
        ("2001", "Robert Scott", 900000.0, 990000.0),
        ("5001", "Ira Mehta", 750000.0, 825000.0),
        ("5002", "Kabir Rao", 650000.0, 715000.0),
    ],
    [("Accounts", 1620000.0, 900000.0, 720000.0, 810000.0)],
    [("5001", "Ira Mehta")],
    [(5, 4)],
)


def run_practical_3(connection: sqlite3.Connection) -> None:
    for index, (title, query) in enumerate(COMPANY_QUERIES):
        rows = show_rows(connection, title, query)
        if rows != EXPECTED_COMPANY_RESULTS[index]:
            raise AssertionError(
                f"{title}: expected {EXPECTED_COMPANY_RESULTS[index]!r}, "
                f"received {rows!r}"
            )
    print("PASS: all five Practical 3 query results match the sample expectations.")


def run_practical_4(connection: sqlite3.Connection) -> None:
    audit = connection.execute(
        """SELECT ACTION, OLD_SALARY, NEW_SALARY, SALARY_DIFFERENCE
           FROM CUSTOMERS_AUDIT
           ORDER BY AUDIT_ID DESC
           LIMIT 3"""
    ).fetchall()
    expected = [
        ("DELETE", 57500.0, None, None),
        ("UPDATE", 50000.0, 57500.0, 7500.0),
        ("INSERT", None, 50000.0, None),
    ]
    if audit != expected:
        raise AssertionError(
            f"Practical 4 trigger audit did not match expected events: {audit!r}"
        )
    show_rows(
        connection,
        "P4: latest trigger audit entries (INSERT, UPDATE +7500, DELETE)",
        """SELECT AUDIT_ID, CUSTOMER_ID, ACTION, OLD_SALARY,
                  NEW_SALARY, SALARY_DIFFERENCE
           FROM CUSTOMERS_AUDIT ORDER BY AUDIT_ID DESC LIMIT 3""",
    )
    remaining = connection.execute(
        "SELECT COUNT(*) FROM CUSTOMERS WHERE NAME = 'Practical 4 Trigger Test'"
    ).fetchone()[0]
    if remaining != 0:
        raise AssertionError("Practical 4 trigger test customer was not deleted.")
    print("PASS: all three SQLite triggers recorded the required salary images.")


def run_practical_5(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute(
            """SELECT E_ID, E_NAME, AGE, SALARY
               FROM CURSOR_EMPLOYEE
               WHERE E_ID BETWEEN 95001 AND 95003
               ORDER BY E_ID"""
        )
        rows = cursor.fetchall()
        expected = [
            (95001, "Pooja Kulkarni", 24, 52000.0),
            (95002, "Rahul Menon", 29, 68000.0),
            (95003, "Sara Fernandes", 32, 81000.0),
        ]
        if rows != expected:
            raise AssertionError(
                f"Practical 5 cursor rows mismatch: expected {expected!r}, got {rows!r}"
            )
        print("\nP5: Python sqlite3 cursor output (not an Oracle PL/SQL cursor)")
        for row in rows:
            print(
                f"E_ID={row[0]}, E_NAME={row[1]}, AGE={row[2]}, "
                f"SALARY={row[3]:.0f}"
            )
        print("PASS: fetched all expected records with Python sqlite3.")
    finally:
        cursor.close()


def verify_foreign_keys(connection: sqlite3.Connection) -> None:
    violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise AssertionError(f"SQLite foreign-key violations found: {violations!r}")
    print("PASS: PRAGMA foreign_key_check returned no violations.")


def run_project() -> int:
    existed = DATABASE.exists()
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = None
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        validate_existing_schema(connection)

        print(f"SQLite version: {sqlite3.sqlite_version}")
        print(f"Database: {DATABASE}")
        print(
            "Database file already existed; existing tables and rows are preserved."
            if existed
            else "Creating the project database file; no existing database was replaced."
        )

        checks = (
            run_practical_1,
            run_practical_2,
            run_practical_3,
            run_practical_4,
            run_practical_5,
        )
        for number, (script_name, verifier) in enumerate(
            zip(SCRIPT_ORDER, checks), start=1
        ):
            print(f"\n{'=' * 72}\nPractical {number}: {script_name}")
            execute_script(connection, script_name)
            verifier(connection)
            if number == 3:
                verify_foreign_keys(connection)

        print("\nAll five practicals executed and their verification checks passed.")
        return 0
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run all SQLite practicals using Python's standard library."
    )
    parser.parse_args()
    try:
        return run_project()
    except (sqlite3.Error, AssertionError, RuntimeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
