-- Practical 3: Company database, sample data, and five SQLite queries.
-- All object names and query requirements follow the company assignment.

-- Q3(a): Create tables in dependency order. SQLite permits references to a
-- table created later; the sample loading sequence satisfies both FKs.
CREATE TABLE IF NOT EXISTS EMPLOYEE (
    SSN       TEXT NOT NULL PRIMARY KEY,
    Name      TEXT NOT NULL,
    Address   TEXT,
    Sex       TEXT CHECK (Sex IN ('F', 'M', 'X')),
    Salary    REAL NOT NULL,
    SuperSSN  TEXT REFERENCES EMPLOYEE (SSN),
    DNo       INTEGER REFERENCES DEPARTMENT (DNo)
);

CREATE TABLE IF NOT EXISTS DEPARTMENT (
    DNo          INTEGER NOT NULL PRIMARY KEY,
    DName        TEXT NOT NULL UNIQUE,
    MgrSSN       TEXT NOT NULL REFERENCES EMPLOYEE (SSN),
    MgrStartDate TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS PROJECT (
    PNo       INTEGER NOT NULL PRIMARY KEY,
    PName     TEXT NOT NULL,
    PLocation TEXT NOT NULL,
    DNo       INTEGER NOT NULL REFERENCES DEPARTMENT (DNo)
);

CREATE TABLE IF NOT EXISTS DLOCATION (
    DNo  INTEGER NOT NULL REFERENCES DEPARTMENT (DNo),
    DLoc TEXT NOT NULL,
    PRIMARY KEY (DNo, DLoc)
);

CREATE TABLE IF NOT EXISTS WORKS_ON (
    SSN   TEXT NOT NULL REFERENCES EMPLOYEE (SSN),
    PNo   INTEGER NOT NULL REFERENCES PROJECT (PNo),
    Hours REAL NOT NULL CHECK (Hours >= 0),
    PRIMARY KEY (SSN, PNo)
);

-- Q3(b): Insert manager employees before their departments. DNo is updated
-- after department rows exist, satisfying the employee-department FK.
INSERT OR IGNORE INTO EMPLOYEE
    (SSN, Name, Address, Sex, Salary, SuperSSN, DNo)
VALUES
    ('2001', 'Robert Scott', '12 Lake Road', 'M', 900000, NULL, NULL),
    ('2002', 'Anita Bose', '8 Market Street', 'F', 720000, '2001', NULL);

INSERT OR IGNORE INTO DEPARTMENT (DNo, DName, MgrSSN, MgrStartDate)
VALUES
    (5, 'Research', '2001', '2022-01-15'),
    (10, 'Accounts', '2002', '2021-06-01'),
    (20, 'Engineering', '2001', '2023-03-01');

UPDATE EMPLOYEE
SET DNo = 10
WHERE SSN = '2001' AND Name = 'Robert Scott' AND DNo IS NULL;
UPDATE EMPLOYEE
SET DNo = 10
WHERE SSN = '2002' AND Name = 'Anita Bose' AND DNo IS NULL;

-- Six department-5 employees make the >5 department filter meaningful.
INSERT OR IGNORE INTO EMPLOYEE
    (SSN, Name, Address, Sex, Salary, SuperSSN, DNo)
VALUES
    ('5001', 'Ira Mehta', '1 Hill Lane', 'F', 750000, '2001', 5),
    ('5002', 'Kabir Rao', '2 Hill Lane', 'M', 650000, '2001', 5),
    ('5003', 'Leena Shah', '3 Hill Lane', 'F', 610000, '2001', 5),
    ('5004', 'Manav Das', '4 Hill Lane', 'M', 580000, '2001', 5),
    ('5005', 'Nisha Iyer', '5 Hill Lane', 'F', 900000, '2001', 5),
    ('5006', 'Omar Ali', '6 Hill Lane', 'M', 600000, '2001', 5);

INSERT OR IGNORE INTO PROJECT (PNo, PName, PLocation, DNo)
VALUES
    (501, 'IoT', 'Bengaluru', 5),
    (502, 'Smart Grid', 'Mysuru', 5),
    (601, 'Ledger Modernization', 'Bengaluru', 10),
    (701, 'Device Platform', 'Mangaluru', 20);

INSERT OR IGNORE INTO DLOCATION (DNo, DLoc)
VALUES
    (5, 'Bengaluru'),
    (5, 'Mysuru'),
    (10, 'Bengaluru'),
    (20, 'Mangaluru');

INSERT OR IGNORE INTO WORKS_ON (SSN, PNo, Hours)
VALUES
    ('2001', 501, 6),
    ('5001', 501, 20),
    ('5001', 502, 12),
    ('5002', 501, 15),
    ('5003', 502, 18),
    ('2002', 601, 10),
    ('5004', 701, 8);

-- Q3(c): Seed verification counts.
SELECT 'EMPLOYEE' AS TABLE_NAME, COUNT(*) AS SAMPLE_ROWS
FROM EMPLOYEE
WHERE SSN IN ('2001','2002','5001','5002','5003','5004','5005','5006')
UNION ALL
SELECT 'DEPARTMENT', COUNT(*) FROM DEPARTMENT WHERE DNo IN (5,10,20)
UNION ALL
SELECT 'PROJECT', COUNT(*) FROM PROJECT WHERE PNo IN (501,502,601,701)
UNION ALL
SELECT 'DLOCATION', COUNT(*) FROM DLOCATION WHERE DNo IN (5,10,20)
UNION ALL
SELECT 'WORKS_ON', COUNT(*) FROM WORKS_ON
WHERE (SSN = '2001' AND PNo = 501)
   OR (SSN = '5001' AND PNo IN (501,502))
   OR (SSN = '5002' AND PNo = 501)
   OR (SSN = '5003' AND PNo = 502)
   OR (SSN = '2002' AND PNo = 601)
   OR (SSN = '5004' AND PNo = 701);

-- Q3(d)(1): Project numbers for Scott as a worker OR the controlling
-- department's manager. OR/EXISTS returns each project number only once.
SELECT p.PNo AS PROJECT_NUMBER
FROM PROJECT AS p
WHERE EXISTS (
    SELECT 1
    FROM WORKS_ON AS w
    JOIN EMPLOYEE AS e ON e.SSN = w.SSN
    WHERE w.PNo = p.PNo
      AND TRIM(e.Name) LIKE '% Scott'
)
OR EXISTS (
    SELECT 1
    FROM DEPARTMENT AS d
    JOIN EMPLOYEE AS e ON e.SSN = d.MgrSSN
    WHERE d.DNo = p.DNo
      AND TRIM(e.Name) LIKE '% Scott'
)
ORDER BY PROJECT_NUMBER;
-- Expected: 501, 502, 701; Scott works on 501 and manages departments 5/20.

-- Q3(d)(2): Proposed 10% raise for IoT workers; salaries are not updated.
SELECT e.SSN, e.Name, e.Salary AS CURRENT_SALARY,
       ROUND(e.Salary * 1.10, 2) AS PROPOSED_SALARY
FROM EMPLOYEE AS e
WHERE EXISTS (
    SELECT 1
    FROM WORKS_ON AS w
    JOIN PROJECT AS p ON p.PNo = w.PNo
    WHERE w.SSN = e.SSN AND p.PName = 'IoT'
)
ORDER BY e.SSN;
-- Expected proposed salaries: 2001=990000, 5001=825000, 5002=715000.

-- Q3(d)(3): SUM, MAX, MIN, and AVG salaries in Accounts.
SELECT d.DName AS DEPARTMENT_NAME,
       SUM(e.Salary) AS TOTAL_SALARY,
       MAX(e.Salary) AS MAX_SALARY,
       MIN(e.Salary) AS MIN_SALARY,
       ROUND(AVG(e.Salary), 2) AS AVG_SALARY
FROM DEPARTMENT AS d
JOIN EMPLOYEE AS e ON e.DNo = d.DNo
WHERE d.DName = 'Accounts'
GROUP BY d.DName;
-- Expected: 1620000 / 900000 / 720000 / 810000.

-- Q3(d)(4): Employees working on every project controlled by department 5.
SELECT e.SSN, e.Name
FROM EMPLOYEE AS e
WHERE NOT EXISTS (
    SELECT 1
    FROM PROJECT AS p
    WHERE p.DNo = 5
      AND NOT EXISTS (
          SELECT 1
          FROM WORKS_ON AS w
          WHERE w.SSN = e.SSN AND w.PNo = p.PNo
      )
)
ORDER BY e.SSN;
-- Expected: 5001.

-- Q3(d)(5): In departments with more than five employees, count employees
-- earning more than Rs. 6,00,000.
SELECT e.DNo AS DEPARTMENT_NUMBER,
       COUNT(*) AS EMPLOYEES_ABOVE_600000
FROM EMPLOYEE AS e
WHERE e.Salary > 600000
  AND e.DNo IN (
      SELECT DNo
      FROM EMPLOYEE
      GROUP BY DNo
      HAVING COUNT(*) > 5
  )
GROUP BY e.DNo
ORDER BY e.DNo;
-- Expected: department 5, count 4.
