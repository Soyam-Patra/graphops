import sys
from falkordb import FalkorDB

def test_falkordb_connection():
    print("[*] Connecting to FalkorDB at localhost:6379...")
    try:
        db = FalkorDB(host="localhost", port=6379)
        # Select graph 'graphops_test'
        graph = db.select_graph("graphops_test")
        
        # Clean any old test data
        graph.query("MATCH (n) DETACH DELETE n")
        
        # Test creating nodes & relationship
        print("[*] Executing Cypher CREATE query...")
        query_create = """
        CREATE (s:Service {name: 'auth-service', tier: 'critical', lang: 'Go'})
        CREATE (d:Database {name: 'user-credentials-db', engine: 'PostgreSQL'})
        CREATE (s)-[:DEPENDS_ON {type: 'strict', timeoutMs: 500}]->(d)
        RETURN s.name AS service, d.name AS database
        """
        result = graph.query(query_create)
        for record in result.result_set:
            print(f"    [+] Created relationship: {record[0]} -> DEPENDS_ON -> {record[1]}")
            
        # Test querying with pattern matching
        print("[*] Executing Cypher MATCH query...")
        query_match = """
        MATCH (s:Service)-[r:DEPENDS_ON]->(d:Database)
        RETURN s.name AS service, s.tier AS tier, type(r) AS rel, d.name AS db, r.timeoutMs AS timeout
        """
        match_result = graph.query(query_match)
        for record in match_result.result_set:
            print(f"    [+] Verified from FalkorDB: {record[0]} (Tier: {record[1]}) -[{record[2]} timeout={record[4]}ms]-> {record[3]}")
            
        print("\n[SUCCESS] FalkorDB connection verified, GraphBLAS linear engine responsive!")
        print("          Visual Browser available at: http://localhost:3000")
        return True
    except Exception as e:
        print(f"\n[ERROR] Failed to connect to FalkorDB: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    success = test_falkordb_connection()
    sys.exit(0 if success else 1)
