"""
Test suite for CodebaseTools and CodebaseGraphSeeder.
Verifies Cypher queries, blast radius calculation, and Git revert generation.
"""

import unittest
from unittest.mock import MagicMock, patch
from src.code_tools import CodebaseTools
from src.code_graph_seeder import CodebaseGraphSeeder

class TestCodebaseTools(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_graph = MagicMock()
        self.mock_db.select_graph.return_value = self.mock_graph

        with patch("src.code_tools.FalkorDB", return_value=self.mock_db):
            self.tools = CodebaseTools(host="localhost", port=6379, graph_name="test_codebase")

    def test_calculate_function_blast_radius(self):
        # Mock FalkorDB query result for blast radius
        mock_res = MagicMock()
        mock_res.result_set = [
            ["auth.py:verify_token", "verify_token", "src/auth.py", 45, 1],
            ["api.py:login_endpoint", "login_endpoint", "src/api.py", 112, 2],
        ]
        self.mock_graph.query.return_value = mock_res

        result = self.tools.calculate_function_blast_radius("hash_password", max_hops=3)

        self.assertEqual(result["target_function"], "hash_password")
        self.assertEqual(result["total_impacted_functions"], 2)
        self.assertEqual(result["total_affected_files"], 2)
        self.assertIn("src/auth.py", result["affected_files"])
        self.assertIn("src/api.py", result["affected_files"])

    def test_get_function_author_and_commit(self):
        mock_res = MagicMock()
        mock_res.result_set = [
            ["a1b2c3d", "feat: update token verification", "2026-10-15T08:30:00Z", "Soyam", "soyam@example.com", "src/auth.py"]
        ]
        self.mock_graph.query.return_value = mock_res

        result = self.tools.get_function_author_and_commit("verify_token")

        self.assertIsNotNone(result)
        self.assertEqual(result["commit_sha"], "a1b2c3d")
        self.assertEqual(result["author_name"], "Soyam")
        self.assertEqual(result["file"], "src/auth.py")

    def test_generate_revert_ticket(self):
        # Mock blast radius and author methods
        with patch.object(self.tools, "calculate_function_blast_radius") as mock_blast, \
             patch.object(self.tools, "get_function_author_and_commit") as mock_author:

            mock_blast.return_value = {
                "target_function": "process_payment",
                "total_impacted_functions": 3,
                "total_affected_files": 2,
                "affected_files": ["src/checkout.py", "src/billing.py"],
                "impacted_functions": []
            }
            mock_author.return_value = {
                "commit_sha": "f89abc1",
                "commit_message": "refactor: payment gateway api",
                "author_name": "Dev Alice",
                "author_email": "alice@company.com"
            }

            ticket = self.tools.generate_revert_ticket("process_payment", "TypeError: amount cannot be None")

            self.assertTrue(ticket["ticket_id"].startswith("CODE-TICKET-"))
            self.assertEqual(ticket["broken_function"], "process_payment")
            self.assertEqual(ticket["culprit_author"], "Dev Alice")
            self.assertEqual(ticket["culprit_commit"], "f89abc1")
            self.assertEqual(ticket["blast_radius_functions_count"], 3)
            self.assertIn("git revert f89abc1", ticket["recommended_action"])

    def test_find_most_critical_functions(self):
        mock_res = MagicMock()
        mock_res.result_set = [
            ["db.py:get_db_session", "get_db_session", "src/db.py", 8, 1, 9],
            ["logger.py:log_event", "log_event", "src/logger.py", 6, 0, 6]
        ]
        self.mock_graph.query.return_value = mock_res

        critical = self.tools.find_most_critical_functions(limit=5)
        self.assertEqual(len(critical), 2)
        self.assertEqual(critical[0]["name"], "get_db_session")
        self.assertEqual(critical[0]["total_calls"], 9)

if __name__ == "__main__":
    unittest.main()
