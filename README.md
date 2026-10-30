# SQLite SQL Practicals and Database AI Assistant (Python 3.13)

This project adapts five Oracle SQL/PLSQL lab practicals to one local SQLite
database, `practicals.db`, and Python's built-in `sqlite3` module. It requires
no administrator rights. It also includes a local Flask website for asking
natural-language questions about the live database.

## Database AI Assistant website

The assistant connects read-only to the existing `practicals.db` file. It
uses local keyword/synonym intent recognition and an allow-list of parameterized
SELECT templates; it does not send questions to a third party, require an API
key, or execute user-provided SQL. No chatbot request changes employee/customer
data. The Flask server binds only to `127.0.0.1`.

Install the single web dependency as the current Windows user (no administrator
permissions required), then start the application:

```powershell
cd D:\PROJECT\sql_practicals
python -m pip install --user -r .\requirements.txt
python .\app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in a browser. Stop the
development server with **Ctrl+C** in the terminal.

The sidebar shows database connection/table counts, supported practicals and
recent questions. Suggested questions, message history, clear/new conversation,
mobile navigation, result tables and expandable read-only SQL are included.
Natural-language answers are made from actual query rows. Unknown questions
receive a clarification message. If Flask is installed in a virtual
environment instead of with `--user`, activate that environment before running
`python .\app.py`.

The assistant does not perform INSERT/UPDATE/DELETE on the database; write
operations are not offered in chat, so they cannot happen without explicit
confirmation. Practical execution remains a separate command below.

### Assistant API

- `GET /api/database-status` — read-only connection state, table names, columns,
  and row counts.
- `GET /api/suggestions` — suggested natural-language prompts grouped by lab.
- `POST /api/chat` — accepts `{"question":"..."}` and returns detected intent,
  live result rows/count, natural-language answer, and approved SQL when used.
- `GET /api/history` and `DELETE /api/history` — read or clear the current
  signed-cookie session's recent question history.

Requests are length-checked; invalid or unknown intents do not run SQL. The SQL
registry only contains SELECT statements, and all extracted names, IDs,
thresholds and limits are passed as bound parameters.

## Run the complete project

Open PowerShell in `D:\PROJECT\sql_practicals` and run:

```powershell
python .\run_practicals.py
```

Or run it from any directory with the absolute script path:

```powershell
python D:\PROJECT\sql_practicals\run_practicals.py
```

The runner creates `practicals.db` the first time, then reuses it on later
runs. It never deletes or replaces the database. Existing unrelated tables
are preserved. Before executing practicals, it checks that any existing lab
tables have compatible columns and stops with an error if a same-named table
is incompatible. It uses `CREATE TABLE IF NOT EXISTS` and guarded sample
inserts instead of destructive cleanup.

`00_master.sql` documents the script order; the actual master execution path
is `run_practicals.py`. The runner reads and executes each SQL practical in
order. It handles SQLite's conditional `ALTER TABLE` operations, uses
`sqlite3.Connection.executescript()` to correctly execute multi-statement
trigger definitions, and prints and checks expected query/cursor output.

## Requirements and Oracle compatibility

- Python 3.13 (the scripts use only the Python standard library).
- SQLite is included with Python. The environment used to verify this project
  reports Python 3.13.13 and SQLite 3.50.4.
- VS Code's existing SQLite extension can inspect `practicals.db`, but it is
  not required to run the project.
- SQLite does not provide Oracle database users, `GRANT`/`REVOKE` privileges,
  Oracle PL/SQL blocks, `DBMS_OUTPUT`, or Oracle explicit cursors. Practical 1
  documents the user/privilege limitation; Practical 4 uses SQLite `OLD` and
  `NEW` trigger values; Practical 5 uses a Python `sqlite3` cursor. These are
  deliberate database-specific adaptations, not Oracle executions.
- SQLite cannot add primary-key or `NOT NULL` constraints to an existing
  column using Oracle-style `ALTER TABLE ... MODIFY`. Practical 1 declares
  its constraints at table creation. Practical 2 demonstrates SQLite's
  supported `ADD COLUMN` and `RENAME COLUMN`.
- A project database file is local state and is ignored by `.gitignore`.

## Verification performed

The complete runner was executed successfully against the workspace database
and in a separate clean temporary directory. The clean first-run check
verified all five practicals, the four remaining P2 sample employees after
the required EMPNO 105 delete, the three P4 audit events, SQLite integrity,
and zero foreign-key violations. The existing workspace database was also
run repeatedly; the practicals remained valid and audit rows accumulated
without dropping tables or replacing the database.

The five Practical 3 result sets were compared to the expected values in the
runner. Practical 1's insert/rollback and NULL constraint probes, Practical 2
column migration, Practical 4's +7500 salary delta, and Practical 5's three
fetched rows were all checked by executed assertions. No Oracle database or
Oracle client was used.

The Database AI Assistant's `test_app.py` checks the requested 15 question
types, variations for maximum salary and Accounts aggregates, database-backed
result rows, employee-105 deletion without reconstructing the row, SQL
injection rejection, API responses, web page delivery, chat history and INR
formatting. The test suite also compares the database file SHA-256 before and
after the read-only chat requests.

Run the assistant checks with:

```powershell
python -m unittest .\test_app.py -v
```

## Practical files and verification

### Practical 1 — Employee transactions and constraints

File: `01_employee_transactions.sql`; table: `P1_EMPLOYEE_TX`.

- Creates `EMPNO`, `ENAME`, `JOB`, `MANAGER_NO`, `SAL`, `COMMISSION`, with an
  `EMPNO` primary key and `EMPNO`/`ENAME` `NOT NULL`.
- Inserts three sample records in a transaction, shows them, rolls back, and
  confirms pre-existing data is unchanged.
- Python inserts and rolls back a test row with NULL optional fields; then
  verifies actual NULL `EMPNO` and `ENAME` inserts fail their constraints.
- SQLite cannot create a database user or grant database privileges. Those
  were Oracle/DBA-specific parts of the original question.

Expected checks: three transaction inserts disappear after rollback; optional
NULL values are accepted; NULL `EMPNO` and `ENAME` are rejected.

### Practical 2 — ALTER, UPDATE, RENAME, DELETE

File: `02_employee_alter_update_delete.sql`; table: `P2_EMPLOYEE_ALT`.

- Starts with the five requested columns, adds `COMMISSION` using
  `ALTER TABLE ... ADD COLUMN`, and inserts five sample records.
- Updates the jobs for the sample employees 101 and 104.
- Renames `MGR` to `MANAGER_NO`.
- Deletes employee 105 only if its ID, sample name, and sample job match.

Expected checks: sample jobs are `SUPPORT` and `ASSOCIATE`; the renamed column
is present; the identified sample employee 105 has been deleted. The runner
handles the add/rename steps conditionally so repeat runs work.

### Practical 3 — Company tables and queries

File: `03_company_queries.sql`; tables: `EMPLOYEE`, `DEPARTMENT`, `PROJECT`,
`DLOCATION`, and `WORKS_ON`.

The sample data has Scott as a project worker and as the manager for
departments 5 and 20; two department-5 projects; Accounts employees; and six
department-5 employees, four of whom earn more than Rs. 6,00,000.

| Question | SQLite query result expected |
|---|---|
| Scott worker or controlling department manager | Project numbers `501`, `502`, `701`, once each |
| Proposed 10% raise for IoT workers | SSN `2001`: `990000`; `5001`: `825000`; `5002`: `715000` |
| Accounts salary aggregates | SUM `1620000`, MAX `900000`, MIN `720000`, AVG `810000` |
| Employee works on every department-5 project (`NOT EXISTS`) | SSN `5001`, Ira Mehta |
| Departments with >5 employees; count earning >600000 | Department `5`, count `4` |

Stored salaries are not updated by the proposed raise query. Foreign keys are
enabled by the runner and checked after this practical.

### Practical 4 — CUSTOMERS triggers and audit table

File: `04_customer_trigger.sql`; tables: `CUSTOMERS` and `CUSTOMERS_AUDIT`.

Three SQLite row-level triggers write INSERT, UPDATE, and DELETE events to
the audit table. For UPDATE, the audit field `SALARY_DIFFERENCE` is
`NEW.SALARY - OLD.SALARY`. INSERT has no old salary, and DELETE has no new
salary, so the unavailable value and difference are NULL. SQLite trigger
pseudocolumns are `OLD.column` and `NEW.column`; they are not Oracle's
`:OLD`/`:NEW`.

The script inserts a generated test customer, updates its salary from 50000
to 57500, deletes it, and retains the three audit rows.

Expected latest audit events: INSERT (new salary 50000), UPDATE (difference
7500), DELETE (old salary 57500). The test customer itself is not left in
`CUSTOMERS`.

### Practical 5 — Employee record iteration

File: `05_employee_cursor.sql`; table: `CURSOR_EMPLOYEE`.

The SQL file creates the table and sample records. `run_practicals.py` opens a
Python `sqlite3.Cursor`, executes a SELECT, fetches and displays all three
records, and closes the cursor. This is a Python DB-API cursor, **not** an
Oracle PL/SQL explicit cursor.

Expected records: Pooja Kulkarni (24, 52000), Rahul Menon (29, 68000), and
Sara Fernandes (32, 81000).

## SQL file execution

The practical `.sql` files use SQLite syntax. The supported complete workflow
is the Python runner above: it processes the conditional migration markers in
Practical 2, handles trigger definitions, runs the Python-only Practical 1
constraint probes and Practical 5 cursor, and validates expected output.
`00_master.sql` is a reference file and is not an executable Oracle or SQLite
master script.

To inspect the generated data in Python, for example:

```powershell
python -c "import sqlite3; c=sqlite3.connect(r'D:\PROJECT\sql_practicals\practicals.db'); print(c.execute('SELECT EMPNO, ENAME FROM P2_EMPLOYEE_ALT ORDER BY EMPNO').fetchall()); c.close()"
```

## Assignment coverage checklist

| Original requirement | SQLite implementation |
|---|---|
| P1 Employee columns, three inserts, ROLLBACK and verification | `01_employee_transactions.sql`; runner verifies rollback. |
| P1 primary key, NOT NULL, NULL acceptance/rejection | Constraints in P1 table; runner performs and checks actual inserts. |
| P1 create user and grant privileges | Documented as Oracle-only and unavailable in SQLite. |
| P2 five Employee columns, add commission, five rows | `02_employee_alter_update_delete.sql`; runner performs conditional `ALTER TABLE ADD COLUMN`. |
| P2 update jobs, rename column, delete 105 | Practical 2 SQL and runner verification. |
| P3 five company tables and keys | `03_company_queries.sql`; foreign keys checked by runner. |
| P3 Scott involvement projects | Query 1, duplicate-free `EXISTS` logic. |
| P3 proposed IoT 10% raise | Query 2; computed only, never stored. |
| P3 Accounts salary SUM/MAX/MIN/AVG | Query 3. |
| P3 all department-5 projects with `NOT EXISTS` | Query 4. |
| P3 department count and >5 employee filter | Query 5. |
| P4 INSERT/UPDATE/DELETE trigger and salary differences | `04_customer_trigger.sql`; audit table captures each event and update difference. |
| P5 explicit-cursor assignment requirement | Adapted to a Python `sqlite3` cursor in `run_practicals.py`; not represented as Oracle PL/SQL. |
| One local database, no silent replacement | `run_practicals.py` uses `practicals.db`, preserves it, and validates pre-existing table schemas. |
