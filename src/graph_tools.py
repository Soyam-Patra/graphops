"""
FalkorDB Graph Intelligence Tools Layer.
Provides high-performance Cypher and Graph Analytics tools for AI agents.
Adheres to Track 1 (Agents That Act on Connected Data).
"""

from typing import List, Dict, Any, Optional
from falkordb import FalkorDB

class GraphTools:
    def __init__(self, host: str = "localhost", port: int = 6379, graph_name: str = "company_brain"):
        self.host = host
        self.port = port
        self.graph_name = graph_name
        self.db = FalkorDB(host=self.host, port=self.port)
        self.graph = self.db.select_graph(self.graph_name)

    def get_active_incidents(self) -> List[Dict[str, Any]]:
        """
        Tool: Retrieve all currently active incidents requiring investigation.
        """
        query = """
        MATCH (inc:Incident {status: 'ACTIVE'})-[:AFFECTS]->(svc:Service)
        RETURN inc.id AS incident_id, inc.title AS title, inc.severity AS severity,
               inc.symptom AS symptom, inc.detectedAt AS detected_at,
               svc.id AS service_id, svc.name AS service_name, svc.tier AS service_tier
        """
        res = self.graph.query(query)
        incidents = []
        for r in res.result_set:
            incidents.append({
                "incident_id": r[0],
                "title": r[1],
                "severity": r[2],
                "symptom": r[3],
                "detected_at": r[4],
                "service_id": r[5],
                "service_name": r[6],
                "service_tier": r[7]
            })
        return incidents

    def trace_root_cause(self, incident_id: str) -> Dict[str, Any]:
        """
        Tool: Multi-hop traversal to determine the root cause commit and author.
        """
        query = """
        MATCH (inc:Incident {id: $incident_id})-[:AFFECTS]->(svc:Service)
        OPTIONAL MATCH (inc)-[:TRIGGERED_BY]->(c:Commit)-[:AUTHORED_BY]->(eng:Engineer)
        OPTIONAL MATCH (svc)-[:DEPENDS_ON]->(db:Database)
        RETURN inc.id AS incident_id,
               svc.name AS service_name,
               c.sha AS commit_sha,
               c.message AS commit_msg,
               c.pullRequest AS pr,
               eng.name AS author_name,
               eng.email AS author_email,
               collect(DISTINCT db.name) AS dependent_databases
        """
        res = self.graph.query(query, {"incident_id": incident_id})
        if not res.result_set:
            return {"error": f"Incident {incident_id} not found"}

        r = res.result_set[0]
        return {
            "incident_id": r[0],
            "affected_service": r[1],
            "suspect_commit": {
                "sha": r[2],
                "message": r[3],
                "pr": r[4],
                "author": r[5],
                "email": r[6]
            } if r[2] else None,
            "dependent_databases": r[7]
        }

    def calculate_blast_radius(self, service_id: str, max_hops: int = 3) -> Dict[str, Any]:
        """
        Tool: Performs multi-hop reverse traversal (CALLS*1..max_hops) to evaluate
        all upstream callers impacted if the given service degrades or fails.
        """
        query = f"""
        MATCH (target:Service {{id: $service_id}})
        OPTIONAL MATCH path = (caller:Service)-[:CALLS*1..{max_hops}]->(target)
        WITH target, caller, length(path) AS distance,
             [rel in relationships(path) | rel.avgRps] AS rpsList
        WHERE caller IS NOT NULL
        RETURN caller.id AS caller_id,
               caller.name AS caller_name,
               caller.tier AS caller_tier,
               min(distance) AS min_hops,
               max(head(rpsList)) AS direct_rps
        ORDER BY min_hops ASC, caller_tier ASC
        """
        res = self.graph.query(query, {"service_id": service_id})
        impacted_services = []
        for r in res.result_set:
            impacted_services.append({
                "service_id": r[0],
                "name": r[1],
                "tier": r[2],
                "hops_from_failure": r[3],
                "inbound_rps": r[4]
            })

        return {
            "origin_service_id": service_id,
            "total_impacted_services": len(impacted_services),
            "critical_tier_0_impacted": sum(1 for s in impacted_services if s["tier"] == "Tier-0"),
            "impacted_services": impacted_services
        }

    def find_service_owners_and_oncall(self, service_id: str) -> Dict[str, Any]:
        """
        Tool: Graph query connecting service -> team -> engineers to identify
        the owning team, communication channels, and active on-call responders.
        """
        query = """
        MATCH (s:Service {id: $service_id})<-[:OWNS]-(t:Team)
        OPTIONAL MATCH (oncall:Engineer)-[:ON_CALL_FOR]->(t)
        OPTIONAL MATCH (eng:Engineer)-[:MEMBER_OF]->(t)
        RETURN t.name AS team_name,
               t.slack AS slack_channel,
               t.tier AS team_tier,
               oncall.name AS on_call_name,
               oncall.email AS on_call_email,
               collect(DISTINCT eng.name) AS team_members
        """
        res = self.graph.query(query, {"service_id": service_id})
        if not res.result_set:
            return {"error": f"No team ownership found for service {service_id}"}

        r = res.result_set[0]
        return {
            "service_id": service_id,
            "owning_team": r[0],
            "slack_channel": r[1],
            "team_tier": r[2],
            "on_call_responder": {
                "name": r[3],
                "email": r[4]
            } if r[3] else None,
            "team_roster": r[5]
        }

    def find_matching_runbook(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """
        Tool: Resolves the procedural runbook linked to the incident or affected service.
        """
        query = """
        MATCH (inc:Incident {id: $incident_id})-[:RECOMMENDED_RUNBOOK]->(rb:Runbook)
        RETURN rb.id AS runbook_id,
               rb.title AS title,
               rb.steps AS steps,
               rb.automatedAction AS automated_action,
               rb.targetComponent AS target_component
        """
        res = self.graph.query(query, {"incident_id": incident_id})
        if not res.result_set:
            return None

        r = res.result_set[0]
        return {
            "runbook_id": r[0],
            "title": r[1],
            "steps": r[2],
            "automated_action": r[3],
            "target_component": r[4]
        }

    def find_critical_bottlenecks(self) -> List[Dict[str, Any]]:
        """
        Tool (Graph Analytics): Computes degree centrality (in-degree and out-degree)
        across services to discover architectural choke points and single points of failure.
        """
        query = """
        MATCH (s:Service)
        OPTIONAL MATCH (s)<-[in_rel:CALLS]-(upstream:Service)
        OPTIONAL MATCH (s)-[out_rel:CALLS]->(downstream:Service)
        WITH s, count(DISTINCT upstream) AS in_degree, count(DISTINCT downstream) AS out_degree
        RETURN s.id AS service_id,
               s.name AS service_name,
               s.tier AS tier,
               in_degree,
               out_degree,
               (in_degree + out_degree) AS total_connectivity
        ORDER BY total_connectivity DESC
        """
        res = self.graph.query(query)
        bottlenecks = []
        for r in res.result_set:
            bottlenecks.append({
                "service_id": r[0],
                "name": r[1],
                "tier": r[2],
                "in_degree": r[3],
                "out_degree": r[4],
                "total_centrality": r[5]
            })
        return bottlenecks
