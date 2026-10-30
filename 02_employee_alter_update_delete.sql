-- Practical 2: ALTER TABLE, UPDATE, RENAME COLUMN, and DELETE.
-- P2 uses a separate employee structure from Practicals 1 and 3.

-- Q2(a): Begin with the assignment's five-column structure.
CREATE TABLE IF NOT EXISTS P2_EMPLOYEE_ALT (
    EMPNO INT NOT NULL PRIMARY KEY,
    ENAME TEXT NOT NULL,
    JOB   TEXT,
    MGR   INT,
    SAL   REAL
);

-- RUNNER: ADD COMMISSION IF MISSING
-- The Python runner executes ALTER TABLE ADD COLUMN only if required.

-- Q2(b): Insert five records without replacing existing rows.
INSERT OR IGNORE INTO P2_EMPLOYEE_ALT
    (EMPNO, ENAME, JOB, MGR, SAL, COMMISSION)
VALUES
    (101, 'Arun Sen', 'CLERK', 103, 42000, NULL),
    (102, 'Bela Roy', 'ANALYST', 103, 65000, 3500),
    (103, 'Chirag Jain', 'MANAGER', NULL, 90000, NULL),
    (104, 'Diya Nair', 'CLERK', 103, 44000, 1500),
    (105, 'Eshan Paul', 'TRAINEE', 103, 38000, NULL);

SELECT EMPNO, ENAME, JOB, MGR, SAL, COMMISSION
FROM P2_EMPLOYEE_ALT
WHERE EMPNO BETWEEN 101 AND 105
ORDER BY EMPNO;

-- Q2(c): Update sample jobs only when their names identify the lab rows.
UPDATE P2_EMPLOYEE_ALT
SET JOB = CASE EMPNO
              WHEN 101 THEN 'SUPPORT'
              WHEN 104 THEN 'ASSOCIATE'
          END
WHERE (EMPNO = 101 AND ENAME = 'Arun Sen')
   OR (EMPNO = 104 AND ENAME = 'Diya Nair');

SELECT EMPNO, ENAME, JOB
FROM P2_EMPLOYEE_ALT
WHERE EMPNO IN (101, 104)
ORDER BY EMPNO;

-- Q2(d): SQLite supports RENAME COLUMN. The runner skips this if already
-- renamed, allowing the project to run repeatedly.
-- RUNNER: RENAME MGR TO MANAGER_NO IF NEEDED

SELECT EMPNO, ENAME, MANAGER_NO
FROM P2_EMPLOYEE_ALT
WHERE EMPNO BETWEEN 101 AND 105
ORDER BY EMPNO;

-- Q2(e): Delete the assignment's sample employee 105, but only when its
-- name and job still match this practical's sample row.
DELETE FROM P2_EMPLOYEE_ALT
WHERE EMPNO = 105
  AND ENAME = 'Eshan Paul'
  AND JOB = 'TRAINEE';

SELECT EMPNO, ENAME
FROM P2_EMPLOYEE_ALT
WHERE EMPNO BETWEEN 101 AND 105
ORDER BY EMPNO;
SELECT COUNT(*) AS SAMPLE_105_REMAINING
FROM P2_EMPLOYEE_ALT
WHERE EMPNO = 105
  AND ENAME = 'Eshan Paul'
  AND JOB = 'TRAINEE';
