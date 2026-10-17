"""
Unit tests for Sandbox Closed-Loop Recovery Engine and API endpoints.
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from src.api import app
from src.sandbox_engine import SandboxEngine

class TestSandbox(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch.object(SandboxEngine, "init_sandbox")
    def test_sandbox_init_endpoint(self, mock_init):
        mock_init.return_value = {
            "status": "INITIALIZED_CLEAN",
            "baseline_tests_passed": True,
            "exit_code": 0
        }
        res = self.client.post("/api/sandbox/init")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "INITIALIZED_CLEAN")
        self.assertTrue(res.json()["baseline_tests_passed"])

    @patch.object(SandboxEngine, "inject_regression")
    def test_sandbox_inject_endpoint(self, mock_inject):
        mock_inject.return_value = {
            "status": "REGRESSION_ACTIVE",
            "failing_function": "charge_card",
            "exit_code": 1,
            "test_passed": False
        }
        res = self.client.post("/api/sandbox/inject")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "REGRESSION_ACTIVE")
        self.assertEqual(res.json()["exit_code"], 1)

    @patch.object(SandboxEngine, "diagnose_regression")
    def test_sandbox_diagnose_endpoint(self, mock_diag):
        mock_diag.return_value = {
            "status": "DIAGNOSED",
            "target_function": "charge_card",
            "blast_radius": {"total_impacted_functions": 2}
        }
        res = self.client.post("/api/sandbox/diagnose")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "DIAGNOSED")

    @patch.object(SandboxEngine, "execute_revert_and_verify")
    def test_sandbox_revert_verify_endpoint(self, mock_revert):
        mock_revert.return_value = {
            "status": "VERIFIED_PASSING",
            "commit_reverted": "a1b2c3d",
            "test_passed": True,
            "exit_code": 0,
            "falkordb_proof_recorded": True
        }
        res = self.client.post("/api/sandbox/revert-and-verify")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "VERIFIED_PASSING")
        self.assertTrue(res.json()["test_passed"])
        self.assertEqual(res.json()["exit_code"], 0)

if __name__ == "__main__":
    unittest.main()
