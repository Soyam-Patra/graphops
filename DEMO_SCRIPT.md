# 🎬 3-Minute Demo Video Script: GraphOps

> **Goal**: A crisp, professional 3-minute screen recording showcasing GraphOps solving an incident using FalkorDB.  
> **Target Tracks**: Track 1, Track 2, and Track 3.

---

## ⏱️ Video Breakdown

### 0:00 – 0:35 | The Problem & The Solution (35s)
* **Screen**: Web Dashboard at `http://localhost:8080`.
* **Narration**:
  > *"When a production incident occurs, traditional AI agents struggle because they see isolated logs and disjointed vector embeddings. They can't trace how microservices connect, who pushed the breaking commit, or how the outage was resolved last month.*  
  > *Welcome to **GraphOps**, an autonomous multi-agent incident intelligence swarm powered by **FalkorDB**'s GraphBLAS linear algebra engine.*  
  > *GraphOps addresses all three hackathon tracks: Track 1 by acting directly on connected graph data, Track 2 through persistent cross-session episodic memory and multi-agent handoffs, and Track 3 by turning the entire company topology into an interconnected graph."*

---

### 0:35 – 1:30 | Exploring the Company Brain & The Incident (55s)
* **Screen**: Switch tab to **FalkorDB Browser** (`http://localhost:3000`), run query:  
  `MATCH (s:Service)-[r]->(d) RETURN s, r, d LIMIT 25`
* **Narration**:
  > *"In FalkorDB, we've modeled the entire Company Brain: microservices, teams, Git commits, on-call engineers, and runbooks.*  
  > *Right now, we have an active SEV-1 incident: `INC-2026-881` where the API Gateway is reporting a 504 gateway timeout.*  
  > *Notice that if you take FalkorDB away, the system cannot function—because the decision loop relies on multi-hop traversals across these connected relationships."*

---

### 1:30 – 2:30 | The Autonomous Multi-Agent Swarm in Action (60s)
* **Screen**: Switch back to Dashboard (`http://localhost:8080`), click **"Run Autonomous Swarm"**.
* **Narration**:
  > *"Let's trigger the autonomous swarm.*  
  > *First, **TriageAgent** leaps into action. It executes a 3-hop reverse traversal query on FalkorDB to calculate the blast radius—discovering that both the API Gateway and Checkout API are affected.*  
  > *Next, it traces the root cause to commit `4a1c78e` authored by Carol Zhang, and queries team ownership to identify her as the active on-call engineer.*  
  > *Then, TriageAgent queries our isolated memory graph, `agent_memory_swarm`, checking past episodic memory to see how similar incidents were resolved.*  
  > *Finally, it writes a formal `HandoffTicket` into FalkorDB.*  
  > *Instantly, **RemediationAgent** picks up the ticket from the shared blackboard, finds the corresponding operational runbook `RB-002`, executes the automated canary rollback, and mutates the incident status in FalkorDB to RESOLVED!"*

---

---

### 2:30 – 3:15 | Codebase AST Blast Radius & 1-Click Revert (45s)
* **Screen**: Switch to **Codebase AST & Git Blame** tab on `http://localhost:8080`.
* **Action**: Enter `d:\FalkorDB` or click the FalkorDB repo preset and click **"Ingest AST"**.
* **Narration**:
  > *"GraphOps doesn't stop at microservices. It can ingest any local or remote GitHub repository—parsing Python files, functions, and Git history into an AST call graph in FalkorDB.*  
  > *If a developer breaks a function like `calculate_function_blast_radius`, GraphOps instantly traverses upstream callers across multiple files in 3 milliseconds using GraphBLAS matrix multiplication.*  
  > *It then automatically correlates Git blame to discover who authored the breaking change and generates a 1-click `git revert` remediation ticket with ready-to-run shell commands."*

---

### 3:15 – 3:45 | Live GitHub Watcher Bot & CI/CD Interception (30s)
* **Screen**: Scroll to **Live GitHub CI/CD & Commit Watcher Bot** card.
* **Action**: Click **"Simulate Dev Commit"**, then click **"Simulate CI/CD Test Failure"**.
* **Narration**:
  > *"We've also built a live GitHub Webhook Watcher Bot. When engineers push commits or merge PRs, FalkorDB tracks modified files and authors in real time.*  
  > *And when CI/CD tests fail, the bot immediately intercepts the failure, computes the cascading blast radius, and posts an automated PR review comment directly to GitHub with the root-cause author and recovery commands."*

---

### 3:45 – 4:00 | Episodic Memory & Wrap-Up (15s)
* **Screen**: Point to the **Agent Memory & Coordination** tab and the **Persisted Episodes** counter.
* **Narration**:
  > *"Every step is traceable, every decision is explainable, and the entire traversal runs in under 4 milliseconds thanks to FalkorDB.*  
  > *This is GraphOps: Context for AI Agents. Thank you!"*
