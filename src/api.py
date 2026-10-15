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
from src.code_parser import CodebaseParser
from src.code_graph_seeder import CodebaseGraphSeeder
from src.code_tools import CodebaseTools

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
async def reset_graph(scenario: str = "bad_deployment"):
    """Resets and re-seeds the company brain with a chosen incident scenario."""
    seed_company_brain(scenario=scenario)
    return {"status": "RESET_SUCCESS", "scenario": scenario, "message": f"Graph seeded with scenario '{scenario}'"}

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

@app.get("/api/memory/episodes")
async def get_all_memory_episodes():
    """Returns all persisted episodes across all services from agent_memory_swarm."""
    mem = AgentMemoryEngine()
    episodes = mem.get_all_episodes(limit=25)
    return {"total_episodes": len(episodes), "episodes": episodes}

@app.get("/api/memory/handoffs")
async def get_all_memory_handoffs():
    """Returns all multi-agent handoff tickets from agent_memory_swarm."""
    mem = AgentMemoryEngine()
    handoffs = mem.get_all_handoffs(limit=25)
    return {"total_handoffs": len(handoffs), "handoffs": handoffs}

@app.get("/api/graph-data")
async def get_graph_data() -> Dict[str, Any]:
    """
    Returns nodes and relationships from company_brain formatted for Vis.js canvas.
    """
    tools = GraphTools()
    node_query = "MATCH (n) RETURN id(n), labels(n), properties(n)"
    edge_query = "MATCH (a)-[r]->(b) RETURN id(a), id(b), type(r), properties(r)"

    n_res = tools.graph.query(node_query).result_set
    e_res = tools.graph.query(edge_query).result_set

    # Color palette for node categories
    color_map = {
        "Service": {"background": "#0284c7", "border": "#38bdf8", "highlight": "#0ea5e9"},      # Cyan
        "Database": {"background": "#7c3aed", "border": "#a855f7", "highlight": "#9333ea"},     # Purple
        "Team": {"background": "#d97706", "border": "#fbbf24", "highlight": "#f59e0b"},         # Amber
        "Engineer": {"background": "#059669", "border": "#34d399", "highlight": "#10b981"},     # Green
        "Incident": {"background": "#dc2626", "border": "#f87171", "highlight": "#ef4444"},     # Red
        "Commit": {"background": "#ea580c", "border": "#fb923c", "highlight": "#f97316"},       # Orange
        "Runbook": {"background": "#2563eb", "border": "#60a5fa", "highlight": "#3b82f6"}       # Blue
    }

    nodes = []
    for r in n_res:
        nid = r[0]
        label = r[1][0] if r[1] else "Entity"
        props = dict(r[2]) if r[2] else {}

        # Display name
        display_name = props.get("name") or props.get("id") or props.get("title") or props.get("sha") or f"Node-{nid}"
        if label == "Commit" and "sha" in props:
            display_name = f"Commit {props['sha'][:7]}"
        elif label == "Incident":
            display_name = f"{props.get('id', 'INC')} ({props.get('status', 'ACTIVE')})"

        # Check if incident is resolved to color it green
        node_colors = color_map.get(label, {"background": "#475569", "border": "#94a3b8", "highlight": "#64748b"})
        if label == "Incident" and props.get("status") == "RESOLVED":
            node_colors = {"background": "#059669", "border": "#34d399", "highlight": "#10b981"}

        tooltip_lines = [f"<b>Type:</b> {label}"]
        for k, v in props.items():
            tooltip_lines.append(f"<b>{k}:</b> {v}")
        tooltip = "<br>".join(tooltip_lines)

        nodes.append({
            "id": nid,
            "label": display_name,
            "group": label,
            "title": tooltip,
            "color": node_colors,
            "shape": "dot" if label != "Service" else "diamond",
            "size": 24 if label in ["Service", "Incident"] else 16,
            "font": {"color": "#ffffff", "face": "JetBrains Mono, monospace", "size": 11}
        })

    edges = []
    for r in e_res:
        from_id = r[0]
        to_id = r[1]
        rel_type = r[2]
        props = dict(r[3]) if r[3] else {}

        edge_color = "#334155" # Default slate
        if rel_type == "CALLS":
            edge_color = "#0ea5e9"
        elif rel_type == "DEPENDS_ON":
            edge_color = "#a855f7"
        elif rel_type == "AFFECTS":
            edge_color = "#f43f5e"
        elif rel_type == "TRIGGERED_BY":
            edge_color = "#fb923c"

        edges.append({
            "from": from_id,
            "to": to_id,
            "label": rel_type,
            "color": {"color": edge_color, "highlight": "#38bdf8"},
            "arrows": "to",
            "font": {"color": "#94a3b8", "size": 9, "align": "middle", "face": "JetBrains Mono, monospace"},
            "smooth": {"type": "curvedCW", "roundness": 0.15}
        })

    return {"nodes": nodes, "edges": edges}

class ChatRequest(BaseModel):
    question: str

