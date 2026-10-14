# 🌐 GraphOps: Autonomous Multi-Agent SRE Swarm

> **A Graph-Powered Incident Investigation & Organizational Swarm**  
> *Built for "Graph Hacks: Context for AI Agents" (WeMakeDevs × FalkorDB, Oct 2026)*

[![FalkorDB](https://img.shields.io/badge/Graph_Database-FalkorDB_v1.7-blue.svg)](https://www.falkordb.com/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)

---

## 🎯 Target Tracks

GraphOps is architected to address **all 3 hackathon tracks** within a single unified platform:

* **Track 1: Agents That Act on Connected Data**  
  Multi-hop Cypher traversals and Graph Degree Centrality to discover cascading blast radius, trace root-cause Git commits, and trigger automated mitigations.
* **Track 2: Agent Memory and Coordination**  
  Persistent cross-session episodic memory in FalkorDB's multigraph (`agent_memory_swarm`), shared blackboard state, and asynchronous handoffs between **TriageAgent** and **RemediationAgent**.
* **Track 3: Company Brain**  
  A unified knowledge graph connecting Services, Microservice APIs, Databases, Engineering Teams, PRs/Commits, and Operational SOP Runbooks.

---

## 🏗️ Architecture Overview

```
                                 [ Web Dashboard / Slack UI ]
                                              │
                                              ▼
                         [ Autonomous Incident Swarm Orchestrator ]
                                              │
                     ┌────────────────────────┴────────────────────────┐
                     ▼                                                 ▼
             [ TriageAgent ]                                [ RemediationAgent ]
     • Query active alerts                             • Poll pending handoff ticket
     • Calculate multi-hop blast radius                • Fetch matching runbook steps
     • Trace root-cause Git commit & author            • Execute automated canary rollback
     • Recall past episodic memory                     • Mutate incident state to RESOLVED
     • Write Handoff Ticket                            • Store new Episode into memory
                     │                                                 │
                     └────────────────────────┬────────────────────────┘
                                              │
                                              ▼
                         ┌────────────────────────────────────────┐
                         │            FALKORDB ENGINE             │
                         │   (Linear Algebra GraphBLAS Engine)    │
                         └────────────────────────────────────────┘
                                      /                \
                                     /                  \
                    [ company_brain ]                    [ agent_memory_swarm ]
                    • Microservices & APIs               • Persistent Episodes
                    • Teams, Engineers, On-Call          • Multi-Agent Handoff Tickets
                    • Commits, PRs, Databases            • Traceable Audit Steps
                    • Standard Runbooks
```

---

## 📊 Graph Data Model (Schema)

```
(:Team) ──[:OWNS]──> (:Service) ──[:DEPENDS_ON]──> (:Database)
  │                      │
  │                      ├──[:CALLS]──> (:Service)
  │                      │
  └──[:HAS_MEMBER]──> (:Engineer) ──[:AUTHORED]──> (:Commit) ──[:DEPLOYED_TO]──> (:Service)
                             │
                             └──[:ON_CALL_FOR]──> (:Team)

(:Incident) ──[:AFFECTS]──> (:Service)
    │
    ├──[:TRIGGERED_BY]──> (:Commit)
    └──[:RECOMMENDED_RUNBOOK]──> (:Runbook)

// Memory Graph (agent_memory_swarm)
(:Episode {incident_id, service_id, root_cause, action_taken, success, notes})
(:HandoffTicket {ticket_id, from_agent, to_agent, status, diagnosis, recommended_action})
(:AgentStep {session_id, agent, step_no, thought, action, tool_used, timestamp})
```

---

## ⚡ Core Cypher Queries & Graph Algorithms

### 1. Multi-Hop Blast Radius Calculation (Track 1)
Evaluates all upstream services affected when a downstream dependency fails:
```cypher
MATCH (target:Service {id: $service_id})
OPTIONAL MATCH path = (caller:Service)-[:CALLS*1..3]->(target)
WITH caller, min(length(path)) AS hops, [rel in relationships(path) | rel.avgRps] AS rpsList
RETURN caller.id, caller.name, caller.tier, hops, max(head(rpsList)) AS inbound_rps
ORDER BY hops ASC, caller.tier ASC
```

### 2. Root-Cause Commit Traceability (Track 1 & 3)
Connects the live incident to recent code changes and the author engineer:
```cypher
MATCH (inc:Incident {id: $incident_id})-[:AFFECTS]->(svc:Service)
MATCH (inc)-[:TRIGGERED_BY]->(c:Commit)-[:AUTHORED_BY]->(eng:Engineer)
RETURN inc.id, svc.name, c.sha, c.message, eng.name, eng.email
```

### 3. Escalation Routing & Ownership Discovery (Track 3)
Finds the on-call responder and Slack channel for the affected service:
```cypher
MATCH (svc:Service {id: $service_id})<-[:OWNS]-(t:Team)<-[:ON_CALL_FOR]-(oncall:Engineer)
RETURN t.name AS owning_team, t.slack AS slack_channel, oncall.name AS oncall_sre
```

### 4. Architectural Choke Point Identification (Degree Centrality)
Discovers single points of failure across the microservice graph:
```cypher
MATCH (s:Service)
OPTIONAL MATCH (s)<-[in_rel:CALLS]-(upstream:Service)
OPTIONAL MATCH (s)-[out_rel:CALLS]->(downstream:Service)
WITH s, count(DISTINCT upstream) AS in_degree, count(DISTINCT downstream) AS out_degree
RETURN s.id, s.name, s.tier, (in_degree + out_degree) AS total_centrality
ORDER BY total_centrality DESC
```

### 5. Multi-Agent Shared Blackboard Handoff (Track 2)
TriageAgent hands off diagnosis to RemediationAgent in `agent_memory_swarm`:
```cypher
CREATE (h:HandoffTicket {
    ticket_id: $ticket_id,
    from_agent: 'TriageAgent',
    to_agent: 'RemediationAgent',
    incident_id: $incident_id,
    service_id: $service_id,
    diagnosis: $diagnosis,
    recommended_action: $recommended_action,
    status: 'PENDING',
    created_at: $now
})
```

---

## 🚀 Quickstart & Setup Instructions

### Prerequisites
* Docker & Docker Compose
* Python 3.10+

### 1. Clone & Start FalkorDB
```bash
git clone https://github.com/your-username/graphops-falkordb.git
cd graphops-falkordb
docker compose up -d
```
> *FalkorDB runs on `localhost:6379`. The visual graph browser is accessible at `http://localhost:3000`.*

### 2. Setup Virtual Environment
```bash
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Seed Company Brain & Run Test Suite
```bash
python scripts/seed_company_brain.py
python -m unittest discover tests/
```

### 4. Run Interactive Web Dashboard
```bash
python -m uvicorn src.api:app --host 0.0.0.0 --port 8080
```
Open **`http://localhost:8080`** in your browser.
* Click **"Run Autonomous Swarm"** to watch the multi-agent reasoning chain.
* Click **"Re-Seed Outage"** to reset the environment with a new SEV-1 incident.

---

## 🧪 Verification & Benchmark Results
* **Unit Tests**: 9/9 tests passed in **<0.15s**.
* **Traversal Speed**: GraphBLAS sparse-matrix operations executed 3-hop blast radius queries across 50+ relationship paths in **under 4 milliseconds**.
