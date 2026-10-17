"""
Test suite for GitHubWatcher engine.
"""

import unittest
from unittest.mock import MagicMock, patch
from src.github_watcher import GitHubWatcher

class TestGitHubWatcher(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_graph = MagicMock()
        self.mock_db.select_graph.return_value = self.mock_graph

        with patch("src.github_watcher.FalkorDB", return_value=self.mock_db), \
             patch("src.github_watcher.CodebaseTools"):
            self.watcher = GitHubWatcher()
            self.watcher.graph = self.mock_graph

    def test_handle_push_event(self):
        payload = {
            "repository": {"name": "graphops"},
            "sender": {"login": "soyam"},
            "commits": [
                {
                    "id": "e987ab123456",
                    "message": "feat: add real-time webhook watcher",
                    "author": {"name": "Soyam", "email": "soyam@example.com"},
                    "modified": ["src/api.py", "src/github_watcher.py"],
                    "added": []
                }
            ]
        }
        res = self.watcher.handle_push_event(payload)
        self.assertEqual(res["status"], "INGESTED")
        self.assertEqual(res["commits_ingested"], 1)
        self.assertEqual(res["details"][0]["sha"], "e987ab12")

    def test_handle_ci_failure_event(self):
        payload = {
            "failing_function": "verify_token",
            "failing_file": "src/auth.py",
            "error_message": "JWTSignatureError: token signature expired",
            "commit_sha": "a1b2c3d4",
            "pr_number": 88
        }

        with patch.object(self.watcher.tools, "calculate_function_blast_radius") as mock_blast, \
             patch.object(self.watcher.tools, "generate_revert_ticket") as mock_ticket:

            mock_blast.return_value = {
                "target_function": "verify_token",
                "total_impacted_functions": 3,
                "total_affected_files": 2,
                "impacted_functions": [{"function_name": "login_handler"}]
            }
            mock_ticket.return_value = {
                "ticket_id": "CODE-TICKET-VERIFY",
                "broken_function": "verify_token",
                "culprit_author": "Dev Carol",
                "culprit_commit": "a1b2c3d4",
                "recommended_action": "git revert a1b2c3d4"
            }

            res = self.watcher.handle_ci_failure_event(payload)
            self.assertEqual(res["status"], "ANALYZED")
            self.assertIn("git revert a1b2c3d4", res["github_pr_comment"])
            self.assertIn("PR #88", res["github_pr_comment"])

if __name__ == "__main__":
    unittest.main()
