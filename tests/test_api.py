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

    def test_serve_minimal_dashboard(self):
        res = self.client.get("/minimal")
        self.assertEqual(res.status_code, 200)
        res_light = self.client.get("/light")
        self.assertEqual(res_light.status_code, 200)

    @patch("src.api.requests.get")
    def test_github_auth_and_session(self, mock_get):
        # Mock user profile response
        mock_user_resp = MagicMock()
        mock_user_resp.status_code = 200
        mock_user_resp.json.return_value = {
            "login": "Soyam-Patra",
            "name": "Soyam Patra",
            "avatar_url": "https://avatars.githubusercontent.com/u/123",
            "html_url": "https://github.com/Soyam-Patra",
            "public_repos": 12,
            "bio": "Building autonomous systems"
        }

        # Mock user repos response
        mock_repos_resp = MagicMock()
        mock_repos_resp.status_code = 200
        mock_repos_resp.json.return_value = [
            {
                "id": 999,
                "name": "graphops",
                "full_name": "Soyam-Patra/graphops",
                "html_url": "https://github.com/Soyam-Patra/graphops",
                "clone_url": "https://github.com/Soyam-Patra/graphops.git",
                "description": "GraphOps Autonomous SRE Swarm",
                "language": "Python",
                "stargazers_count": 5,
                "forks_count": 1,
                "updated_at": "2026-10-17T12:00:00Z",
                "default_branch": "main"
            }
        ]

        mock_get.side_effect = [mock_user_resp, mock_repos_resp]

        # 1. Connect
        connect_res = self.client.post("/api/github/connect", json={"username": "Soyam-Patra"})
        self.assertEqual(connect_res.status_code, 200)
        data = connect_res.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["user"]["login"], "Soyam-Patra")
        self.assertEqual(len(data["repos"]), 1)

        # 2. Check Session
        session_res = self.client.get("/api/github/session")
        self.assertEqual(session_res.status_code, 200)
        self.assertTrue(session_res.json()["authenticated"])
        self.assertEqual(session_res.json()["user"]["login"], "Soyam-Patra")

        # 3. Disconnect
        disc_res = self.client.post("/api/github/disconnect")
        self.assertEqual(disc_res.status_code, 200)
        self.assertFalse(disc_res.json()["authenticated"])

    @patch("src.api.CodebaseParser")
    @patch("src.api.CodebaseGraphSeeder")
    def test_github_monitor_repo_endpoint(self, mock_seeder_cls, mock_parser_cls):
        mock_parser = MagicMock()
        mock_parser.parse_repository.return_value = {
            "repository": "graphops",
            "repo_path": "/tmp/graphops",
            "files": [{"path": "src/api.py"}],
            "functions": [{"id": "func1", "name": "serve_dashboard"}],
            "calls": [],
            "commits": []
        }
        mock_parser_cls.return_value = mock_parser

        mock_seeder = MagicMock()
        mock_seeder.ingest_codebase.return_value = {
            "total_nodes": 10,
            "total_relationships": 12
        }
        mock_seeder_cls.return_value = mock_seeder

        res = self.client.post("/api/github/monitor-repo", json={
            "repo_url": "https://github.com/Soyam-Patra/graphops",
            "repo_name": "graphops"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["monitored_repo"]["name"], "graphops")
        self.assertEqual(data["monitored_repo"]["functions_count"], 1)

    @patch("src.api.CodebaseTools")
    @patch("src.api.AgentMemoryEngine")
    def test_execute_revert_endpoint(self, mock_mem_cls, mock_tools_cls):
        mock_tools = MagicMock()
        mock_tools_cls.return_value = mock_tools
        mock_mem = MagicMock()
        mock_mem_cls.return_value = mock_mem

        res = self.client.post("/api/codebase/execute-revert", json={
            "commit_sha": "86e6fd7",
            "function_name": "calculate_function_blast_radius",
            "ticket_id": "TICKET-123"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["commit_reverted"], "86e6fd7")
        self.assertTrue(data["falkordb_mutated"])

    @patch("src.api.CodebaseTools")
    def test_codebase_overview_endpoint(self, mock_tools_cls):
        mock_tools = MagicMock()
        mock_tools.find_most_critical_functions.return_value = [{"function_name": "calc", "in_degree": 3}]
        mock_tools.graph.query.side_effect = [
            MagicMock(result_set=[[10]]),  # functions
            MagicMock(result_set=[[5]]),   # files
            MagicMock(result_set=[[25]]),  # calls
            MagicMock(result_set=[[4]]),   # commits
            MagicMock(result_set=[["a1b2c3d", "test commit", "2026-10-17"]]), # latest commit
            MagicMock(result_set=[[1]])    # active incidents
        ]
        mock_tools_cls.return_value = mock_tools

        res = self.client.get("/api/codebase/overview")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ONLINE")
        self.assertEqual(data["indexed_revision"], "a1b2c3d")
        self.assertEqual(data["metrics"]["total_functions"], 10)

    @patch("src.api.CodebaseTools")
    def test_codebase_incidents_endpoint(self, mock_tools_cls):
        mock_tools = MagicMock()
        mock_tools.graph.query.return_value = MagicMock(result_set=[
            ["INC-101", "charge_card", "pay.py", "TypeError", "c123456", 12, "ACTIVE", "HIGH", "2026-10-18T10:00:00Z", 3]
        ])
        mock_tools_cls.return_value = mock_tools

        res = self.client.get("/api/codebase/incidents")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(len(data["incidents"]), 1)
        self.assertEqual(data["incidents"][0]["failing_function"], "charge_card")

    @patch("src.api.CodebaseTools")
    @patch("src.api.AgentMemoryEngine")
    def test_codebase_audit_endpoint(self, mock_mem_cls, mock_tools_cls):
        mock_tools = MagicMock()
        mock_tools.graph.query.return_value = MagicMock(result_set=[
            ["REV-001", "GIT_REVERT", "sha123", "charge_card", "EXECUTED", 0, True, "2026-10-18T10:05:00Z"]
        ])
        mock_tools_cls.return_value = mock_tools
        mock_mem = MagicMock()
        mock_mem.get_all_episodes.return_value = [{"episode_id": "EP-01", "root_cause": "Bug"}]
        mock_mem_cls.return_value = mock_mem

        res = self.client.get("/api/codebase/audit")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(len(data["recovery_actions"]), 1)
        self.assertEqual(data["recovery_actions"][0]["action_id"], "REV-001")

if __name__ == "__main__":
    unittest.main()
