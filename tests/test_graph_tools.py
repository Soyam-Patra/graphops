"""
Test suite verifying FalkorDB GraphTools layer.
"""

import unittest
from src.graph_tools import GraphTools
from scripts.seed_company_brain import seed_company_brain

class TestGraphTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_company_brain(scenario="bad_deployment")
        cls.tools = GraphTools()

    def test_get_active_incidents(self):
        incidents = self.tools.get_active_incidents()
        self.assertGreater(len(incidents), 0)
        self.assertEqual(incidents[0]["incident_id"], "INC-2026-881")
        print(f"[OK] test_get_active_incidents: found {len(incidents)} active incident(s)")

    def test_trace_root_cause(self):
        result = self.tools.trace_root_cause("INC-2026-881")
        self.assertIn("suspect_commit", result)
        self.assertIsNotNone(result["suspect_commit"])
        self.assertEqual(result["suspect_commit"]["sha"], "4a1c78e")
        self.assertEqual(result["suspect_commit"]["author"], "Carol Zhang")
        print(f"[OK] test_trace_root_cause: resolved author Carol Zhang, commit 4a1c78e")

    def test_calculate_blast_radius(self):
        radius = self.tools.calculate_blast_radius("auth-service", max_hops=3)
        self.assertGreaterEqual(radius["total_impacted_services"], 2)
        caller_ids = [s["service_id"] for s in radius["impacted_services"]]
        self.assertIn("checkout-api", caller_ids)
        self.assertIn("api-gateway", caller_ids)
        print(f"[OK] test_calculate_blast_radius: identified {radius['total_impacted_services']} callers in blast radius")

    def test_find_service_owners_and_oncall(self):
        ownership = self.tools.find_service_owners_and_oncall("auth-service")
        self.assertEqual(ownership["owning_team"], "Identity & Sec")
        self.assertEqual(ownership["slack_channel"], "#eng-auth")
        self.assertIsNotNone(ownership["on_call_responder"])
        self.assertEqual(ownership["on_call_responder"]["name"], "Carol Zhang")
        print(f"[OK] test_find_service_owners_and_oncall: team '{ownership['owning_team']}', on-call '{ownership['on_call_responder']['name']}'")

    def test_find_matching_runbook(self):
        runbook = self.tools.find_matching_runbook("INC-2026-881")
        self.assertIsNotNone(runbook)
        self.assertEqual(runbook["runbook_id"], "RB-002")
        self.assertEqual(runbook["automated_action"], "REVERT_CANARY_DEPLOYMENT")
        print(f"[OK] test_find_matching_runbook: mapped to {runbook['runbook_id']} ('{runbook['automated_action']}')")

    def test_find_critical_bottlenecks(self):
        bottlenecks = self.tools.find_critical_bottlenecks()
        self.assertGreater(len(bottlenecks), 0)
        # Check top bottleneck
        top = bottlenecks[0]
        print(f"[OK] test_find_critical_bottlenecks: top choke point '{top['name']}' with centrality {top['total_centrality']}")

if __name__ == "__main__":
    unittest.main()
