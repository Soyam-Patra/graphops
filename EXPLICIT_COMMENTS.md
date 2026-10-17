# 💬 GraphOps — Explicit Comments & Code Invariants Guide

> **Rule for AI & Engineers**: Do not restate what the code syntax does.  
> Document **intent**, **assumptions**, **architectural invariants**, and **WHY notes** (explaining surprising or non-obvious code so future sessions do not accidentally "clean it up").

---

## 📌 Standard Invariant & Comment Patterns

### 1. The "WHY" Note (Surprising Code Protection)
Used whenever an implementation deviates from the intuitive or standard path to solve an edge case.
```python
# WHY: On Windows systems, invoking `git clone` or `git pull` on remote repositories
# may launch the Windows OpenSSH or Git Credential Manager GUI dialog if credentials
# are missing or invalid. This blocks the Python subprocess indefinitely without throwing
# an exception, causing the frontend fetch call to hang and time out.
# Passing GIT_TERMINAL_PROMPT="0" forces Git to fail immediately with an exit code != 0,
# allowing Python to catch the failure and return a structured JSON error to the user.
git_env = os.environ.copy()
git_env["GIT_TERMINAL_PROMPT"] = "0"
```

### 2. The Architectural Invariant
Used when order of execution is mathematically or structurally critical.
```python
# INVARIANT [CRITICAL]: Must query isolated multigraph 'agent_memory_swarm', NEVER 'company_brain'.
# Episodic memories and multi-agent deliberation traces must never collide with production
# service infrastructure nodes.
self.graph = self.driver.select_graph("agent_memory_swarm")
```

### 3. Property Resolution Invariant (Cypher in FalkorDB)
```python
# INVARIANT: Do NOT split relationship traversal into disconnected MATCH clauses.
# In OpenCypher on GraphBLAS, matching `(f:Function)` and separately matching `(file:File {path: f.file})`
# without an edge requires a cross-product Cartesian join over sparse matrices.
# Always traverse via the explicit structural relationship:
# `MATCH (f:Function)<-[:DEFINES]-(file:File)<-[:MODIFIED]-(cm:Commit)-[:AUTHORED_BY]->(eng:Engineer)`
```

---

## 🔍 Module-by-Module Intent & Assumptions

### 1. `src/code_parser.py` (AST & Git Blame Parser)
- **Primary Function**: `parse_repository()`
  - **What calls into it**: `src/api.py` (`POST /api/codebase/scan`, `POST /api/github/monitor-repo`).
  - **Assumptions**:
    - The repository filesystem is readable by the operating system user.
    - Python files are valid UTF-8 (falls back to `errors="ignore"` for mixed encodings).
    - Remote URLs start with `http://`, `https://`, or `git@`.
  - **WHY Note**:
    - *Ignore Directory Set*: `.repo_cache` **must** be included in `ignore_dirs`. If omitted, when parsing `.` (the root project directory), `os.walk` will descend into previously cloned repositories inside `.repo_cache/`, causing runaway recursive loops and duplicate node explosions.
    - *Local Fast-Path*: If repository name is `graphops` and `src/` exists locally, bypass network git clone completely. Reading local disk takes 1.4s vs 20s over internet.

### 2. `src/code_tools.py` (GraphBLAS Blast Radius Engine)
- **Primary Function**: `calculate_function_blast_radius(function_name, max_hops=4)`
  - **What calls into it**: `src/api.py`, `src/github_watcher.py` (on CI failure).
  - **Assumptions**:
    - FalkorDB contains a populated `codebase_graph` populated with `(:Function)` and `[:CALLS]` edges.
  - **Invariant**:
    - Traversal direction is **strictly reverse**: `(caller:Function)-[:CALLS*1..$max_hops]->(target:Function)`. Target is the callee; we seek all upstream callers whose execution depends on target.
  - **WHY Note**:
    - We use Cypher aggregation `WITH caller, min(length(path)) AS hops` rather than returning all raw paths to prevent duplicate entries when multiple call paths converge on the same caller.

### 3. `src/agent_memory.py` (Track 2 Episodic Memory Vault)
- **Primary Function**: `store_episode()`, `recall_similar_episodes()`, `post_handoff_ticket()`
  - **What calls into it**: `IncidentSwarmOrchestrator` (`src/agent_orchestrator.py`), `TriageAgent`, `RemediationAgent`.
  - **Assumptions**:
    - Every incident has a unique alphanumeric ID (e.g. `INC-2026-881`).
  - **Invariant**:
    - Handoff tickets must transition strictly: `PENDING` &rarr; `IN_PROGRESS` &rarr; `COMPLETED`.
    - Once marked `COMPLETED`, the ticket is retained in the graph for auditability but filtered out of the active blackboard queue.

### 4. `src/github_watcher.py` (Live Webhook & CI/CD Review Bot)
- **Primary Function**: `handle_push_event()`, `handle_ci_failure_event()`
  - **What calls into it**: `POST /api/github/webhook` (real GitHub), `POST /api/github/simulate` (dashboard).
  - **Assumptions**:
    - Git commits include a SHA, author name, and list of modified file paths.
  - **WHY Note**:
    - We use `MERGE (cm:Commit {sha: $sha})` instead of `CREATE` so duplicate webhook delivery or retries by GitHub do not duplicate commit nodes or corrupt relationship degree centrality.

### 5. `src/api.py` (FastAPI Layer & 1-Click Revert)
- **Primary Function**: `POST /api/codebase/execute-revert`
  - **What calls into it**: Dashboard button "⚡ Execute 1-Click Git Revert & Mark Resolved".
  - **Assumptions**:
    - The commit SHA exists in `codebase_graph`.
  - **Invariant**:
    - Creates a `:RecoveryAction` node and mutates the incident state in FalkorDB before returning HTTP 200. This guarantees atomic consistency between UI and database.
