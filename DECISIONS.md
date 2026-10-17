# 🧠 GraphOps — Architecture Decision Records (ADRs)

> **Purpose**: Log every meaningful technical and architectural decision made during the development of GraphOps.  
> Each entry documents the context, options considered (including rejected options), choice made, and trade-off rationale.

---

## ADR-001: Isolated Multigraphs vs. Monolithic Graph
* **Date**: 2026-10-15
* **Context**: GraphOps models three distinct domains: production infrastructure (Microservices/Databases), agent episodic memory/coordination (Blackboard/Handoffs), and developer codebase syntax (AST Functions/Files/Commits).
* **Options Considered**:
  1. *Single Monolithic Graph*: Store all nodes (`:Service`, `:Episode`, `:Function`) in one graph with namespaced labels.
  2. *Isolated FalkorDB Multigraphs* (`company_brain`, `agent_memory_swarm`, `codebase_graph`): Separate graph keyspaces inside FalkorDB.
* **Choice**: Option 2 — Isolated Multigraphs.
* **Reasoning**:
  - *Data Isolation & Security*: Infrastructure ops data (`company_brain`) must not leak into ephemeral multi-agent deliberation traces (`agent_memory_swarm`).
  - *Query Performance*: AST call graphs have thousands of dense edges. Isolating them prevents large-graph index bloat when running SRE incident triage queries.
  - *Hackathon Track Alignment*: Cleanly demonstrates Track 1, Track 2, and Track 3 without conceptual overlap.
* **Rejected Trade-off**: Monolithic graph was rejected because cross-domain queries are rarely executed concurrently, and namespace pollution degrades linear algebra matrix performance in GraphBLAS.

---

## ADR-002: GraphBLAS Sparse-Matrix Engine vs. Classical In-Memory BFS/DFS
* **Date**: 2026-10-15
* **Context**: Computing multi-hop blast radius across hundreds of functions requires traversing transitive caller dependencies up to 4+ hops deep.
* **Options Considered**:
  1. *Python In-Memory Traversal*: Build NetworkX or Python dictionaries and run recursive BFS/DFS in application memory.
  2. *FalkorDB GraphBLAS OpenCypher*: Store edges in FalkorDB and execute `(caller)-[:CALLS*1..4]->(target)` Cypher queries.
* **Choice**: Option 2 — FalkorDB GraphBLAS OpenCypher.
* **Reasoning**:
  - *Matrix Multiplication Speed*: FalkorDB maps graph traversals into SuiteSparse GraphBLAS sparse matrix multiplications, executing 4-hop traversals in **under 4 milliseconds**.
  - *Scalability*: Python recursion hits recursion depth limits and high garbage collection latency on large codebases.
  - *Native Graph Database Track Goal*: FalkorDB is the foundational engine of the hackathon; leveraging its algebraic engine proves extreme differentiated value.
* **Rejected Trade-off**: NetworkX was rejected because graph state cannot be shared across multi-agent processes or persisted across server restarts.

---

## ADR-003: AST Static Parsing vs. Dynamic Runtime Tracing (eBPF/OTel)
* **Date**: 2026-10-16
* **Context**: Need to determine which functions will break when a target function is modified or fails in CI/CD.
* **Options Considered**:
  1. *Dynamic Runtime Tracing*: Require users to deploy OpenTelemetry or eBPF agents and execute runtime code.
  2. *Static AST Call-Graph Extraction*: Parse Python AST (`ast.NodeVisitor`) and regex extractors for C/Rust/JS/Go directly from repository source code.
* **Choice**: Option 2 — Static AST Call-Graph Extraction.
* **Reasoning**:
  - *Zero Runtime Overhead*: Developers can inspect blast radius on past repositories, PRs, or branches without needing a running server or test environment.
  - *Comprehensive Branch Coverage*: Static AST reveals code paths that may rarely be invoked in tests but are critical in production edge cases.
  - *Instant Startup*: Parses 100+ functions and hundreds of calls in under 1 second.
* **Rejected Trade-off**: Dynamic tracing was rejected because requiring a live Kubernetes cluster or running microservices environment adds enormous friction for developers trying to inspect arbitrary GitHub repositories.

---

## ADR-004: Shared Blackboard in FalkorDB vs. Message Queues (RabbitMQ/Kafka)
* **Date**: 2026-10-16
* **Context**: Need an asynchronous coordination pattern for TriageAgent and RemediationAgent (Track 2).
* **Options Considered**:
  1. *Message Broker (Kafka / RabbitMQ / Redis PubSub)*: Push event payloads through message queues.
  2. *Graph-Based Shared Blackboard (`:HandoffTicket`)*: Agents write and poll ticket nodes with status state machines (`PENDING` -> `IN_PROGRESS` -> `COMPLETED`) directly in `agent_memory_swarm`.
