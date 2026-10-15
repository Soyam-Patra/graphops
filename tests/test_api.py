"""
Unit tests for FastAPI endpoints in src/api.py.
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.api import app

class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_serve_dashboard(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    @patch("src.api.CodebaseParser")
    @patch("src.api.CodebaseGraphSeeder")
    def test_codebase_scan_endpoint(self, mock_seeder_cls, mock_parser_cls):
        mock_parser = MagicMock()
        mock_parser.parse_repository.return_value = {
            "repository": "test-repo",
            "repo_path": "/path/to/test",
            "files": [{"path": "a.py"}],
            "functions": [{"id": "a.py:foo", "name": "foo"}],
            "calls": [],
            "commits": []
        }
        mock_parser_cls.return_value = mock_parser

        mock_seeder = MagicMock()
        mock_seeder.ingest_codebase.return_value = {
            "total_nodes": 5,
            "total_relationships": 4
        }
        mock_seeder_cls.return_value = mock_seeder

        res = self.client.post("/api/codebase/scan", json={"repo_path": "."})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["repository"], "test-repo")
        self.assertEqual(data["parsed_summary"]["functions"], 1)

    @patch("src.api.CodebaseTools")
    def test_codebase_blast_radius_endpoint(self, mock_tools_cls):
        mock_tools = MagicMock()
        mock_tools.calculate_function_blast_radius.return_value = {
            "target_function": "verify_auth",
            "total_impacted_functions": 4,
            "total_affected_files": 2,
            "affected_files": ["auth.py", "api.py"],
            "impacted_functions": []
        }
        mock_tools_cls.return_value = mock_tools

        res = self.client.post("/api/codebase/blast-radius", json={"function_name": "verify_auth", "max_hops": 3})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_impacted_functions"], 4)

    @patch("src.api.CodebaseTools")
    def test_codebase_revert_ticket_endpoint(self, mock_tools_cls):
        mock_tools = MagicMock()
        mock_tools.generate_revert_ticket.return_value = {
            "ticket_id": "CODE-TICKET-VERIFY",
            "broken_function": "verify_auth",
            "culprit_author": "Soyam",
            "culprit_commit": "e8912ba",
            "recommended_action": "git revert e8912ba"
        }
        mock_tools_cls.return_value = mock_tools

        res = self.client.post("/api/codebase/revert-ticket", json={"function_name": "verify_auth", "error_symptom": "NullPointer"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["culprit_commit"], "e8912ba")
        self.assertIn("git revert", data["recommended_action"])

if __name__ == "__main__":
    unittest.main()
