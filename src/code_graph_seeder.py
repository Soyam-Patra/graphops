"""
FalkorDB Codebase Graph Ingestion Engine.
Takes parsed AST & Git metadata from CodebaseParser and stores it in FalkorDB
under an isolated multigraph ('codebase_graph').
Enables:
- Function-level blast radius analysis (CALLS*1..4)
- Git change tracking & author attribution (MODIFIED / AUTHORED_BY)
- Multi-file dependency mapping (IMPORTS)
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from typing import Dict, Any, List
from falkordb import FalkorDB
from src.code_parser import CodebaseParser

CODEBASE_GRAPH = "codebase_graph"

class CodebaseGraphSeeder:
    def __init__(self, host: str = "localhost", port: int = 6379, graph_name: str = CODEBASE_GRAPH):
        self.host = host
        self.port = port
        self.graph_name = graph_name
        self.db = FalkorDB(host=self.host, port=self.port)
        self.graph = self.db.select_graph(self.graph_name)

    def ingest_codebase(self, repo_data: Dict[str, Any]) -> Dict[str, int]:
        """
        Populates the FalkorDB codebase graph with repository AST nodes and Git history.
        """
        # 1. Reset old graph data for this codebase
        self.graph.query("MATCH (n) DETACH DELETE n")

        repo_name = repo_data["repository"]
        repo_path = repo_data["repo_path"]

        # 2. Create Repository Root Node
        self.graph.query(
            "CREATE (r:Repository {name: $name, path: $path})",
            {"name": repo_name, "path": repo_path}
        )

        # 3. Filter and limit entities for optimal graph performance
        files_to_ingest = repo_data.get("files", [])[:60]
        file_paths_set = {f["path"] for f in files_to_ingest}
        funcs_to_ingest = [fn for fn in repo_data.get("functions", []) if fn["file"] in file_paths_set][:250]
        func_ids_set = {fn["id"] for fn in funcs_to_ingest}
        calls_to_ingest = [c for c in repo_data.get("calls", []) if c["caller_func"] in func_ids_set][:350]
        commits_to_ingest = repo_data.get("commits", [])[:20]

        # Create Files and link to Repository
        for f in files_to_ingest:
            self.graph.query("""
            MATCH (r:Repository {name: $repo_name})
            CREATE (file:File {path: $path, name: $name, loc: $loc})
            CREATE (r)-[:CONTAINS]->(file)
            """, {
                "repo_name": repo_name,
                "path": f["path"],
                "name": f["name"],
                "loc": f["lines_of_code"]
            })

        # 4. Create Functions and link to Files
        for fn in funcs_to_ingest:
            self.graph.query("""
            MATCH (file:File {path: $file_path})
            CREATE (func:Function {
                id: $id,
                name: $name,
                file: $file_path,
                start_line: $start_line,
                end_line: $end_line,
                docstring: $docstring
            })
            CREATE (file)-[:DEFINES]->(func)
            """, {
                "file_path": fn["file"],
                "id": fn["id"],
                "name": fn["name"],
                "start_line": fn["start_line"],
                "end_line": fn["end_line"],
                "docstring": fn["docstring"]
            })

        # 5. Connect Function Calls
        for call in calls_to_ingest:
            self.graph.query("""
            MATCH (caller:Function {id: $caller_id})
            MATCH (callee:Function {name: $callee_name})
            WHERE caller <> callee
            MERGE (caller)-[r:CALLS {line: $line}]->(callee)
            """, {
                "caller_id": call["caller_func"],
                "callee_name": call["callee_name"],
                "line": call["line_number"]
            })

        # 6. Ingest Git Commits & Engineers
        for c in commits_to_ingest:
            # Upsert Engineer & Commit
            self.graph.query("""
            MERGE (eng:Engineer {email: $email})
            ON CREATE SET eng.name = $author
            CREATE (cm:Commit {
                sha: $sha,
                full_sha: $full_sha,
                message: $message,
                date: $date
            })
            CREATE (cm)-[:AUTHORED_BY]->(eng)
            """, {
                "email": c["email"],
                "author": c["author"],
                "sha": c["sha"],
                "full_sha": c["full_sha"],
                "message": c["message"],
                "date": c["date"]
            })

            # Link Commit to modified Files
            for mod_file in c.get("modified_files", []):
                self.graph.query("""
                MATCH (cm:Commit {sha: $sha}), (f:File {path: $file_path})
                MERGE (cm)-[:MODIFIED]->(f)
                """, {
                    "sha": c["sha"],
                    "file_path": mod_file
                })

        # Get summary metrics
        nodes = self.graph.query("MATCH (n) RETURN count(n)").result_set[0][0]
        edges = self.graph.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]

        return {
            "total_nodes": nodes,
            "total_relationships": edges,
            "files_ingested": len(repo_data.get("files", [])),
            "functions_ingested": len(repo_data.get("functions", []))
        }

if __name__ == "__main__":
    parser = CodebaseParser(".")
    parsed = parser.parse_repository()
    seeder = CodebaseGraphSeeder()
    stats = seeder.ingest_codebase(parsed)
    print(f"[SUCCESS] Codebase ingested into FalkorDB '{CODEBASE_GRAPH}': {stats}")
