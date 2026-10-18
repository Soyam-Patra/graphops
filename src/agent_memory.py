"""
Agent Memory & Coordination Engine.
Implements:
1. Episodic Memory (Storing & recalling past incident resolution episodes).
2. Multi-Agent Shared Blackboard (State handoffs between Triage and Remediation agents).
3. Persistent Session History (Audit log of agent thoughts and actions).
Directly satisfies Track 2: Agent Memory and Coordination.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from falkordb import FalkorDB

MEMORY_GRAPH = "agent_memory_swarm"

class AgentMemoryEngine:
    def __init__(self, host: str = "localhost", port: int = 6379, memory_graph: str = MEMORY_GRAPH):
        self.host = host
        self.port = port
        self.memory_graph = memory_graph
        self.db = FalkorDB(host=self.host, port=self.port)
        self.graph = self.db.select_graph(self.memory_graph)

    def init_memory_schema(self):
        """
        Initializes schema / indices in the isolated agent memory graph.
        """
        try:
            # Create indices for quick lookups on episodes and tickets
            self.graph.query("CREATE INDEX FOR (e:Episode) ON (e.service_id)")
            self.graph.query("CREATE INDEX FOR (h:HandoffTicket) ON (h.ticket_id)")
        except Exception:
            pass # Index already exists

    def clear_memory(self):
        """Clears the agent memory graph (useful for test resets)."""
        self.graph.query("MATCH (n) DETACH DELETE n")

    # ---------------------------------------------------------
    # 1. EPISODIC MEMORY (Remembering Past Incidents Across Sessions)
    # ---------------------------------------------------------

    def store_episode(
        self,
        incident_id: str,
        service_id: str,
        root_cause_summary: str,
        remediation_action: str,
        success: bool,
        notes: str
    ) -> str:
        """
        Stores an episodic memory node capturing a completed incident investigation.
        """
        episode_id = f"EP-{incident_id}-{int(datetime.now(timezone.utc).timestamp())}"
        now_iso = datetime.now(timezone.utc).isoformat()

        query = """
        CREATE (ep:Episode {
            episode_id: $episode_id,
            incident_id: $incident_id,
            service_id: $service_id,
            root_cause: $root_cause,
            action_taken: $action_taken,
            success: $success,
            notes: $notes,
            created_at: $created_at
        })
        RETURN ep.episode_id AS id
        """
        params = {
            "episode_id": episode_id,
            "incident_id": incident_id,
            "service_id": service_id,
            "root_cause": root_cause_summary,
            "action_taken": remediation_action,
            "success": success,
            "notes": notes,
            "created_at": now_iso
        }
        res = self.graph.query(query, params)
        return res.result_set[0][0]

    def recall_episodes_for_service(self, service_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recalls past episodes for a given service to inform future agent decisions.
        """
        query = """
        MATCH (ep:Episode {service_id: $service_id})
        RETURN ep.episode_id, ep.incident_id, ep.root_cause, ep.action_taken,
               ep.success, ep.notes, ep.created_at
        ORDER BY ep.created_at DESC
        LIMIT $limit
        """
        res = self.graph.query(query, {"service_id": service_id, "limit": limit})
        episodes = []
        for r in res.result_set:
            episodes.append({
                "episode_id": r[0],
                "incident_id": r[1],
                "root_cause": r[2],
                "action_taken": r[3],
                "success": r[4],
                "notes": r[5],
                "created_at": r[6]
            })
        return episodes

    def get_all_episodes(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieves all persistent incident episodes across the entire organization.
        """
        query = """
        MATCH (ep:Episode)
        RETURN ep.episode_id, ep.incident_id, ep.service_id, ep.root_cause,
               ep.action_taken, ep.success, ep.notes, ep.created_at
        ORDER BY ep.created_at DESC
        LIMIT $limit
        """
        res = self.graph.query(query, {"limit": limit})
        episodes = []
        for r in res.result_set:
            episodes.append({
                "episode_id": r[0],
                "incident_id": r[1],
                "service_id": r[2],
                "root_cause": r[3],
                "action_taken": r[4],
                "success": r[5],
                "notes": r[6],
                "created_at": r[7]
            })
        return episodes

    # ---------------------------------------------------------
    # 2. MULTI-AGENT STATE & HANDOFF (Shared Blackboard)
    # ---------------------------------------------------------

    def create_handoff_ticket(
        self,
        from_agent: str,
        to_agent: str,
        incident_id: str,
        service_id: str,
        diagnosis: str,
        recommended_action: str,
        status: str = "PENDING",
        proposed_diff: Optional[str] = None,
        candidate_commit: Optional[str] = None
    ) -> str:
        """
        Triage Agent writes a HandoffTicket to the graph for Remediation Agent to process.
        """
        ticket_id = f"TICKET-{incident_id}-{from_agent[:3].upper()}"
        now_iso = datetime.now(timezone.utc).isoformat()

        query = """
        CREATE (h:HandoffTicket {
            ticket_id: $ticket_id,
            from_agent: $from_agent,
            to_agent: $to_agent,
            incident_id: $incident_id,
            service_id: $service_id,
            diagnosis: $diagnosis,
            recommended_action: $recommended_action,
            status: $status,
            proposed_diff: $proposed_diff,
            candidate_commit: $candidate_commit,
            created_at: $created_at
        })
        RETURN h.ticket_id AS tid
        """
        params = {
            "ticket_id": ticket_id,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "incident_id": incident_id,
            "service_id": service_id,
            "diagnosis": diagnosis,
            "recommended_action": recommended_action,
            "status": status,
            "proposed_diff": proposed_diff or "",
            "candidate_commit": candidate_commit or "",
            "created_at": now_iso
        }
        res = self.graph.query(query, params)
        return res.result_set[0][0]

    def update_handoff_ticket_status(
        self,
        ticket_id: str,
        status: str,
        resolved_by: Optional[str] = None,
        execution_result: Optional[str] = None,
        proposed_diff: Optional[str] = None,
        approved_by: Optional[str] = None,
        exit_code: Optional[int] = None,
        notes: Optional[str] = None
    ) -> bool:
        """
        Updates the ticket through distinct states:
        'AWAITING_APPROVAL', 'APPLYING', 'VERIFYING', 'VERIFIED_SUCCESS', 'VERIFIED_FAILED', 'CANCELLED', 'COMPLETED'.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        query = """
        MATCH (h:HandoffTicket {ticket_id: $ticket_id})
        SET h.status = $status,
            h.updated_at = $updated_at
        """
        params = {
            "ticket_id": ticket_id,
            "status": status,
            "updated_at": now_iso
        }
        if resolved_by is not None:
            query += ", h.resolved_by = $resolved_by"
            params["resolved_by"] = resolved_by
        if execution_result is not None:
            query += ", h.execution_result = $execution_result"
            params["execution_result"] = execution_result
        if proposed_diff is not None:
            query += ", h.proposed_diff = $proposed_diff"
            params["proposed_diff"] = proposed_diff
        if approved_by is not None:
            query += ", h.approved_by = $approved_by, h.approved_at = $updated_at"
            params["approved_by"] = approved_by
        if exit_code is not None:
            query += ", h.verification_exit_code = $exit_code"
            params["exit_code"] = exit_code
        if notes is not None:
            query += ", h.notes = $notes"
            params["notes"] = notes

        query += " RETURN count(h) AS updated"
        res = self.graph.query(query, params)
        return res.result_set[0][0] > 0

    def get_handoff_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a specific handoff ticket by ID."""
        query = """
        MATCH (h:HandoffTicket {ticket_id: $ticket_id})
        RETURN h.ticket_id, h.from_agent, h.to_agent, h.incident_id,
               h.service_id, h.diagnosis, h.recommended_action,
               h.status, h.resolved_by, h.proposed_diff, h.approved_by,
               h.verification_exit_code, h.created_at
        """
        res = self.graph.query(query, {"ticket_id": ticket_id})
        if not res.result_set:
            return None
        r = res.result_set[0]
        return {
            "ticket_id": r[0],
            "from_agent": r[1],
            "to_agent": r[2],
            "incident_id": r[3],
            "service_id": r[4],
            "diagnosis": r[5],
            "recommended_action": r[6],
            "status": r[7],
            "resolved_by": r[8],
            "proposed_diff": r[9],
            "approved_by": r[10],
            "verification_exit_code": r[11],
            "created_at": r[12]
        }

    def get_pending_handoffs(self, agent_role: str) -> List[Dict[str, Any]]:
        """
        Retrieves pending handoffs waiting for an agent with the given role.
        """
        query = """
        MATCH (h:HandoffTicket)
        WHERE h.to_agent = $agent_role AND (h.status = 'PENDING' OR h.status = 'AWAITING_APPROVAL')
        RETURN h.ticket_id, h.from_agent, h.incident_id, h.service_id,
               h.diagnosis, h.recommended_action, h.created_at, h.status
        ORDER BY h.created_at ASC
        """
        res = self.graph.query(query, {"agent_role": agent_role})
        tickets = []
        for r in res.result_set:
            tickets.append({
                "ticket_id": r[0],
                "from_agent": r[1],
                "incident_id": r[2],
                "service_id": r[3],
                "diagnosis": r[4],
                "recommended_action": r[5],
                "created_at": r[6],
                "status": r[7]
            })
        return tickets

    def complete_handoff_ticket(
        self,
        ticket_id: str,
        resolved_by: str,
        execution_result: str
    ) -> bool:
        """
        Remediation Agent marks the handoff ticket as COMPLETED.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        query = """
        MATCH (h:HandoffTicket {ticket_id: $ticket_id})
        SET h.status = 'COMPLETED',
            h.resolved_by = $resolved_by,
            h.execution_result = $execution_result,
            h.resolved_at = $resolved_at
        RETURN count(h) AS updated
        """
        params = {
            "ticket_id": ticket_id,
            "resolved_by": resolved_by,
            "execution_result": execution_result,
            "resolved_at": now_iso
        }
        res = self.graph.query(query, params)
        return res.result_set[0][0] > 0


    def get_all_handoffs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieves all past and active multi-agent handoff tickets from the graph blackboard.
        """
        query = """
        MATCH (h:HandoffTicket)
        RETURN h.ticket_id, h.from_agent, h.to_agent, h.incident_id,
               h.service_id, h.diagnosis, h.recommended_action,
               h.status, h.resolved_by, h.created_at
        ORDER BY h.created_at DESC
        LIMIT $limit
        """
        res = self.graph.query(query, {"limit": limit})
        handoffs = []
        for r in res.result_set:
            handoffs.append({
                "ticket_id": r[0],
                "from_agent": r[1],
                "to_agent": r[2],
                "incident_id": r[3],
                "service_id": r[4],
                "diagnosis": r[5],
                "recommended_action": r[6],
                "status": r[7],
                "resolved_by": r[8] or "Pending",
                "created_at": r[9]
            })
        return handoffs

    # ---------------------------------------------------------
    # 3. TRACEABLE AUDIT TRAIL (Session Action Log)
    # ---------------------------------------------------------

    def log_agent_thought(
        self,
        session_id: str,
        agent_name: str,
        step_number: int,
        thought: str,
        action: str,
        tool_used: Optional[str] = None
    ):
        """
        Logs every step of an agent's reasoning chain into the memory graph
        for full explainability and auditability (Rule #10 & Track 1/2).
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        query = """
        CREATE (s:AgentStep {
            session_id: $session_id,
            agent: $agent_name,
            step_no: $step_no,
            thought: $thought,
            action: $action,
            tool_used: $tool_used,
            timestamp: $timestamp
        })
        """
        self.graph.query(query, {
            "session_id": session_id,
            "agent_name": agent_name,
            "step_no": step_number,
            "thought": thought,
            "action": action,
            "tool_used": tool_used or "N/A",
            "timestamp": now_iso
        })

    def get_session_steps(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieves chronological execution chain for an incident session."""
        query = """
        MATCH (s:AgentStep {session_id: $session_id})
        RETURN s.step_no, s.agent, s.thought, s.action, s.tool_used, s.timestamp
        ORDER BY s.step_no ASC
        """
        res = self.graph.query(query, {"session_id": session_id})
        steps = []
        for r in res.result_set:
            steps.append({
                "step": r[0],
                "agent": r[1],
                "thought": r[2],
                "action": r[3],
                "tool_used": r[4],
                "timestamp": r[5]
            })
        return steps
