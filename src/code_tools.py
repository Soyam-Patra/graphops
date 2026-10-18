"""
Codebase Graph Intelligence & Blast Radius Tools.
Queries the FalkorDB 'codebase_graph' to perform:
1. Function-level blast radius analysis (who breaks when a function is changed).
2. Git blame & author attribution (who authored the commit that touched this function).
3. Critical function bottleneck detection via Degree Centrality.
4. Automated revert/patch ticket generation for multi-agent triage.
"""

import os
from typing import List, Dict, Any, Optional
from falkordb import FalkorDB

CODEBASE_GRAPH = "codebase_graph"

class CodebaseTools:
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None, graph_name: str = CODEBASE_GRAPH):
        self.host = host if host is not None else os.getenv("FALKORDB_HOST", "localhost")
        self.port = port if port is not None else int(os.getenv("FALKORDB_PORT", 6379))
        self.graph_name = graph_name
        self.db = FalkorDB(host=self.host, port=self.port)
        self.graph = self.db.select_graph(self.graph_name)

    def calculate_function_blast_radius(self, func_name: str, max_hops: int = 4) -> Dict[str, Any]:
        """
        Tool: Multi-hop reverse traversal (CALLS*1..max_hops) to discover all
        functions and files impacted if the target function breaks or changes.
        """
        query = f"""
        MATCH (target:Function)
        WHERE target.name = $func_name OR target.id = $func_name
        OPTIONAL MATCH path = (caller:Function)-[:CALLS*1..{max_hops}]->(target)
        WITH caller, min(length(path)) AS hops, target
        WHERE caller IS NOT NULL AND caller <> target
        RETURN caller.id AS caller_id,
               caller.name AS caller_name,
               caller.file AS caller_file,
               caller.start_line AS start_line,
               hops
        ORDER BY hops ASC, caller_file ASC
        """
        res = self.graph.query(query, {"func_name": func_name})
        impacted = []
        for r in res.result_set:
            impacted.append({
                "function_id": r[0],
                "function_name": r[1],
                "file": r[2],
                "start_line": r[3],
                "hops": r[4]
            })

        affected_files = list(set(item["file"] for item in impacted))

        return {
            "target_function": func_name,
            "total_impacted_functions": len(impacted),
            "total_affected_files": len(affected_files),
            "affected_files": affected_files,
            "impacted_functions": impacted
        }

    def get_function_author_and_commit(self, func_name: str) -> Optional[Dict[str, Any]]:
        """
        Tool: Traverses Function <- File <- Commit -> Engineer to find
        who last touched the file containing this function.
        """
        query = """
        MATCH (f:Function)<-[:DEFINES]-(file:File)<-[:MODIFIED]-(cm:Commit)-[:AUTHORED_BY]->(eng:Engineer)
        WHERE f.name = $func_name OR f.id = $func_name
        RETURN cm.sha AS sha,
               cm.message AS message,
               cm.date AS date,
               eng.name AS author,
               eng.email AS email,
               file.path AS file_path
        ORDER BY cm.date DESC
        LIMIT 1
        """
        res = self.graph.query(query, {"func_name": func_name})
        if not res.result_set:
            return None

        r = res.result_set[0]
        return {
            "function_name": func_name,
            "file": r[5],
            "commit_sha": r[0],
            "commit_message": r[1],
            "commit_date": r[2],
            "author_name": r[3],
            "author_email": r[4]
        }

    def find_most_critical_functions(self, limit: int = 8) -> List[Dict[str, Any]]:
        """
        Tool: Degree Centrality across the codebase call graph.
        Finds the core foundational functions called by the most callers.
        """
        query = """
        MATCH (f:Function)
        OPTIONAL MATCH (f)<-[:CALLS]-(caller:Function)
        OPTIONAL MATCH (f)-[:CALLS]->(callee:Function)
        WITH f, count(DISTINCT caller) AS in_degree, count(DISTINCT callee) AS out_degree
        WHERE (in_degree + out_degree) > 0
        RETURN f.id AS id,
               f.name AS name,
               f.file AS file,
               in_degree,
               out_degree,
               (in_degree + out_degree) AS total_calls
        ORDER BY total_calls DESC
        LIMIT $limit
        """
        res = self.graph.query(query, {"limit": limit})
        functions = []
        for r in res.result_set:
            functions.append({
                "id": r[0],
                "name": r[1],
                "file": r[2],
                "in_degree": r[3],
                "out_degree": r[4],
                "total_calls": r[5]
            })
        return functions

    def generate_revert_ticket(self, func_name: str, error_symptom: str) -> Dict[str, Any]:
        """
        Generates an automated Git remediation / revert ticket.
        Combines blast radius with author blame.
        """
        blast = self.calculate_function_blast_radius(func_name)
        author_info = self.get_function_author_and_commit(func_name)

        ticket_id = f"CODE-TICKET-{func_name.upper()[:6]}"
        return {
            "ticket_id": ticket_id,
            "broken_function": func_name,
            "error_symptom": error_symptom,
            "culprit_author": author_info["author_name"] if author_info else "Unknown",
            "culprit_email": author_info["author_email"] if author_info else "Unknown",
            "culprit_commit": author_info["commit_sha"] if author_info else "Unknown",
            "commit_message": author_info["commit_message"] if author_info else "N/A",
            "blast_radius_functions_count": blast["total_impacted_functions"],
            "impacted_files": blast["affected_files"],
            "recommended_action": f"git revert {author_info['commit_sha']}" if author_info else "Inspect and hotfix function"
        }