@app.post("/api/chat")
async def chat_with_company_brain(req: ChatRequest) -> Dict[str, Any]:
    """
    Translates Natural Language questions about the company architecture,
    on-call rosters, bottlenecks, and services into Cypher queries on FalkorDB.
    """
    tools = GraphTools()
    q = req.question.strip().lower()

    # Raw Cypher execution if query starts with MATCH, RETURN, etc.
    if q.startswith("match") or q.startswith("return"):
        try:
            cypher = req.question.strip()
            res = tools.graph.query(cypher)
            columns = [c for c in res.result_set[0]] if res.result_set else []
            return {
                "question": req.question,
                "cypher": cypher,
                "answer": f"Executed custom Cypher query returning {len(res.result_set)} record(s).",
                "records": [list(r) for r in res.result_set]
            }
        except Exception as e:
            return {"question": req.question, "error": f"Cypher error: {str(e)}"}

    # Intent routing for Natural Language questions
    if any(k in q for k in ["on call", "oncall", "who is on call", "responder"]):
        cypher = """
        MATCH (e:Engineer)-[:ON_CALL_FOR]->(t:Team)
        RETURN e.name AS engineer, e.email AS email, e.role AS role, t.name AS team, t.slack AS slack
        """
        res = tools.graph.query(cypher)
        records = [list(r) for r in res.result_set]
        roster_str = ", ".join([f"**{r[0]}** ({r[2]}) for *{r[3]}* on `{r[4]}`" for r in records])
        answer = f"Currently active on-call engineers:\n{roster_str}"

    elif any(k in q for k in ["bottleneck", "single point", "failure", "centrality"]):
        cypher = """
        MATCH (s:Service)
        OPTIONAL MATCH (s)<-[i:CALLS]-(u:Service)
        OPTIONAL MATCH (s)-[o:CALLS]->(d:Service)
        WITH s, count(DISTINCT u) AS in_deg, count(DISTINCT d) AS out_deg
        RETURN s.name AS service, s.tier AS tier, in_deg, out_deg, (in_deg + out_deg) AS total_connections
        ORDER BY total_connections DESC
        """
        res = tools.graph.query(cypher)
        records = [list(r) for r in res.result_set]
        top = records[0]
        answer = f"The primary architectural choke point is **{top[0]}** ({top[1]}) with **{top[4]} total connections** (calls {top[3]} services, called by {top[2]})."

    elif any(k in q for k in ["database", "db", "storage", "postgres", "cockroach", "redis"]):
        cypher = """
        MATCH (s:Service)-[r:DEPENDS_ON]->(db:Database)
        RETURN s.name AS service, db.name AS database, db.engine AS engine, r.mode AS access_mode
        """
        res = tools.graph.query(cypher)
        records = [list(r) for r in res.result_set]
        items = "\n".join([f"• `{r[0]}` depends on **{r[1]}** ({r[2]}) in `{r[3]}` mode" for r in records])
        answer = f"Company Datastore Dependencies:\n{items}"

    elif any(k in q for k in ["team", "teams", "owner", "owns", "ownership"]):
        cypher = """
        MATCH (t:Team)-[:OWNS]->(s:Service)
        RETURN t.name AS team, t.slack AS slack, collect(s.name) AS owned_services
        """
        res = tools.graph.query(cypher)
        records = [list(r) for r in res.result_set]
        items = "\n".join([f"• **{r[0]}** (`{r[1]}`): {', '.join(r[2])}" for r in records])
        answer = f"Engineering Team Ownership:\n{items}"

    elif any(k in q for k in ["commit", "commits", "pr", "pull request", "git", "author"]):
        cypher = """
        MATCH (c:Commit)-[:AUTHORED_BY]->(e:Engineer)
        MATCH (c)-[:DEPLOYED_TO]->(s:Service)
        RETURN c.sha AS sha, c.message AS message, e.name AS author, s.name AS service
        """
        res = tools.graph.query(cypher)
        records = [list(r) for r in res.result_set]
        items = "\n".join([f"• Commit `{r[0]}` by **{r[2]}** deployed to *{r[3]}*: \"{r[1]}\"" for r in records])
        answer = f"Recent Git Deployments:\n{items}"

    elif any(k in q for k in ["runbook", "runbooks", "sop", "procedure", "mitigation"]):
        cypher = """
        MATCH (r:Runbook)
        RETURN r.id AS id, r.title AS title, r.automatedAction AS action, r.steps AS steps
        """
        res = tools.graph.query(cypher)
        records = [list(r) for r in res.result_set]
        items = "\n".join([f"• **{r[0]}**: {r[1]} (Action: `{r[2]}`)" for r in records])
        answer = f"Available Operational Runbooks:\n{items}"

    else:
        # Default query: general service topology
        cypher = """
        MATCH (s:Service)-[r:CALLS]->(target:Service)
        RETURN s.name AS caller, target.name AS callee, r.protocol AS protocol, r.avgRps AS rps
        """
        res = tools.graph.query(cypher)
        records = [list(r) for r in res.result_set]
        answer = f"Here is the active service call-chain topology with {len(records)} active API dependencies."

    return {
        "question": req.question,
        "cypher": cypher.strip(),
        "answer": answer,
        "records": records
    }

# =========================================================================
# Codebase Intelligence & AST Call-Graph Endpoints
# =========================================================================

