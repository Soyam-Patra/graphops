# 🌐 GraphOps: Autonomous Multi-Agent SRE Swarm

> **A Graph-Powered Incident Investigation & Organizational Swarm**  
> *Built for "Graph Hacks: Context for AI Agents" (WeMakeDevs × FalkorDB, Oct 2026)*

[![Live Demo](https://img.shields.io/badge/Live_Demo-Render-46E3B7.svg?style=for-the-badge&logo=render&logoColor=black)](https://graphops-29w6.onrender.com/)
[![FalkorDB](https://img.shields.io/badge/Graph_Database-FalkorDB_v1.7-blue.svg?style=for-the-badge)](https://www.falkordb.com/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-Apache_2.0-green.svg?style=for-the-badge)](LICENSE)

> 🚀 **Live Cloud Deployment**: [**https://graphops-29w6.onrender.com/**](https://graphops-29w6.onrender.com/)  
> Explore live dependency blast radius, CI/CD failure localization, and human-approved targeted recovery without any local installation!

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

### 🌐 Live Cloud Deployment (No Setup Needed)
The full GraphOps platform is deployed and running live on Render:
* **Interactive Web App**: [https://graphops-29w6.onrender.com/](https://graphops-29w6.onrender.com/)
* **System Health & Graph Telemetry**: [https://graphops-29w6.onrender.com/api/status](https://graphops-29w6.onrender.com/api/status)

### Local Prerequisites
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
python -m uvicorn src.api:app --host 0.0.0.0 --port 8080 --reload
```
Open **`http://localhost:8080`** in your browser. The application offers two clearly separated primary experiences:

#### 1. Codebases (The Real Product)
* **GitHub Connection**: Connect your GitHub account via PAT or public username (e.g. `@Soyam-Patra`) to list and authorize repositories.
* **Repository Catalog**: View authorized repositories, sync status, and health indicators.
* **Inspect Codebase**:
  * **Overview & Health**: High-level metrics (indexed functions, call dependencies, files, active incidents, and degree centrality bottlenecks).
  * **Dependency Graph**: Interactive Vis.js topology canvas with search jump, node inspection (direct callers vs. transitive callers with hop distances), and blame commit history.
  * **Incidents & CI/CD**: Intercepted build/test failures with failing function, candidate commit attribution, and webhook simulation.
  * **Incident Dossier & Safe Recovery**: Detailed error trace, GraphBLAS multi-hop blast radius, and **"Propose Recovery"** with preview and explicit user approval before executing safe `git revert`.
  * **Activity & Audit**: Real chronological audit trail of repository indexing, CI detections, and recovery actions.

#### 2. Sandbox Lab (Demonstration & Validation Environment)
* **Isolated Environment**: Runs strictly against `sandbox_repo/` without touching production code.
* **5-Step Verifiable Closed Loop**:
  1. **Baseline**: Known-good payment gateway code and 100% passing tests (Exit 0).
  2. **Inject Regression**: Controlled bug committed as `Soyam` &rarr; live test suite fails (Exit 1).
  3. **Diagnose with FalkorDB**: FalkorDB GraphBLAS multi-hop traversal in **3.2ms**, identifying 4 impacted callers and culprit commit.
  4. **Review Recovery**: Previews safe `git revert` command with linear history explanation.
  5. **Revert & Verify**: Genuinely executes `git revert` in the sandbox, re-runs tests live returning to **100% GREEN (Exit 0)**, and writes `:RecoveryAction` audit proof to FalkorDB.

---

## 🧪 Verification & Benchmark Results
* **Test Suite**: **45 / 45 unit tests passing** (100% pass rate in ~11s) across all failure analyzer, targeted recovery engine, parser, tool, agent memory, GitHub watcher, sandbox engine, and API suites.
* **Traversal Speed**: GraphBLAS sparse-matrix operations executed 4-hop blast radius queries across 500+ AST relationships in **under 4 milliseconds**.
