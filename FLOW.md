# 🌊 GraphOps — End-to-End Execution Flows & Traceability

> **Purpose**: Trace how execution travels across files, functions, and database calls.  
> Answers: *Where does execution start? What calls what? In what order? Where can it fail?*

---

## 🗺️ Flow 1: Repository Ingestion & AST Seeding

```
[User clicks "⚡ Monitor" or calls POST /api/github/monitor-repo]
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│ 1. src/api.py :: monitor_selected_repo()               │
│    • Receives: { repo_url, repo_name }                 │
│    • Checks: Fast-path local workspace vs. remote      │
└────────────────────────┬───────────────────────────────┘
                         │ Calls
                         ▼
┌────────────────────────────────────────────────────────┐
│ 2. src/code_parser.py :: CodebaseParser(repo_path)     │
│    • __init__(): Resolves path (or clones shallow git) │
│    • parse_repository(): Walks files ignoring cache    │
│      ├── _parse_python_file(): Uses ast.NodeVisitor    │
│      │   └── Extracts: FunctionDefs, Call visitors     │
│      ├── _parse_generic_code_file(): Regex for C/JS/Go │
│      └── _extract_git_history(): Runs git log & blame  │
└────────────────────────┬───────────────────────────────┘
                         │ Returns parsed data dict
                         ▼
┌────────────────────────────────────────────────────────┐
│ 3. src/code_graph_seeder.py :: ingest_codebase(data)   │
│    • Driver connects to FalkorDB keyspace:             │
│      `codebase_graph`                                  │
│    • Cypher queries:                                   │
│      ├── MERGE (f:File {path})                         │
│      ├── MERGE (fn:Function {name, file})              │
│      ├── MERGE (file)-[:DEFINES]->(fn)                 │
│      ├── MERGE (caller)-[:CALLS]->(callee)             │
│      ├── MERGE (eng:Engineer {name, email})            │
│      ├── MERGE (cm:Commit {sha, msg})-[:AUTHORED_BY]   │
│      └── MERGE (cm)-[:MODIFIED]->(file)                │
└────────────────────────┬───────────────────────────────┘
                         │ Returns graph stats
                         ▼
[Frontend UI renders Vis.js Network Topology Canvas & Switches to Tab 2]
```

### Potential Failure Choke Points in Flow 1:
1. **Network Timeout during `git clone`**:
   - *Failure*: Remote server slow or unreachable.
   - *Mitigation*: Timeout capped at 45s, `GIT_TERMINAL_PROMPT=0` prevents hanging. Fast-path used for `graphops`.
2. **Invalid Python Syntax in target repository**:
   - *Failure*: `ast.parse` throws `SyntaxError`.
   - *Mitigation*: Wrapped in `try...except Exception: return None` in `_parse_python_file`. Bad files skipped gracefully without aborting whole repo.

---

## 💥 Flow 2: CI/CD Failure Interception & Blast Radius

```
[CI/CD Workflow Fails / User clicks "🚨 Simulate CI/CD Failure"]
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│ 1. src/api.py :: receive_github_webhook() / simulate   │
│    • Intercepts workflow_run or check_run failure      │
│    • Extracts: failing_function, failing_file, trace   │
└────────────────────────┬───────────────────────────────┘
                         │ Calls
                         ▼
┌────────────────────────────────────────────────────────┐
│ 2. src/github_watcher.py :: handle_ci_failure_event()  │
│    • Calls CodebaseTools to calculate blast radius     │
│    • Calls CodebaseTools to generate revert ticket     │
└────────────────────────┬───────────────────────────────┘
                         │ Calls
                         ▼
┌────────────────────────────────────────────────────────┐
│ 3. src/code_tools.py :: calculate_function_blast_radius│
│    • Connects to FalkorDB `codebase_graph`             │
│    • Cypher GraphBLAS reverse reachability:            │
│      MATCH path = (upstream:Function)-[:CALLS*1..4]    │
│                    ->(target:Function {name: $func})   │
│      RETURN upstream.name, upstream.file, min(hops)    │
└────────────────────────┬───────────────────────────────┘
                         │ Returns { impacted_functions, affected_files }
                         ▼
┌────────────────────────────────────────────────────────┐
│ 4. src/code_tools.py :: generate_revert_ticket()       │
│    • Queries FalkorDB for Git Author Blame:            │
│      MATCH (f:Function {name: $func})<-[:DEFINES]-     │
│            (file)<-[:MODIFIED]-(cm)-[:AUTHORED_BY]     │
│            ->(eng:Engineer)                            │
│      RETURN cm.sha, eng.name, eng.email, cm.message    │
│    • Constructs structured ticket & shell revert cmd   │
└────────────────────────┬───────────────────────────────┘
                         │ Returns { ticket_id, culprit_commit, action }
                         ▼
┌────────────────────────────────────────────────────────┐
│ 5. src/github_watcher.py :: generate_pr_review_comment │
│    • Formats GitHub Flavored Markdown PR comment       │
│    • Includes: Component, Root Cause, Blast Radius,    │
│      Culprit author, and 1-Click `git revert` command  │
└────────────────────────┬───────────────────────────────┘
                         │ Returns JSON payload
                         ▼
[Frontend UI renders Linear-style KPI cards, caller chains, and highlights RED on Vis.js]
```

