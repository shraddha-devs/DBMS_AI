-- Practical 5: Sample table for the Python sqlite3 cursor practical.
-- This is NOT an Oracle PL/SQL explicit cursor; fetching is implemented by
-- run_practicals.py using Python's standard-library sqlite3 module.

CREATE TABLE IF NOT EXISTS CURSOR_EMPLOYEE (
    E_ID   INT NOT NULL PRIMARY KEY,
    E_NAME TEXT NOT NULL,
    AGE    INTEGER,
    SALARY REAL
);

-- Q5(a): Insert sample rows without replacing existing rows.
INSERT OR IGNORE INTO CURSOR_EMPLOYEE (E_ID, E_NAME, AGE, SALARY)
VALUES
    (95001, 'Pooja Kulkarni', 24, 52000),
    (95002, 'Rahul Menon', 29, 68000),
    (95003, 'Sara Fernandes', 32, 81000);

-- Q5(b): run_practicals.py declares a sqlite3 cursor, executes this SELECT,
-- iterates through all rows, displays them, and closes the cursor.
SELECT E_ID, E_NAME, AGE, SALARY
FROM CURSOR_EMPLOYEE
WHERE E_ID BETWEEN 95001 AND 95003
ORDER BY E_ID;
