"""
FastAPI Backend for GraphOps.
Exposes endpoints to trigger multi-agent investigation, query graph topology,
and inspect real-time agent audit logs.
"""

import os
from typing import Dict, Any
from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agent_orchestrator import IncidentSwarmOrchestrator
from src.graph_tools import GraphTools
from src.agent_memory import AgentMemoryEngine
from scripts.seed_company_brain import seed_company_brain

app = FastAPI(title="GraphOps: Autonomous Multi-Agent SRE Swarm", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the main GraphOps interactive dashboard."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return "<h1>GraphOps Dashboard Initializing...</h1>"

@app.get("/api/status")
async def get_system_status() -> Dict[str, Any]:
    """Returns FalkorDB connection status, node/edge counts, and active incidents."""
    try:
        tools = GraphTools()
        mem = AgentMemoryEngine()

        # Company Brain metrics
        n_res = tools.graph.query("MATCH (n) RETURN count(n)").result_set
        e_res = tools.graph.query("MATCH ()-[r]->() RETURN count(r)").result_set
        nodes = n_res[0][0] if n_res else 0
        edges = e_res[0][0] if e_res else 0

        # Memory Graph metrics
        ep_res = mem.graph.query("MATCH (ep:Episode) RETURN count(ep)").result_set
        episodes_count = ep_res[0][0] if ep_res else 0

        # Incidents
        inc_res = tools.graph.query("MATCH (i:Incident) RETURN i.id, i.title, i.status, i.severity").result_set
        incidents = [
            {"id": r[0], "title": r[1], "status": r[2], "severity": r[3]}
            for r in inc_res
        ]

        bottlenecks = tools.find_critical_bottlenecks()

        return {
            "status": "ONLINE",
            "falkordb_host": f"{tools.host}:{tools.port}",
            "browser_url": "http://localhost:3000",
            "company_brain_nodes": nodes,
            "company_brain_edges": edges,
            "persisted_episodes": episodes_count,
            "incidents": incidents,
            "top_bottlenecks": bottlenecks[:3]
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

@app.post("/api/reset")
async def reset_graph():
    """Resets and re-seeds the company brain with a fresh ACTIVE incident."""
    seed_company_brain()
    return {"status": "RESET_SUCCESS", "message": "Graph seeded with active SEV-1 incident"}

@app.post("/api/run-swarm")
async def trigger_swarm() -> Dict[str, Any]:
    """Triggers the autonomous multi-agent triage and remediation swarm."""
    orchestrator = IncidentSwarmOrchestrator()
    result = orchestrator.run_investigation_and_mitigation()
    return result

@app.get("/api/episodes")
async def get_episodes(service_id: str = "auth-service"):
    """Recalls past episodes from FalkorDB's agent_memory_swarm."""
    mem = AgentMemoryEngine()
    episodes = mem.recall_episodes_for_service(service_id, limit=10)
    return {"service_id": service_id, "episodes": episodes}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api:app", host="0.0.0.0", port=8000, reload=True)
