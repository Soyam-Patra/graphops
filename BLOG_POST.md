# 🧠 How We Built an Autonomous Multi-Agent SRE Swarm with FalkorDB GraphBLAS Context

> *Submitting for Graph Hacks: Context for AI Agents (WeMakeDevs × FalkorDB)*  
> *Author: Solo Builder | Project: GraphOps*

---

## The Core Challenge: Why Vector RAG Fails in Production Incidents

In standard AI agent architectures, Retrieval-Augmented Generation (RAG) relies almost entirely on dense vector embeddings and cosine similarity. While vector databases excel at finding unstructured text paragraphs that *sound* like a user query, they fail catastrophically when an AI agent needs to reason across connected systems:

1. **Multi-Hop Blindness**: When an API returns HTTP 504 timeouts, an agent cannot guess which upstream services depend on it simply by comparing text vectors. It needs a graph traversal across API call edges: `(:Service)-[:CALLS*1..3]->(:Service)`.
2. **Loss of Session Continuity**: Agents suffer from context amnesia. If an outage was resolved three weeks ago by tweaking a connection pool, the agent loses that memory unless it is structured into persistent episodic nodes.
3. **Black-Box Decision Loops**: In mission-critical enterprise infrastructure, an SRE cannot trust an LLM that says *"I rolled back service X because I guessed so."* Every action must have an audit trail linked to a Git commit, a PR author, and an approved runbook.

To solve this, we built **GraphOps**: an autonomous multi-agent incident intelligence swarm that uses **FalkorDB** as its primary cognitive backbone across all three hackathon tracks.

---

## Why FalkorDB?

FalkorDB isn't just an ordinary graph database; it is specifically built for low-latency agent loops:

* **SuiteSparse:GraphBLAS Under the Hood**: FalkorDB represents graphs as sparse matrices and executes graph traversals using linear algebra matrix multiplication. This allowed our multi-hop blast radius queries to run in **under 4 milliseconds**, fast enough to sit inside an inner agent decision loop.
* **Multigraph Topology**: FalkorDB allows hosting thousands of isolated graphs in a single instance without extra infrastructure. We used this to cleanly separate:
  * `company_brain`: The public organizational topology.
  * `agent_memory_swarm`: The private episodic memory and multi-agent blackboard.

---

## Architectural Breakdown: 3 Tracks in 1 Unified System

### 1. Track 1: Agents That Act on Connected Data
When an incident is detected, **TriageAgent** executes a reverse traversal to discover all services impacted upstream:

```cypher
MATCH (target:Service {id: $service_id})
OPTIONAL MATCH path = (caller:Service)-[:CALLS*1..3]->(target)
WITH caller, min(length(path)) AS hops, [rel in relationships(path) | rel.avgRps] AS rpsList
RETURN caller.id, caller.name, caller.tier, hops, max(head(rpsList)) AS inbound_rps
ORDER BY hops ASC, caller.tier ASC
```

Simultaneously, it traverses code ownership to find the offending deployment:
```cypher
MATCH (inc:Incident {id: $incident_id})-[:AFFECTS]->(svc:Service)
MATCH (inc)-[:TRIGGERED_BY]->(c:Commit)-[:AUTHORED_BY]->(eng:Engineer)
RETURN inc.id, svc.name, c.sha, c.message, eng.name, eng.email
```
The agent acts directly on what this query returns.

---

### 2. Track 2: Agent Memory & Multi-Agent Coordination
Instead of keeping agent state in fragile in-memory dictionaries, our swarm coordinates via a shared blackboard in FalkorDB's `agent_memory_swarm` graph.

1. **Agent Handoff**: `TriageAgent` writes a `:HandoffTicket` node:
   ```cypher
   CREATE (h:HandoffTicket {
       ticket_id: $ticket_id,
       from_agent: 'TriageAgent',
       to_agent: 'RemediationAgent',
       incident_id: $incident_id,
       status: 'PENDING',
       diagnosis: $diagnosis,
       recommended_action: $action
   })
   ```
2. **Remediation Execution**: `RemediationAgent` polls for pending tickets, checks the procedural runbook, and drains canary traffic.
3. **Episodic Persistence**: Upon resolution, the agent stores an `:Episode` node:
   ```cypher
   CREATE (ep:Episode {
       episode_id: $episode_id,
       service_id: $service_id,
       root_cause: $root_cause,
       action_taken: $action,
       success: true,
       resolved_at: datetime()
   })
   ```
When an outage hits `auth-service` next month, the agent recalls this episode first.

---

### 3. Track 3: The Company Brain
The graph connects:
* Engineering Teams (`Team`)
* On-Call Rotations (`Engineer -[:ON_CALL_FOR]-> Team`)
* Microservice Call Graphs (`Service -[:CALLS]-> Service`)
* Datastores (`Service -[:DEPENDS_ON]-> Database`)
* Approved SOP Runbooks (`Runbook`)

When the outage occurs, the agent does not guess who to notify—it traverses `(:Service)<-[:OWNS]-(Team)<-[:ON_CALL_FOR]-(Engineer)` and immediately routes escalation to the right Slack channel.

---

## Interactive Dashboard & Visual Inspector

To make the system completely transparent, we built a modern FastAPI web dashboard (`http://localhost:8080`) that visualizes:
* Live node and edge counters in FalkorDB.
* Real-time chronological audit trail of agent steps.
* Computed blast radius and culprit commits.
* One-click trigger to run the swarm or re-seed outages.
* Direct deep-link to the FalkorDB Visual Browser (`http://localhost:3000`).

---

## Conclusion & Key Takeaways

1. **Graphs Provide Deterministic Context**: While LLMs can hallucinate answers, they cannot hallucinate when grounded in a rigid graph topology.
2. **Speed is Essential for Agent Swarms**: FalkorDB’s GraphBLAS performance ensures that multi-agent handoffs and traversals occur in milliseconds.
3. **Memory is More Than Chat History**: Structuring memory as episodes and handoffs transforms an AI from a novelty chatbot into an autonomous enterprise coworker.

---
*Check out the public repository and full documentation on GitHub: [github.com/your-username/graphops-falkordb](https://github.com/)*
