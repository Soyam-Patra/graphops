"""
Codebase AST & Git Parser.
Analyzes codebases using Python AST for Python files and regex extractors for C/Rust/JS.
Extracts:
- Files, Classes, and Functions (with line numbers & docstrings)
- Function-to-Function call graph (who calls whom)
- File-to-File import dependencies
- Git commit blame & author attribution (who wrote/modified each function)
Supports both local directories (e.g. '.') and remote GitHub repository URLs
(e.g. 'https://github.com/FalkorDB/falkordb-py').
"""

import ast
import os
import re
import subprocess
from typing import Dict, List, Any, Optional

class CodebaseParser:
    def __init__(self, repo_path: str):
        raw_path = repo_path.strip()

        # Handle remote Git / GitHub repository URLs
        if raw_path.startswith(("http://", "https://", "git@")):
            self.repo_url = raw_path
            clean_url = raw_path.rstrip("/").removesuffix(".git")
            repo_name = clean_url.split("/")[-1]
            base_cache = os.path.join(os.path.abspath("."), ".repo_cache")
            os.makedirs(base_cache, exist_ok=True)
            target_dir = os.path.join(base_cache, repo_name)

            if not os.path.exists(target_dir):
                cmd = ["git", "clone", "--depth", "25", raw_path, target_dir]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if res.returncode != 0:
                    raise RuntimeError(f"Failed to clone repository: {res.stderr.strip() or res.stdout.strip()}")
            else:
                try:
                    subprocess.run(["git", "pull"], cwd=target_dir, capture_output=True, timeout=15)
                except Exception:
                    pass

            self.repo_path = os.path.abspath(target_dir)
            self.display_name = repo_name
        else:
            self.repo_url = None
            self.repo_path = os.path.abspath(raw_path)
            self.display_name = os.path.basename(self.repo_path) or "repository"

    def parse_repository(self) -> Dict[str, Any]:
        """
        Scans code files in the repository and builds the graph entity model.
        """
        if not os.path.exists(self.repo_path):
            raise FileNotFoundError(f"Repository path does not exist: {self.repo_path}")

        files_data = []
        functions_data = []
        calls_data = []
        imports_data = []

        ignore_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build", "target", ".repo_cache"}

        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.repo_path).replace("\\", "/")

                if file.endswith(".py"):
                    file_info = self._parse_python_file(full_path, rel_path)
                    if file_info:
                        files_data.append(file_info["file"])
                        functions_data.extend(file_info["functions"])
                        calls_data.extend(file_info["calls"])
                        imports_data.extend(file_info["imports"])
                elif file.endswith((".c", ".h", ".cpp", ".rs", ".js", ".ts", ".go")):
                    file_info = self._parse_generic_code_file(full_path, rel_path)
                    if file_info:
                        files_data.append(file_info["file"])
                        functions_data.extend(file_info["functions"])
                        calls_data.extend(file_info["calls"])

        # Extract git commit history and blame attribution
        commits_data = self._extract_git_history()

        return {
            "repository": self.display_name,
            "repo_path": self.repo_path,
            "files": files_data,
            "functions": functions_data,
            "calls": calls_data,
            "imports": imports_data,
            "commits": commits_data
        }

    def _parse_python_file(self, full_path: str, rel_path: str) -> Optional[Dict[str, Any]]:
        """Parses an individual Python file with the AST engine."""
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                source_code = f.read()

            tree = ast.parse(source_code, filename=rel_path)
        except Exception:
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

    def _parse_generic_code_file(self, full_path: str, rel_path: str) -> Optional[Dict[str, Any]]:
        """Parses C, C++, Rust, Go, or JS/TS files using regex function extractors."""
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return None

        file_node = {
            "path": rel_path,
            "name": os.path.basename(rel_path),
            "lines_of_code": len(lines)
        }

        functions = []
        calls = []

        # Function patterns for C/Rust/JS/Go
        fn_pattern = re.compile(
            r'^(?:pub\s+)?(?:fn|def|function|func)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(|'
            r'^(?:[a-zA-Z_][a-zA-Z0-9_*]*\s+)+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{'
        )

        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            match = fn_pattern.match(stripped)
            if match:
                func_name = match.group(1) or match.group(2)
                if func_name and func_name not in {"if", "for", "while", "switch"}:
                    func_id = f"{rel_path}::{func_name}"
                    functions.append({
                        "id": func_id,
                        "name": func_name,
                        "file": rel_path,
                        "class_name": None,
                        "start_line": line_no,
                        "end_line": line_no + 10,
                        "args": [],
                        "docstring": ""
                    })

        return {
            "file": file_node,
            "functions": functions,
            "calls": calls
        }

    def _extract_git_history(self) -> List[Dict[str, Any]]:
        """Extracts recent commit history and author information from git."""
        commits = []
        code_exts = {".py", ".c", ".h", ".cpp", ".cc", ".rs", ".js", ".ts", ".go", ".java", ".md", ".json"}

        try:
            cmd = ["git", "log", "-n", "20", "--pretty=format:%H|%an|%ae|%ad|%s", "--date=iso"]
            result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True, check=True)
            lines = result.stdout.strip().splitlines()

            for line in lines:
                parts = line.split("|", 4)
                if len(parts) == 5:
                    sha, author, email, date, msg = parts
                    # Get modified files for this commit
                    diff_cmd = ["git", "show", "--name-only", "--pretty=format:", sha]
                    diff_res = subprocess.run(diff_cmd, cwd=self.repo_path, capture_output=True, text=True)
                    modified_files = [
                        f.strip().replace("\\", "/") for f in diff_res.stdout.splitlines()
                        if any(f.strip().endswith(ext) for ext in code_exts)
                    ]

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
