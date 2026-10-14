"""
CLI Entrypoint: Runs the Autonomous Multi-Agent Swarm against FalkorDB.
Demonstrates:
- Track 1: Connected Data Blast-Radius & Root-Cause Traversal
- Track 2: Episodic Memory Recall & Multi-Agent Handoff
- Track 3: Team Ownership & Code Traceability
"""

import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.agent_orchestrator import IncidentSwarmOrchestrator
from scripts.seed_company_brain import seed_company_brain

def main():
    print("=" * 70)
    print("    GRAPHOPS: AUTONOMOUS INCIDENT INVESTIGATION & ORG SWARM")
    print("       Powered by FalkorDB GraphBLAS Linear Engine")
    print("=" * 70)

    # Ensure fresh active incident state
    seed_company_brain()

    orchestrator = IncidentSwarmOrchestrator()
    result = orchestrator.run_investigation_and_mitigation()

    print("\n" + "=" * 70)
    print("                    WORKFLOW SUMMARY REPORT")
    print("=" * 70)
    print(f"Session ID:         {result['session_id']}")
    print(f"Incident Handled:   {result['incident_id']}")
    print(f"Final Status:       {result['status']}")
    print(f"Handoff Ticket:     {result['ticket_id']}")
    print(f"Persisted Episode:  {result['episode_id']}")
    print(f"Traceable Steps:    {result['total_audit_steps']}")
    print("\nChronological Audit Chain (Stored in FalkorDB):")
    for s in result["audit_trail"]:
        print(f"  Step {s['step']} [{s['agent']}] ({s['tool_used']}): {s['thought']}")

    print("\n[SUCCESS] The multi-agent swarm resolved the outage and updated FalkorDB!")
    print("          Inspect the mutated graph at: http://localhost:3000")

if __name__ == "__main__":
    main()
