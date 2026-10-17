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

    @patch("src.api.AgentMemoryEngine")
    def test_memory_endpoints(self, mock_mem_cls):
        mock_mem = MagicMock()
        mock_mem.get_all_episodes.return_value = [{"episode_id": "EP-01", "service_id": "auth-service"}]
        mock_mem.get_all_handoffs.return_value = [{"ticket_id": "TICKET-01", "status": "COMPLETED"}]
        mock_mem_cls.return_value = mock_mem

        res_ep = self.client.get("/api/memory/episodes")
        self.assertEqual(res_ep.status_code, 200)
        self.assertEqual(res_ep.json()["total_episodes"], 1)

        res_h = self.client.get("/api/memory/handoffs")
        self.assertEqual(res_h.status_code, 200)
        self.assertEqual(res_h.json()["total_handoffs"], 1)

    @patch("src.api.GitHubWatcher")
    def test_github_webhook_and_simulate(self, mock_watcher_cls):
        mock_watcher = MagicMock()
        mock_watcher.handle_push_event.return_value = {"status": "INGESTED", "commits_ingested": 1}
        mock_watcher.handle_ci_failure_event.return_value = {"status": "ANALYZED", "github_pr_comment": "PR review comment"}
        mock_watcher_cls.return_value = mock_watcher

        # Test webhook push
        res_push = self.client.post("/api/github/webhook", json={"commits": []}, headers={"X-GitHub-Event": "push"})
        self.assertEqual(res_push.status_code, 200)
        self.assertEqual(res_push.json()["status"], "INGESTED")

        # Test simulator
        res_sim = self.client.post("/api/github/simulate", json={"event_type": "ci_failure", "failing_function": "foo"})
        self.assertEqual(res_sim.status_code, 200)
        self.assertEqual(res_sim.json()["status"], "ANALYZED")

if __name__ == "__main__":
    unittest.main()
