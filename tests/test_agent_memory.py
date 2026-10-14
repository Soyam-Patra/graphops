"""
Test suite verifying FalkorDB Agent Memory & Coordination Engine.
"""

import unittest
from src.agent_memory import AgentMemoryEngine

class TestAgentMemoryEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mem = AgentMemoryEngine()
        cls.mem.clear_memory()
        cls.mem.init_memory_schema()

    def test_store_and_recall_episode(self):
        # Store an episode
        ep_id = self.mem.store_episode(
            incident_id="INC-2026-881",
            service_id="auth-service",
            root_cause_summary="JWKS cache TTL bug caused high Redis connection churn",
            remediation_action="REVERT_CANARY_DEPLOYMENT",
            success=True,
            notes="Rolled back commit 4a1c78e; latency recovered to 78ms"
        )
        self.assertTrue(ep_id.startswith("EP-INC-2026-881"))
        print(f"[OK] Stored episodic memory: {ep_id}")

        # Recall episode
        recalled = self.mem.recall_episodes_for_service("auth-service")
        self.assertGreater(len(recalled), 0)
        self.assertEqual(recalled[0]["incident_id"], "INC-2026-881")
        self.assertEqual(recalled[0]["action_taken"], "REVERT_CANARY_DEPLOYMENT")
        print(f"[OK] Recalled episode across sessions: {recalled[0]['root_cause'][:40]}...")

    def test_multi_agent_handoff(self):
        # 1. Triage Agent creates ticket for Remediation Agent
        ticket_id = self.mem.create_handoff_ticket(
            from_agent="TriageAgent",
            to_agent="RemediationAgent",
            incident_id="INC-2026-881",
            service_id="auth-service",
            diagnosis="Identified bad commit 4a1c78e causing cascading 504 gateway timeout",
            recommended_action="Execute RB-002: Revert Canary Deployment"
        )
        self.assertTrue(ticket_id.startswith("TICKET-INC-2026-881"))
        print(f"[OK] Created multi-agent handoff ticket: {ticket_id}")

        # 2. Remediation Agent polls pending handoffs
        pending = self.mem.get_pending_handoffs("RemediationAgent")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["ticket_id"], ticket_id)
        print(f"[OK] Remediation Agent retrieved handoff ticket: {pending[0]['diagnosis'][:40]}...")

        # 3. Remediation Agent completes ticket
        completed = self.mem.complete_handoff_ticket(
            ticket_id=ticket_id,
            resolved_by="RemediationAgent",
            execution_result="SUCCESS: Canary traffic set to 0%; commit reverted"
        )
        self.assertTrue(completed)

        # 4. Confirm no more pending tickets
        after_pending = self.mem.get_pending_handoffs("RemediationAgent")
        self.assertEqual(len(after_pending), 0)
        print(f"[OK] Handoff ticket marked COMPLETED and blackboard cleared")

    def test_log_and_audit_session_steps(self):
        session_id = "SESSION-TEST-001"
        self.mem.log_agent_thought(
            session_id=session_id,
            agent_name="TriageAgent",
            step_number=1,
            thought="Detected SEV-1 incident INC-2026-881 affecting auth-service",
            action="Querying blast radius",
            tool_used="calculate_blast_radius"
        )
        self.mem.log_agent_thought(
            session_id=session_id,
            agent_name="TriageAgent",
            step_number=2,
            thought="Blast radius includes API Gateway and Checkout API",
            action="Handing off to RemediationAgent",
            tool_used="create_handoff_ticket"
        )

        steps = self.mem.get_session_steps(session_id)
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]["step"], 1)
        self.assertEqual(steps[1]["agent"], "TriageAgent")
        print(f"[OK] Verified traceable audit log: {len(steps)} steps retrieved in chronological order")

if __name__ == "__main__":
    unittest.main()
