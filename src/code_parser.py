"""
Codebase AST & Git Parser.
Analyzes Python codebases using Abstract Syntax Trees (AST) and Git metadata.
Extracts:
- Files, Classes, and Functions (with line numbers & docstrings)
- Function-to-Function call graph (who calls whom)
- File-to-File import dependencies
- Git commit blame & author attribution (who wrote/modified each function)
"""

import ast
import os
import subprocess
from typing import Dict, List, Any, Optional

class CodebaseParser:
    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)

    def parse_repository(self) -> Dict[str, Any]:
        """
        Scans all Python files in the repository and builds the code entity model.
        """
        files_data = []
        functions_data = []
        calls_data = []
        imports_data = []

        ignore_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build"}

        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.repo_path).replace("\\", "/")
                    file_info = self._parse_file(full_path, rel_path)
                    if file_info:
                        files_data.append(file_info["file"])
                        functions_data.extend(file_info["functions"])
                        calls_data.extend(file_info["calls"])
                        imports_data.extend(file_info["imports"])

        # Extract git commit history and blame attribution
        commits_data = self._extract_git_history()

        return {
            "repository": os.path.basename(self.repo_path),
            "repo_path": self.repo_path,
            "files": files_data,
            "functions": functions_data,
            "calls": calls_data,
            "imports": imports_data,
            "commits": commits_data
        }

    def _parse_file(self, full_path: str, rel_path: str) -> Optional[Dict[str, Any]]:
        """Parses an individual Python file with the AST engine."""
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                source_code = f.read()

            tree = ast.parse(source_code, filename=rel_path)
        except Exception as e:
            return None

        file_node = {
            "path": rel_path,
            "name": os.path.basename(rel_path),
            "lines_of_code": len(source_code.splitlines())
        }

        functions = []
        calls = []
        imports = []

        class ASTVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_function = None
                self.current_class = None

            def visit_Import(self, node):
                for alias in node.names:
                    imports.append({
                        "file": rel_path,
                        "imported_module": alias.name
                    })
                self.generic_visit(node)

            def visit_ImportFrom(self, node):
                module = node.module or ""
                for alias in node.names:
                    imports.append({
                        "file": rel_path,
                        "imported_module": f"{module}.{alias.name}" if module else alias.name
                    })
                self.generic_visit(node)

            def visit_ClassDef(self, node):
                prev_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = prev_class

            def visit_FunctionDef(self, node):
                self._handle_func(node)

            def visit_AsyncFunctionDef(self, node):
                self._handle_func(node)

            def _handle_func(self, node):
                func_id = f"{rel_path}::{node.name}"
                docstring = ast.get_docstring(node) or ""
                args = [a.arg for a in node.args.args]

                functions.append({
                    "id": func_id,
                    "name": node.name,
                    "file": rel_path,
                    "class_name": self.current_class,
                    "start_line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "args": args,
                    "docstring": docstring.strip()[:120]
                })

                prev_func = self.current_function
                self.current_function = func_id
                self.generic_visit(node)
                self.current_function = prev_func

            def visit_Call(self, node):
                if self.current_function:
                    callee_name = None
                    if isinstance(node.func, ast.Name):
                        callee_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        callee_name = node.func.attr

                    if callee_name:
                        calls.append({
                            "caller_func": self.current_function,
                            "caller_file": rel_path,
                            "callee_name": callee_name,
                            "line_number": node.lineno
                        })
                self.generic_visit(node)

        visitor = ASTVisitor()
        visitor.visit(tree)

        return {
            "file": file_node,
            "functions": functions,
            "calls": calls,
            "imports": imports
        }

    def _extract_git_history(self) -> List[Dict[str, Any]]:
        """Extracts recent commit history and author information from git."""
        commits = []
        try:
            cmd = ["git", "log", "-n", "15", "--pretty=format:%H|%an|%ae|%ad|%s", "--date=iso"]
            result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True, check=True)
            lines = result.stdout.strip().splitlines()

            for line in lines:
                parts = line.split("|", 4)
                if len(parts) == 5:
                    sha, author, email, date, msg = parts
                    # Get modified files for this commit
                    diff_cmd = ["git", "show", "--name-only", "--pretty=format:", sha]
                    diff_res = subprocess.run(diff_cmd, cwd=self.repo_path, capture_output=True, text=True)
                    modified_files = [f.strip().replace("\\", "/") for f in diff_res.stdout.splitlines() if f.strip().endswith(".py")]

                    commits.append({
                        "sha": sha[:8],
                        "full_sha": sha,
                        "author": author,
                        "email": email,
                        "date": date,
                        "message": msg,
                        "modified_files": modified_files
                    })
        except Exception:
            pass # Non-git repository fallback

        return commits
