"""Functional tests for natural-language routing and the local Flask API."""

from __future__ import annotations

import hashlib
import sqlite3
import unittest
from pathlib import Path

from app import create_app
from database import DATABASE_PATH, available_entities, connect_readonly
from nlp_processor import classify_question


class AssistantIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.original_hash = hashlib.sha256(DATABASE_PATH.read_bytes()).hexdigest()
        cls.connection = connect_readonly()
        entities = available_entities(cls.connection)
        cls.departments = entities["department_names"]
        cls.projects = entities["project_names"]
        cls.employee_records = entities["employee_records"]
        cls.connection.close()
        cls.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(DATABASE_PATH),
                "SECRET_KEY": "test-session-secret",
            }
        )
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls) -> None:
        after_hash = hashlib.sha256(DATABASE_PATH.read_bytes()).hexdigest()
        if after_hash != cls.original_hash:
            raise AssertionError("The assistant modified the original practicals.db.")

    def ask(self, question: str) -> dict:
        response = self.client.post("/api/chat", json={"question": question})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def intent_for(self, question: str) -> str | None:
        result = classify_question(
            question,
            department_names=self.departments,
            project_names=self.projects,
            employee_records=self.employee_records,
        )
        return result.name if result else None

    def test_requested_fifteen_questions(self) -> None:
        cases = [
            ("What is rollback?", "rollback_explanation"),
            ("Show the employee records in Practical 2.", "p2_employees"),
            ("Which employee was deleted?", "p2_employee_105"),
            ("What is the highest salary?", "company_highest_salary"),
            ("Which projects involve Scott?", "projects_scott"),
            ("Show IoT employees with their proposed increased salaries.", "iot_salary_raise"),
            ("Calculate the total salary in Accounts.", "department_salary_aggregates"),
            ("Who works on all department 5 projects?", "employees_all_d5_projects"),
            ("Which departments have more than five employees?", "departments_salary_threshold"),
            ("Show the latest customer audit entries.", "customer_audit"),
            ("What was the salary difference after the customer update?", "customer_salary_difference"),
            ("Show all cursor employee records.", "cursor_employees"),
            ("Who is the oldest cursor employee?", "cursor_oldest"),
            ("Explain the difference between a trigger and a cursor.", "trigger_cursor_difference"),
            ("Explain the purpose of the primary key constraint.", "primary_key_explanation"),
        ]
        for question, expected_intent in cases:
            with self.subTest(question=question):
                result = self.ask(question)
                self.assertTrue(result["success"], result)
                self.assertEqual(result["intent"], expected_intent)
                self.assertTrue(result["answer"])

    def test_highest_salary_synonyms(self) -> None:
        variants = [
            "What is the highest salary?",
            "Find the maximum salary.",
            "Who earns the most?",
            "Show the highest-paid employee.",
            "Which employee receives the largest salary?",
        ]
        for question in variants:
            with self.subTest(question=question):
                self.assertEqual(self.intent_for(question), "company_highest_salary")
                answer = self.ask(question)
                self.assertIn("Robert Scott", answer["answer"])

    def test_accounts_aggregate_synonyms(self) -> None:
        variants = [
            "What is the total salary paid to employees in Accounts?",
            "Find the total salary in Accounts.",
            "Calculate the salary sum of the Accounts department.",
            "How much salary is paid to Accounts employees?",
            "Find the average salary of Accounts employees.",
        ]
        for question in variants:
            with self.subTest(question=question):
                result = self.ask(question)
                self.assertEqual(result["intent"], "department_salary_aggregates")
                self.assertIn("₹16,20,000", result["answer"])

    def test_database_backed_query_results(self) -> None:
        expected = {
            "Which projects involve Scott?": [(501,), (502,), (701,)],
            "Show employees working on IoT with a proposed 10% increase.": [
                ("2001", "Robert Scott", 900000.0, 990000.0),
                ("5001", "Ira Mehta", 750000.0, 825000.0),
                ("5002", "Kabir Rao", 650000.0, 715000.0),
            ],
            "Who works on all department 5 projects?": [("5001", "Ira Mehta")],
            "Who is the oldest cursor employee?": [
                {"E_ID": 95003, "E_NAME": "Sara Fernandes", "AGE": 32, "SALARY": 81000.0}
            ],
        }
        for question, wanted in expected.items():
            with self.subTest(question=question):
                response = self.ask(question)
                if response["intent"] == "projects_scott":
                    self.assertEqual(
                        [(row["PROJECT_NUMBER"],) for row in response["rows"]], wanted
                    )
                elif response["intent"] == "iot_salary_raise":
                    self.assertEqual(
                        [
                            (
                                row["SSN"],
                                row["Name"],
                                row["CURRENT_SALARY"],
                                row["PROPOSED_SALARY"],
                            )
                            for row in response["rows"]
                        ],
                        wanted,
                    )
                elif response["intent"] == "employees_all_d5_projects":
                    self.assertEqual(
                        [(row["SSN"], row["Name"]) for row in response["rows"]], wanted
                    )
                else:
                    self.assertEqual(response["rows"], wanted)

    def test_p2_deleted_employee_is_not_reconstructed(self) -> None:
        response = self.ask("What happened to employee 105?")
        self.assertEqual(response["intent"], "p2_employee_105")
        self.assertEqual(response["rows"], [])
        self.assertEqual(response["result_count"], 0)
        self.assertIn("former details", response["answer"])
        self.assertNotIn("Eshan Paul", response["answer"])

    def test_employee_lookups_use_live_names_and_ids(self) -> None:
        cases = [
            ("Show Practical 2 employee 101.", "p2_employee_by_id", "Arun Sen"),
            ("What is Arun Sen's salary?", "p2_employee_by_id", "Arun Sen"),
            ("Show cursor employee 95001.", "cursor_employee_by_id", "Pooja Kulkarni"),
            ("What is salary of Robert Scott?", "company_employee_by_id", "Robert Scott"),
            ("Show company employee 2001.", "company_employee_by_id", "Robert Scott"),
        ]
        for question, expected_intent, expected_name in cases:
            with self.subTest(question=question):
                result = self.ask(question)
                self.assertEqual(result["intent"], expected_intent)
                self.assertIn(expected_name, result["answer"])

    def test_update_delete_question_and_salary_aggregate(self) -> None:
        operations = self.ask("What is the difference between UPDATE and DELETE?")
        self.assertEqual(operations["intent"], "p2_operations_explanation")
        self.assertIn("renames MGR", operations["answer"])

        aggregates = self.ask("What are the minimum and maximum salaries?")
        self.assertEqual(aggregates["intent"], "company_salary_aggregates")
        self.assertEqual(
            aggregates["rows"][0]["TOTAL_SALARY"],
            5_710_000.0,
        )

    def test_iot_employee_lookup_does_not_imply_a_raise(self) -> None:
        response = self.ask("Find employees working on the IoT project.")
        self.assertEqual(response["intent"], "iot_employees")
        self.assertEqual(response["result_count"], 3)
        self.assertNotIn("PROPOSED_SALARY", response["columns"])

    def test_sql_injection_is_not_executed(self) -> None:
        response = self.ask("Show all employees; DROP TABLE EMPLOYEE;")
        self.assertTrue(response.get("clarification"))
        with sqlite3.connect(DATABASE_PATH) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM EMPLOYEE").fetchone()[0],
                8,
            )

    def test_database_status_and_frontend(self) -> None:
        status = self.client.get("/api/database-status")
        self.assertEqual(status.status_code, 200)
        payload = status.get_json()
        self.assertTrue(payload["connected"])
        self.assertIn("EMPLOYEE", [table["name"] for table in payload["tables"]])

        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Welcome to", page.data)
        self.assertIn(b"Database AI Assistant", page.data)
        self.assertIn(b"chat-form", page.data)

        suggestions = self.client.get("/api/suggestions")
        self.assertEqual(suggestions.status_code, 200)
        self.assertGreaterEqual(len(suggestions.get_json()["groups"]), 5)

    def test_history_can_be_read_and_cleared(self) -> None:
        self.ask("How many cursor employees are there?")
        history = self.client.get("/api/history").get_json()["messages"]
        self.assertEqual(history[-1]["intent"], "cursor_count")
        cleared = self.client.delete("/api/history")
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.get_json()["messages"], [])

    def test_inr_formatting(self) -> None:
        from response_generator import format_inr

        self.assertEqual(format_inr(1620000), "₹16,20,000")
        self.assertEqual(format_inr(7500.5), "₹7,500.50")

    def test_database_connection_is_read_only(self) -> None:
        connection = connect_readonly(DATABASE_PATH)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("DELETE FROM CUSTOMERS")
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
