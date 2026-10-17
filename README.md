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

### 5. Live GitHub Watcher & CI/CD Interceptor (Track 1 & 3)
Incrementally tracks commits and maps CI/CD test failures to upstream function blast radius:
```cypher
// 1. Ingest push webhook: Update commit and author topology
MERGE (eng:Engineer {name: $author_name, email: $author_email})
MERGE (cm:Commit {sha: $sha, message: $message, repo: $repo})
MERGE (cm)-[:AUTHORED_BY]->(eng)
WITH cm
MATCH (f:File {path: $file_path})
MERGE (cm)-[:MODIFIED]->(f)

// 2. CI/CD test failure: Find author and multi-hop upstream blast radius
MATCH (f:Function {name: $failing_func})<-[:DEFINES]-(file:File)<-[:MODIFIED]-(cm:Commit)-[:AUTHORED_BY]->(eng:Engineer)
RETURN f.name, file.path, eng.name, eng.email, cm.sha, cm.message
```

---

## 🔬 How Failure Detection & Blast Radius Work

### 1. How Does GraphOps Know Which Part Failed?
GraphOps operates on two complementary graph planes:
* **Production Alert / Telemetry Plane (`company_brain`)**:
  When monitoring systems (Prometheus, Datadog, Sentry) alert on high latency or error rates (e.g. `504 Gateway Timeout`), an `:Incident` node is created linking `(Incident)-[:AFFECTS]->(Service)`. GraphOps correlates the service to the most recent canary deployment `(Service)<-[:DEPLOYED_TO]-(Commit)`.
* **Codebase & CI/CD Plane (`codebase_graph`)**:
  When a unit test or CI pipeline crashes with a stack trace (e.g. `AttributeError in src/code_tools.py inside calculate_function_blast_radius`), GraphOps parses the file and function symbols. It queries the AST graph:
  ```cypher
  MATCH (f:Function {name: $func_name})<-[:DEFINES]-(file:File {path: $file_path})
  ```
  It then traces backward through `MODIFIED` and `AUTHORED_BY` relationships to identify the exact author and Git SHA that introduced the regression.

### 2. Can It Find the Blast Radius for Future Discrepancies on Past Repositories?
**Yes, instantly.**
* When GraphOps ingests a repository (past or present), it parses the entire Abstract Syntax Tree (AST) to build a static call graph of caller-to-callee dependencies: `(caller:Function)-[:CALLS]->(callee:Function)`.
* Because this dependency graph is stored in FalkorDB's high-performance GraphBLAS sparse matrix engine, any future code modification or failure triggers a reverse reachability query:
  ```cypher
  MATCH path = (upstream:Function)-[:CALLS*1..4]->(target:Function {name: $broken_function})
  RETURN upstream.name, upstream.file, length(path) AS hops
  ```
* Even if the repository was written 5 years ago, GraphOps traverses all upstream entry points, APIs, and business logic that depend on the broken function in single-digit milliseconds.

---

## 🚀 Quickstart & Setup Instructions

### Prerequisites
* Docker & Docker Compose
* Python 3.10+

### 1. Clone & Start FalkorDB
```bash
git clone https://github.com/Soyam-Patra/graphops.git
cd graphops
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
Open **`http://localhost:8080`** in your browser:
* **Microservices & Incident Swarm Tab**: Click **"Run Autonomous Swarm"** to watch the multi-agent reasoning chain resolve outages in real time.
* **Agent Memory & Coordination Tab**: Inspect persistent episodic memory and active multi-agent handoff tickets in `agent_memory_swarm`.
* **Codebase AST & Git Blame Tab**: Click **"Ingest AST"** to parse any repository into FalkorDB, calculate multi-hop function blast radius, and generate 1-click `git revert` remediation tickets.
* **Live GitHub CI/CD Watcher Bot**: 1-click interactive simulation to push commits and simulate CI failure alerts with real-time PR review comments.

---

## 🧪 Verification & Benchmark Results
* **Test Suite**: **23 / 23 unit tests passing** (100% pass rate) across all parser, tool, agent memory, GitHub watcher, and API suites.
* **Traversal Speed**: GraphBLAS sparse-matrix operations executed 4-hop blast radius queries across 500+ AST relationships in **under 4 milliseconds**.
