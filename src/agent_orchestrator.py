"""
Autonomous Multi-Agent Orchestrator for GraphOps.
Coordinates:
1. TriageAgent: Investigates incidents, queries blast radius, checks past episodic memory.
2. RemediationAgent: Executes runbook mitigation, marks incident resolved, and stores new episode.
Directly unifies Track 1 (Connected Data Actions), Track 2 (Memory & Handoffs), and Track 3 (Company Brain).
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
from src.graph_tools import GraphTools
from src.agent_memory import AgentMemoryEngine

class IncidentSwarmOrchestrator:
    def __init__(self, host: str = "localhost", port: int = 6379):
        self.graph_tools = GraphTools(host=host, port=port, graph_name="company_brain")
        self.memory = AgentMemoryEngine(host=host, port=port, memory_graph="agent_memory_swarm")
        self.session_id = f"SESS-{uuid.uuid4().hex[:8].upper()}"

    def run_investigation_and_mitigation(self) -> Dict[str, Any]:
        """
        Executes the full multi-agent triage and remediation workflow.
        """
        session_id = self.session_id
        trace_log: List[Dict[str, Any]] = []

        # =====================================================================
        # PHASE 1: TRIAGE AGENT - Investigation & Multi-hop Reasoning (Track 1)
        # =====================================================================
        print(f"\n[AGENT: TriageAgent] Initializing investigation session {session_id}...")

        # Step 1: Detect active incidents
        self.memory.log_agent_thought(
            session_id=session_id, agent_name="TriageAgent", step_number=1,
            thought="Checking FalkorDB for active unmitigated incidents.",
            action="Querying active incidents", tool_used="get_active_incidents"
        )
        active_incidents = self.graph_tools.get_active_incidents()
        if not active_incidents:
            return {"status": "NO_ACTIVE_INCIDENTS", "session_id": session_id}

        incident = active_incidents[0]
        inc_id = incident["incident_id"]
        svc_id = incident["service_id"]
        print(f"  [+] Discovered ACTIVE incident {inc_id} affecting service '{svc_id}' (Severity: {incident['severity']})")

        # Step 2: Compute Blast Radius
        self.memory.log_agent_thought(
            session_id=session_id, agent_name="TriageAgent", step_number=2,
            thought=f"Calculating cascading blast radius for affected service '{svc_id}'.",
            action="Traversing reverse call graph", tool_used="calculate_blast_radius"
        )
        blast_radius = self.graph_tools.calculate_blast_radius(svc_id, max_hops=3)
        print(f"  [+] Blast Radius: {blast_radius['total_impacted_services']} upstream callers affected (Tier-0: {blast_radius['critical_tier_0_impacted']})")

        # Step 3: Root-Cause Trace
        self.memory.log_agent_thought(
            session_id=session_id, agent_name="TriageAgent", step_number=3,
            thought="Tracing suspect commits and deployments in FalkorDB.",
            action="Matching incident commit relationships", tool_used="trace_root_cause"
        )
        root_cause = self.graph_tools.trace_root_cause(inc_id)
        suspect_commit = root_cause.get("suspect_commit")
        commit_sha = suspect_commit["sha"] if suspect_commit else "UNKNOWN"
        author = suspect_commit["author"] if suspect_commit else "UNKNOWN"
        print(f"  [+] Root-Cause Identified: Commit {commit_sha} by {author} ('{suspect_commit.get('message', '')}')")

        # Step 4: Recall Episodic Memory (Track 2)
        self.memory.log_agent_thought(
            session_id=session_id, agent_name="TriageAgent", step_number=4,
            thought=f"Recalling past incident episodes for service '{svc_id}'.",
            action="Querying episodic memory", tool_used="recall_episodes_for_service"
        )
        past_episodes = self.memory.recall_episodes_for_service(svc_id, limit=3)
        prior_context = f"Found {len(past_episodes)} prior episode(s)" if past_episodes else "No prior history for this service"
        print(f"  [+] Episodic Memory: {prior_context}")

        # Step 5: Find Ownership & On-call SRE (Track 3)
        self.memory.log_agent_thought(
            session_id=session_id, agent_name="TriageAgent", step_number=5,
            thought="Resolving owning team and on-call escalation contact.",
            action="Traversing team & on-call edges", tool_used="find_service_owners_and_oncall"
        )
        ownership = self.graph_tools.find_service_owners_and_oncall(svc_id)
        oncall_name = ownership["on_call_responder"]["name"] if ownership.get("on_call_responder") else "Unassigned"
        print(f"  [+] Escalation Target: Team '{ownership['owning_team']}' on Slack {ownership['slack_channel']} (On-Call: {oncall_name})")

        # Step 6: Fetch Runbook
        self.memory.log_agent_thought(
            session_id=session_id, agent_name="TriageAgent", step_number=6,
            thought="Fetching recommended procedural runbook.",
            action="Matching runbook node", tool_used="find_matching_runbook"
        )
        runbook = self.graph_tools.find_matching_runbook(inc_id)
        action_name = runbook["automated_action"] if runbook else "MANUAL_INVESTIGATION"
        print(f"  [+] Procedural Runbook: {runbook['runbook_id']} ('{runbook['title']}') -> Action: {action_name}")

        # Step 7: Multi-Agent Handoff Ticket Creation (Track 2)
        diagnosis_summary = (
            f"Commit {commit_sha} deployed by {author} triggered 504 timeouts on {svc_id}. "
            f"Blast radius impacts {blast_radius['total_impacted_services']} services."
        )
        ticket_id = self.memory.create_handoff_ticket(
            from_agent="TriageAgent",
            to_agent="RemediationAgent",
            incident_id=inc_id,
            service_id=svc_id,
            diagnosis=diagnosis_summary,
            recommended_action=action_name
        )
        print(f"  [+] Handed off to RemediationAgent via FalkorDB ticket: {ticket_id}")

        # =====================================================================
        # PHASE 2: REMEDIATION AGENT - Execution & State Mutation (Track 1 & 2)
        # =====================================================================
        print(f"\n[AGENT: RemediationAgent] Picking up pending handoff ticket {ticket_id}...")

        self.memory.log_agent_thought(
            session_id=session_id, agent_name="RemediationAgent", step_number=7,
            thought=f"Claimed ticket {ticket_id}. Preparing to execute automated action '{action_name}'.",
            action=f"Executing {action_name}", tool_used="execute_mitigation"
        )

        # Execute simulated mitigation action
        execution_details = self._execute_remediation(action_name, svc_id, commit_sha)
        print(f"  [+] Mitigation Action Executed: {execution_details}")

        # Complete Handoff Ticket in FalkorDB
        self.memory.complete_handoff_ticket(
            ticket_id=ticket_id,
            resolved_by="RemediationAgent",
            execution_result=execution_details
        )

        # Mutate Incident status in company_brain to 'RESOLVED'
        self._mark_incident_resolved(inc_id, resolution_notes=execution_details)
        print(f"  [+] FalkorDB State Mutated: Incident {inc_id} marked RESOLVED")

        # Step 8: Store New Episodic Memory for Future Sessions (Track 2)
        episode_id = self.memory.store_episode(
            incident_id=inc_id,
            service_id=svc_id,
            root_cause_summary=diagnosis_summary,
            remediation_action=action_name,
            success=True,
            notes=execution_details
        )
        print(f"  [+] Episodic Memory Stored: {episode_id} (Available for all future agent sessions)")

        # Retrieve chronological audit trail
        audit_steps = self.memory.get_session_steps(session_id)

        return {
            "session_id": session_id,
            "incident_id": inc_id,
            "service_id": svc_id,
            "status": "RESOLVED",
            "blast_radius": blast_radius,
            "root_cause": root_cause,
            "ownership": ownership,
            "runbook": runbook,
            "ticket_id": ticket_id,
            "episode_id": episode_id,
            "total_audit_steps": len(audit_steps),
            "audit_trail": audit_steps
        }

    def _execute_remediation(self, action_name: str, service_id: str, commit_sha: str) -> str:
        """Simulates automated infrastructure remediation based on graph runbook."""
        if action_name == "REVERT_CANARY_DEPLOYMENT":
            return f"Drained canary traffic to 0% for '{service_id}'. Reverted deployment from SHA {commit_sha} to baseline."
        elif action_name == "FLUSH_IDLE_POOL_AND_RESTART_REPLICAS":
            return f"Flushed leaked connections on '{service_id}' and restarted stalled worker pods."
        elif action_name == "ENABLE_CIRCUIT_BREAKER_FALLBACK":
            return f"Tripped upstream circuit breaker for '{service_id}'. Enabled cached fallback responses."
        else:
            return f"Standard mitigation applied for '{service_id}'."

    def _mark_incident_resolved(self, incident_id: str, resolution_notes: str):
        """Mutates the incident status in FalkorDB to RESOLVED."""
        now_iso = datetime.now(timezone.utc).isoformat()
        query = """
        MATCH (inc:Incident {id: $incident_id})
        SET inc.status = 'RESOLVED',
            inc.resolvedAt = $resolved_at,
            inc.resolutionNotes = $resolution_notes
        """
        self.graph_tools.graph.query(query, {
            "incident_id": incident_id,
            "resolved_at": now_iso,
            "resolution_notes": resolution_notes
        })