### Potential Failure Choke Points in Flow 2:
1. **Target function not found in AST**:
   - *Failure*: Function name misspelled or dynamically generated at runtime.
   - *Mitigation*: Fallback matching by suffix (`ends-with`) or returning 0 impacted callers safely with clear diagnostic message.
2. **Commit history detached or missing author**:
   - *Failure*: Shallow clone without Git history.
   - *Mitigation*: `generate_revert_ticket()` defaults `culprit_author` to "Unknown" and provides manual hotfix instruction.

---

## ⚡ Flow 3: 1-Click Automated Revert & Incident Recovery

```
[User clicks "⚡ Execute 1-Click Git Revert & Mark Resolved" in UI]
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│ 1. src/api.py :: execute_code_revert()                 │
│    • Receives: { commit_sha, function_name, ticket_id }│
└────────────────────────┬───────────────────────────────┘
                         │ Calls FalkorDB
                         ▼
┌────────────────────────────────────────────────────────┐
│ 2. FalkorDB `codebase_graph` Mutation                  │
│    • Cypher:                                           │
│      MERGE (c:Commit {sha: $sha})                      │
│      CREATE (r:RecoveryAction {                        │
│          action_id: $action_id,                        │
│          action_type: 'GIT_REVERT',                    │
│          status: 'EXECUTED'                            │
│      })                                                │
│      CREATE (c)-[:REVERTED_BY]->(r)                    │
└────────────────────────┬───────────────────────────────┘
                         │ Calls
                         ▼
┌────────────────────────────────────────────────────────┐
│ 3. src/agent_memory.py :: store_episode()              │
│    • Writes to FalkorDB `agent_memory_swarm`:          │
│      CREATE (:Episode {                                │
│          incident_id: $incident_id,                    │
│          root_cause: "Regression in commit $sha",      │
│          action_taken: "git revert $sha",              │
│          success: true                                 │
│      })                                                │
└────────────────────────┬───────────────────────────────┘
                         │ Returns { status: SUCCESS, action_id }
                         ▼
[Frontend: Resets graph colors, clears red fault pulse, renders green resolution card]
```

---

## 🤖 Flow 4: Autonomous SRE Multi-Agent Swarm (Track 1, 2, 3)

```
[Incident Alert INC-2026-881 Triggered / User clicks "Run Swarm"]
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│ 1. src/agent_orchestrator.py :: run_autonomous_swarm() │
│    • Instantiates TriageAgent & RemediationAgent       │
└────────────────────────┬───────────────────────────────┘
                         │ Step 1
                         ▼
┌────────────────────────────────────────────────────────┐
│ 2. TriageAgent Execution (`company_brain`)             │
│    • get_active_incidents() -> INC-2026-881 (HTTP 504) │
│    • calculate_blast_radius(checkout-api) -> 2 callers │
│    • trace_root_cause() -> Commit 4a1c78e (Carol Zhang)│
│    • find_service_owners_and_oncall() -> Identity Team │
│    • recall_similar_episodes() -> Found past TTL bug   │
│    • post_handoff_ticket() -> Writes to Shared         │
│      Blackboard in `agent_memory_swarm` (PENDING)      │
└────────────────────────┬───────────────────────────────┘
                         │ Step 2 (Agent Handoff)
                         ▼
┌────────────────────────────────────────────────────────┐
│ 3. RemediationAgent Execution (`agent_memory_swarm`)   │
│    • poll_pending_handoff_ticket() -> Claims ticket    │
│    • Updates status: PENDING -> IN_PROGRESS            │
│    • find_matching_runbook() -> RB-002 (ROLLBACK)      │
│    • execute_automated_remediation() -> Simulates      │
│      canary rollback to commit 7b2a19c                 │
│    • update_incident_status() -> Sets INC to RESOLVED  │
│    • complete_handoff_ticket() -> Sets status COMPLETED│
│    • store_episode() -> Persists new Episode in graph  │
└────────────────────────┬───────────────────────────────┘
                         │ Returns complete audit trajectory
                         ▼
[Frontend renders real-time audit feed and increments Persisted Episodes counter]
```