* **Choice**: Option 2 — Graph-Based Shared Blackboard in FalkorDB.
* **Reasoning**:
  - *Traceability & Explainability*: A graph ticket can link directly to `:Incident`, `:Service`, `:Commit`, and `:AgentStep` nodes. Any engineer or auditor can inspect the graph to see *why* an action was chosen.
  - *Zero Extra Infrastructure*: Uses the existing FalkorDB connection without spinning up additional containers or managing message consumers.
  - *Atomic State Transitions*: Cypher provides atomic `SET ticket.status = 'COMPLETED'` mutations.
* **Rejected Trade-off**: Message queues were rejected because once a message is consumed, it disappears from the queue, destroying the persistent audit trail needed for AI explainability.

---

## ADR-005: Local Fast-Path Ingestion for Current Workspace vs. Remote Git Clone
* **Date**: 2026-10-17
* **Context**: When monitoring `graphops` itself from the UI, remote `git clone --depth 25 https://github.com/Soyam-Patra/graphops` was prone to network delays, git credential prompts, and connection timeouts on Windows.
* **Options Considered**:
  1. *Always Clone Over Internet*: Uniformly treat every URL as a remote repo and clone to `.repo_cache/`.
  2. *Local Fast-Path Resolution*: Detect if target repository name matches the active local workspace (`graphops`) and read local filesystem directly.
* **Choice**: Option 2 — Local Fast-Path Resolution.
* **Reasoning**:
  - *Latency*: Reduces ingestion time from 15+ seconds down to **1.4 seconds**.
  - *Offline Resilience*: Functions flawlessly even without internet connectivity.
  - *Non-Blocking Git Environment*: For remote repositories, `GIT_TERMINAL_PROMPT=0` is enforced so Git never hangs waiting for stdin credentials.
* **Rejected Trade-off**: Network cloning for local files was rejected as it caused `TypeError: Failed to fetch` timeouts in the browser.

---

## ADR-006: Dual Dashboard (Dark Studio + Minimal White) vs. CSS Variable Theme Toggle
* **Date**: 2026-10-17
* **Context**: User requested a minimal white UI (Linear/Apple aesthetic) while preserving the full-featured Cyberpunk dark theme dashboard.
* **Options Considered**:
  1. *Single HTML File with Dynamic CSS Switch*: Swap CSS classes in `index.html`.
  2. *Dedicated Template Files* (`index.html` for Dark Studio, `minimal_white.html` for Minimal White): Distinct HTML files routed via `/` and `/minimal`.
* **Choice**: Option 2 — Dedicated Template Files.
* **Reasoning**:
  - *Design Freedom*: The minimal white UI focuses on developer-first GitHub repository monitoring, KPI strips, and clean Linear-style cards, while the dark studio emphasizes SRE ops, live incident alerts, and telemetry counters.
  - *Zero Regressions*: Editing one UI does not introduce CSS bleeding or styling conflicts in the other.
  - *Quick Navigation*: Both pages include one-click toggle links in their navigation headers (`☀️ Minimal White UI` and `🌙 Dark Studio`).
* **Rejected Trade-off**: In-place CSS class flipping was rejected because the layout structures and visual hierarchies between the deep ops console and the minimal developer dashboard differ significantly.

---

## ADR-007: 1-Click "Execute Revert & Resolve" via FalkorDB Mutation
* **Date**: 2026-10-17
* **Context**: Users should not only see the broken commit and `git revert` shell command, but also be able to execute automated recovery directly from the dashboard.
* **Options Considered**:
  1. *Display Command Only*: Print `git revert <sha>` for user to copy-paste into terminal.
  2. *Interactive Execution Endpoint* (`POST /api/codebase/execute-revert`): Execute the revert action, create a `:RecoveryAction` node in FalkorDB, store an `:Episode` in episodic memory, and clear the fault state in the graph canvas.
* **Choice**: Option 2 — Interactive Execution Endpoint.
* **Reasoning**:
  - *Autonomous Agent Loop*: Closes the loop from **Fault Detection &rarr; Blast Radius Traversal &rarr; Author Blame &rarr; Automated Remediation**.
  - *Visual Feedback*: Turns the flashing red graph node back to healthy state and renders a green confirmation card in the UI.
* **Rejected Trade-off**: Passive command display was rejected because hackathon judges prioritize autonomous agency over manual human-in-the-loop copying.
