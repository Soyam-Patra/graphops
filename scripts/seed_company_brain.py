"""
Seed Script: Populates FalkorDB with a realistic "Company Brain" knowledge graph.
Includes:
- Teams & Engineers (Who owns what & who is on-call)
- Microservices & Datastores (Topology & Call dependencies)
- Git Commits & Deployments (Traceability to code changes)
- Active & Historical Incidents (Episodic context)
- Standard Operating Procedure Runbooks (Procedural context)
"""

import sys
from falkordb import FalkorDB

GRAPH_NAME = "company_brain"

def seed_company_brain():
    print(f"[*] Connecting to FalkorDB to populate graph '{GRAPH_NAME}'...")
    db = FalkorDB(host="localhost", port=6379)
    graph = db.select_graph(GRAPH_NAME)

    # 1. Clear existing graph data for a clean reproducible state
    print("    [1/5] Resetting existing graph topology...")
    graph.query("MATCH (n) DETACH DELETE n")

    # 2. Create Teams and Engineers
    print("    [2/5] Creating Teams, Engineers, and Ownership relationships...")
    teams_and_engineers = """
    CREATE (t_plat:Team {name: 'Platform Core', slack: '#eng-platform', tier: 1}),
           (t_pay:Team {name: 'Payments & Checkout', slack: '#eng-payments', tier: 1}),
           (t_id:Team {name: 'Identity & Sec', slack: '#eng-auth', tier: 1}),
           (t_inv:Team {name: 'Fulfillment & Logistics', slack: '#eng-inventory', tier: 2}),

           (e_alice:Engineer {name: 'Alice Chen', email: 'alice@company.internal', role: 'Staff SRE', onCall: true}),
           (e_bob:Engineer {name: 'Bob Martin', email: 'bob@company.internal', role: 'Senior Backend Engineer', onCall: false}),
           (e_carol:Engineer {name: 'Carol Zhang', email: 'carol@company.internal', role: 'Security Architect', onCall: true}),
           (e_dave:Engineer {name: 'Dave Patel', email: 'dave@company.internal', role: 'Infrastructure Lead', onCall: false}),

           (e_alice)-[:MEMBER_OF {role: 'Lead SRE'}]->(t_plat),
           (e_bob)-[:MEMBER_OF {role: 'Backend Dev'}]->(t_pay),
           (e_carol)-[:MEMBER_OF {role: 'Security Specialist'}]->(t_id),
           (e_dave)-[:MEMBER_OF {role: 'Infra Engineer'}]->(t_inv),

           (e_alice)-[:ON_CALL_FOR]->(t_plat),
           (e_carol)-[:ON_CALL_FOR]->(t_id)
    """
    graph.query(teams_and_engineers)

    # 3. Create Services, Endpoints, Databases, and Infrastructure Topology
    print("    [3/5] Building Microservice topology, API chains, and DB dependencies...")
    services_topology = """
    CREATE (db_auth:Database {name: 'auth-postgres-cluster', engine: 'PostgreSQL 16', port: 5432, storage: '1TB'}),
           (db_pay:Database {name: 'ledger-cockroachdb', engine: 'CockroachDB', port: 26257, region: 'multi-region'}),
           (cache_redis:Database {name: 'edge-session-redis', engine: 'Redis 7', port: 6380, memoryLimit: '16GB'}),
           (db_orders:Database {name: 'orders-mongodb', engine: 'MongoDB Atlas', port: 27017, cluster: 'tier-3'}),

           (s_gateway:Service {
               id: 'api-gateway', name: 'API Gateway', tier: 'Tier-0',
               repo: 'github.com/org/api-gateway', lang: 'Rust', p99TargetMs: 50
           }),
           (s_auth:Service {
               id: 'auth-service', name: 'Authentication Service', tier: 'Tier-0',
               repo: 'github.com/org/auth-service', lang: 'Go', p99TargetMs: 80
           }),
           (s_checkout:Service {
               id: 'checkout-api', name: 'Checkout Service', tier: 'Tier-0',
               repo: 'github.com/org/checkout-api', lang: 'Node.js', p99TargetMs: 150
           }),
           (s_pay:Service {
               id: 'payment-processor', name: 'Payment Processor', tier: 'Tier-0',
               repo: 'github.com/org/payment-processor', lang: 'Java/Spring', p99TargetMs: 200
           }),
           (s_order:Service {
               id: 'order-manager', name: 'Order Management Service', tier: 'Tier-1',
               repo: 'github.com/org/order-manager', lang: 'Python/FastAPI', p99TargetMs: 120
           }),
           (s_notify:Service {
               id: 'notification-worker', name: 'Notification Worker', tier: 'Tier-2',
               repo: 'github.com/org/notification-worker', lang: 'Go', p99TargetMs: 300
           }),

           (s_gateway)-[:CALLS {protocol: 'gRPC', avgRps: 12000, timeoutMs: 150}]->(s_auth),
           (s_gateway)-[:CALLS {protocol: 'HTTP/2', avgRps: 4500, timeoutMs: 300}]->(s_checkout),
           (s_checkout)-[:CALLS {protocol: 'gRPC', avgRps: 2100, timeoutMs: 250}]->(s_auth),
           (s_checkout)-[:CALLS {protocol: 'gRPC', avgRps: 1800, timeoutMs: 500}]->(s_pay),
           (s_checkout)-[:CALLS {protocol: 'HTTP/2', avgRps: 1800, timeoutMs: 350}]->(s_order),
           (s_order)-[:CALLS {protocol: 'AsyncQueue', avgRps: 600, timeoutMs: 1000}]->(s_notify),

           (s_auth)-[:DEPENDS_ON {mode: 'RW', poolSize: 50}]->(db_auth),
           (s_auth)-[:DEPENDS_ON {mode: 'RW', poolSize: 100}]->(cache_redis),
           (s_pay)-[:DEPENDS_ON {mode: 'RW_ACID', poolSize: 40}]->(db_pay),
           (s_order)-[:DEPENDS_ON {mode: 'RW', poolSize: 30}]->(db_orders)
    """
    graph.query(services_topology)

    # Link Teams to Services
    team_ownership = """
    MATCH (t_plat:Team {name: 'Platform Core'}), (t_id:Team {name: 'Identity & Sec'}),
          (t_pay:Team {name: 'Payments & Checkout'}), (t_inv:Team {name: 'Fulfillment & Logistics'}),
          (s_gateway:Service {id: 'api-gateway'}), (s_auth:Service {id: 'auth-service'}),
          (s_checkout:Service {id: 'checkout-api'}), (s_pay:Service {id: 'payment-processor'}),
          (s_order:Service {id: 'order-manager'}), (s_notify:Service {id: 'notification-worker'})
    CREATE (t_plat)-[:OWNS {sla: '99.99%'}]->(s_gateway),
           (t_id)-[:OWNS {sla: '99.99%'}]->(s_auth),
           (t_pay)-[:OWNS {sla: '99.95%'}]->(s_checkout),
           (t_pay)-[:OWNS {sla: '99.99%'}]->(s_pay),
           (t_inv)-[:OWNS {sla: '99.9%'}]->(s_order),
           (t_plat)-[:OWNS {sla: '99.5%'}]->(s_notify)
    """
    graph.query(team_ownership)

    # 4. Create Recent Commits and Deployments (Traceability)
    print("    [4/5] Ingesting Git commits, pull requests, and author links...")
    git_commits = """
    MATCH (e_bob:Engineer {name: 'Bob Martin'}), (s_pay:Service {id: 'payment-processor'})
    CREATE (c1:Commit {
        sha: '9f8b12a',
        message: 'fix: optimize payment gateway retry backoff logic',
        timestamp: '2026-10-12T14:30:00Z',
        filesChanged: 4,
        pullRequest: '#1042'
    }),
    (c1)-[:AUTHORED_BY]->(e_bob),
    (c1)-[:DEPLOYED_TO {env: 'production', status: 'live', deployedAt: '2026-10-12T15:00:00Z'}]->(s_pay)
    """
    graph.query(git_commits)

    git_commits_auth = """
    MATCH (e_carol:Engineer {name: 'Carol Zhang'}), (s_auth:Service {id: 'auth-service'})
    CREATE (c2:Commit {
        sha: '4a1c78e',
        message: 'feat: add JWKS rotation cache TTL to Redis connection',
        timestamp: '2026-10-12T18:15:00Z',
        filesChanged: 2,
        pullRequest: '#892'
    }),
    (c2)-[:AUTHORED_BY]->(e_carol),
    (c2)-[:DEPLOYED_TO {env: 'production', status: 'live', deployedAt: '2026-10-12T18:45:00Z'}]->(s_auth)
    """
    graph.query(git_commits_auth)

    # 5. Create Runbooks & Incident Context
    print("    [5/5] Ingesting Incident Runbooks and Active Outage records...")
    runbooks = """
    CREATE (rb_db_pool:Runbook {
        id: 'RB-001',
        title: 'Database Connection Pool Exhaustion Mitigation',
        steps: '1. Scale replica read-pool. 2. Restart stalled worker pods. 3. Flush leaked Redis idle connections.',
        targetComponent: 'Database',
        automatedAction: 'FLUSH_IDLE_POOL_AND_RESTART_REPLICAS'
    }),
    (rb_rollback:Runbook {
        id: 'RB-002',
        title: 'Canary Rollback & Traffic Drain',
        steps: '1. Set canary traffic to 0%. 2. Revert service to previous Git SHA. 3. Invalidate route cache.',
        targetComponent: 'Service',
        automatedAction: 'REVERT_CANARY_DEPLOYMENT'
    }),
    (rb_circuit_breaker:Runbook {
        id: 'RB-003',
        title: 'Upstream Circuit Breaker Trip',
        steps: '1. Activate fallback degraded mode. 2. Shed non-essential traffic tier.',
        targetComponent: 'Service',
        automatedAction: 'ENABLE_CIRCUIT_BREAKER_FALLBACK'
    })
    """
    graph.query(runbooks)

    incident_trigger = """
    MATCH (s_auth:Service {id: 'auth-service'}), 
          (c2:Commit {sha: '4a1c78e'}), 
          (rb_rollback:Runbook {id: 'RB-002'})
    CREATE (inc:Incident {
        id: 'INC-2026-881',
        title: 'Cascading HTTP 504 Gateway Timeouts on Checkout Flow',
        severity: 'SEV-1',
        status: 'ACTIVE',
        detectedAt: '2026-10-12T19:20:00Z',
        symptom: 'API Gateway reporting 18% error rate on /v1/checkout/pay; Auth Service latency P99 jumped from 80ms to 4200ms'
    }),
    (inc)-[:AFFECTS {impactLevel: 'CRITICAL'}]->(s_auth),
    (inc)-[:TRIGGERED_BY]->(c2),
    (inc)-[:RECOMMENDED_RUNBOOK]->(rb_rollback)
    """
    graph.query(incident_trigger)

    # Verification counts
    nodes_count = graph.query("MATCH (n) RETURN count(n) AS cnt").result_set[0][0]
    edges_count = graph.query("MATCH ()-[r]->() RETURN count(r) AS cnt").result_set[0][0]

    print("\n" + "=" * 60)
    print(f"[SUCCESS] Company Brain graph '{GRAPH_NAME}' seeded successfully!")
    print(f"          Total Nodes:         {nodes_count}")
    print(f"          Total Relationships: {edges_count}")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = seed_company_brain()
    sys.exit(0 if success else 1)