class CodebaseScanRequest(BaseModel):
    repo_path: str = "."

class BlastRadiusRequest(BaseModel):
    function_name: str
    max_hops: int = 4

class RevertTicketRequest(BaseModel):
    function_name: str
    error_symptom: str = "Regression or incident detected in downstream service"

@app.post("/api/codebase/scan")
async def scan_and_ingest_codebase(req: CodebaseScanRequest) -> Dict[str, Any]:
    """
    Parses any target Git repository's AST functions, calls, and commits,
    and seeds them into the FalkorDB 'codebase_graph' multigraph.
    """
    try:
        parser = CodebaseParser(req.repo_path)
        data = parser.parse_repository()
        seeder = CodebaseGraphSeeder()
        stats = seeder.ingest_codebase(data)
        return {
            "status": "SUCCESS",
            "repository": data["repository"],
            "repo_path": data["repo_path"],
            "metrics": stats,
            "parsed_summary": {
                "files": len(data["files"]),
                "functions": len(data["functions"]),
                "calls": len(data["calls"]),
                "commits": len(data["commits"])
            }
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

@app.get("/api/codebase/graph")
async def get_codebase_graph_data() -> Dict[str, Any]:
    """
    Extracts nodes and relationships from FalkorDB's 'codebase_graph'
    formatted for the interactive Vis.js canvas.
    """
    try:
        tools = CodebaseTools()
        node_query = "MATCH (n) RETURN id(n), labels(n), properties(n)"
        edge_query = "MATCH (a)-[r]->(b) RETURN id(a), id(b), type(r), properties(r)"

        n_res = tools.graph.query(node_query).result_set
        e_res = tools.graph.query(edge_query).result_set

        color_map = {
            "Function": {"background": "#8b5cf6", "border": "#a78bfa", "highlight": "#c084fc"},
            "File": {"background": "#0284c7", "border": "#38bdf8", "highlight": "#0ea5e9"},
            "Commit": {"background": "#ea580c", "border": "#fb923c", "highlight": "#f97316"},
            "Engineer": {"background": "#059669", "border": "#34d399", "highlight": "#10b981"},
            "Repository": {"background": "#db2777", "border": "#f472b6", "highlight": "#f43f5e"}
        }

        nodes = []
        for r in n_res:
            nid = r[0]
            label = r[1][0] if r[1] else "Entity"
            props = dict(r[2]) if r[2] else {}

            display_name = props.get("name") or props.get("id") or props.get("sha") or f"Node-{nid}"
            if label == "Commit" and "sha" in props:
                display_name = f"git {props['sha'][:7]}"

            tooltip_lines = [f"<b>Type:</b> {label}"]
            for k, v in props.items():
                tooltip_lines.append(f"<b>{k}:</b> {v}")
            tooltip = "<br>".join(tooltip_lines)

            nodes.append({
                "id": nid,
                "label": display_name,
                "group": label,
                "title": tooltip,
                "color": color_map.get(label, {"background": "#475569", "border": "#94a3b8", "highlight": "#64748b"}),
                "shape": "diamond" if label == "Repository" else ("box" if label == "File" else "dot"),
                "size": 22 if label in ["Repository", "Function"] else 15,
                "font": {"color": "#ffffff", "face": "JetBrains Mono, monospace", "size": 11}
            })

        edges = []
        for r in e_res:
            from_id = r[0]
            to_id = r[1]
            rel_type = r[2]

            edge_color = "#334155"
            if rel_type == "CALLS":
                edge_color = "#a855f7"
            elif rel_type == "DEFINES":
                edge_color = "#38bdf8"
            elif rel_type == "CONTAINS":
                edge_color = "#64748b"
            elif rel_type == "MODIFIED":
                edge_color = "#fb923c"
            elif rel_type == "AUTHORED_BY":
                edge_color = "#34d399"

            edges.append({
                "from": from_id,
                "to": to_id,
                "label": rel_type,
                "color": {"color": edge_color, "highlight": "#c084fc"},
                "arrows": "to",
                "font": {"color": "#94a3b8", "size": 9, "align": "middle", "face": "JetBrains Mono, monospace"}
            })

        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

@app.post("/api/codebase/blast-radius")
async def analyze_function_blast_radius(req: BlastRadiusRequest) -> Dict[str, Any]:
    """Calculates multi-hop blast radius for a given function."""
    try:
        tools = CodebaseTools()
        return tools.calculate_function_blast_radius(req.function_name, req.max_hops)
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/codebase/revert-ticket")
async def generate_code_revert_ticket(req: RevertTicketRequest) -> Dict[str, Any]:
    """Automates Git author attribution and revert ticket creation."""
    try:
        tools = CodebaseTools()
        return tools.generate_revert_ticket(req.function_name, req.error_symptom)
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/codebase/critical")
async def get_critical_functions() -> Dict[str, Any]:
    """Returns functions with highest call centrality in the codebase."""
    try:
        tools = CodebaseTools()
        funcs = tools.find_most_critical_functions(limit=10)
        return {"critical_functions": funcs}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api:app", host="0.0.0.0", port=8000, reload=True)
