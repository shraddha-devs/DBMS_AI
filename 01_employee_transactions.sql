-- Practical 1: Employee transactions, constraints, and NULL behavior.
-- SQLite cannot create database users or grant database privileges.
-- P1 uses a prefixed table name to avoid conflict with Practical 3 EMPLOYEE.

CREATE TABLE IF NOT EXISTS P1_EMPLOYEE_TX (
    EMPNO       INT NOT NULL PRIMARY KEY,
    ENAME       TEXT NOT NULL,
    JOB         TEXT,
    MANAGER_NO  INT,
    SAL         REAL,
    COMMISSION  REAL
);

-- Q1(a): Demonstrate three inserts inside a transaction, then ROLLBACK.
BEGIN TRANSACTION;
INSERT OR IGNORE INTO P1_EMPLOYEE_TX
    (EMPNO, ENAME, JOB, MANAGER_NO, SAL, COMMISSION)
VALUES
    (91001, 'Asha Rao', 'ANALYST', NULL, 72000, 5000),
    (91002, 'Dev Shah', 'CLERK', 91001, 48000, NULL),
    (91003, 'Mina Das', 'MANAGER', NULL, 95000, 12000);

-- Verification before rollback: newly inserted rows are visible here.
SELECT EMPNO, ENAME, JOB, SAL
FROM P1_EMPLOYEE_TX
WHERE EMPNO BETWEEN 91001 AND 91003
ORDER BY EMPNO;
ROLLBACK;

-- Verification after rollback: only rows that existed before this
-- transaction can remain in the reserved sample-ID range.
SELECT EMPNO, ENAME
FROM P1_EMPLOYEE_TX
WHERE EMPNO BETWEEN 91001 AND 91003
ORDER BY EMPNO;

-- Q1(b): Required/optional NULL tests are performed by run_practicals.py.
-- It inserts one row with NULL optional fields inside a savepoint, then
-- confirms NULL EMPNO and NULL ENAME fail the NOT NULL constraints.
-- SQLite cannot add a primary key or NOT NULL constraint with ALTER COLUMN;
-- they are declared when this table is created.
