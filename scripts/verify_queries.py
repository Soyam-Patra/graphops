"""
Verification queries demonstrating multi-hop graph reasoning over FalkorDB.
"""

from falkordb import FalkorDB

def verify():
    db = FalkorDB(host="localhost", port=6379)
    graph = db.select_graph("company_brain")

    print("\n--- [Query 1]: Find Active Incident, Root-Cause Commit & Author ---")
    q1 = """
    MATCH (inc:Incident {status: 'ACTIVE'})-[:TRIGGERED_BY]->(c:Commit)-[:AUTHORED_BY]->(eng:Engineer)
    MATCH (inc)-[:AFFECTS]->(svc:Service)
    RETURN inc.id AS incident, svc.name AS affectedService, c.sha AS commitSha, c.message AS commitMsg, eng.name AS author, eng.email AS email
    """
    res1 = graph.query(q1)
    for r in res1.result_set:
        print(f"Incident: {r[0]}")
        print(f"Affected Service: {r[1]}")
        print(f"Suspect Commit: {r[2]} ('{r[3]}')")
        print(f"Author: {r[4]} <{r[5]}>")

    print("\n--- [Query 2]: Multi-hop Blast Radius (Services that call the affected service) ---")
    q2 = """
    MATCH (s:Service {id: 'auth-service'})<-[:CALLS*1..2]-(dependent:Service)
    RETURN DISTINCT dependent.name AS callerService, dependent.tier AS tier
    """
    res2 = graph.query(q2)
    for r in res2.result_set:
        print(f"  -> Blast Radius Impact: {r[0]} ({r[1]})")

    print("\n--- [Query 3]: Find On-Call SRE & Team owning the affected service ---")
    q3 = """
    MATCH (svc:Service {id: 'auth-service'})<-[:OWNS]-(t:Team)<-[:ON_CALL_FOR]-(oncall:Engineer)
    RETURN t.name AS owningTeam, t.slack AS slackChannel, oncall.name AS onCallEngineer, oncall.role AS role
    """
    res3 = graph.query(q3)
    for r in res3.result_set:
        print(f"Team: {r[0]} ({r[1]})")
        print(f"On-Call Responder: {r[2]} - {r[3]}")

if __name__ == "__main__":
    verify()
