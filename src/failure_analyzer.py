"""
Failure Localization and Stack Trace Analyzer.
Parses runtime test failures, stack traces, and CI exception logs to extract:
1. Failing location vs. suspected root cause vs. confirmed root cause.
2. Direct runtime evidence vs. inferred graph analysis.
3. Exception type, message, stack frames, file and line locations.
"""

import re
import os
from typing import Dict, Any, List, Optional

class FailureEvidence:
    def __init__(
        self,
        repository_id: str = "graphops",
        branch: str = "main",
        commit_sha: str = "HEAD",
        indexed_revision: str = "HEAD",
        failing_test: str = "unknown_test",
        test_command: str = "python -m unittest discover tests/",
        exception_type: str = "UnknownException",
        exception_message: str = "",
        stack_frames: Optional[List[Dict[str, Any]]] = None,
        failing_location: Optional[Dict[str, Any]] = None,
        suspected_root_cause: Optional[Dict[str, Any]] = None,
        evidence_type: str = "DIRECT_RUNTIME_TRACE",
        raw_traceback: str = ""
    ):
        self.repository_id = repository_id
        self.branch = branch
        self.commit_sha = commit_sha
        self.indexed_revision = indexed_revision
        self.failing_test = failing_test
        self.test_command = test_command
        self.exception_type = exception_type
        self.exception_message = exception_message
        self.stack_frames = stack_frames or []
        self.failing_location = failing_location or {}
        self.suspected_root_cause = suspected_root_cause or self.failing_location
        self.confirmed_root_cause = None  # Confirmed ONLY after verification
        self.evidence_type = evidence_type
        self.raw_traceback = raw_traceback

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repository_id": self.repository_id,
            "branch": self.branch,
            "commit_sha": self.commit_sha,
            "indexed_revision": self.indexed_revision,
            "failing_test": self.failing_test,
            "test_command": self.test_command,
            "exception_type": self.exception_type,
            "exception_message": self.exception_message,
            "stack_frames": self.stack_frames,
            "failing_location": self.failing_location,
            "suspected_root_cause": self.suspected_root_cause,
            "confirmed_root_cause": self.confirmed_root_cause,
            "evidence_type": self.evidence_type,
            "caveat": "Do not treat a function's presence in a stack trace as definitive proof that it introduced the bug. Causality must be confirmed by commit diff inspection and test verification."
        }

class FailureAnalyzer:
    @staticmethod
    def parse_traceback(
        traceback_text: str,
        repository_id: str = "graphops",
        branch: str = "main",
        commit_sha: str = "HEAD",
        test_command: str = "python -m unittest discover tests/"
    ) -> FailureEvidence:
        """
        Parses standard Python traceback strings, pytest/unittest outputs,
        and extracts frames, exception types, and exact source lines.
        """
        lines = traceback_text.strip().splitlines()
        frames: List[Dict[str, Any]] = []
        exception_type = "Exception"
        exception_message = ""
        failing_test = "test_case"

        # Regex patterns for Python traceback frames
        frame_pattern = re.compile(r'File\s+"([^"]+)",\s+line\s+(\d+),\s+in\s+([a-zA-Z0-9_<>\.]+)$')
        test_pattern = re.compile(r'FAIL:\s+([a-zA-Z0-9_\.]+)|ERROR:\s+([a-zA-Z0-9_\.]+)')

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Check for test name
            test_match = test_pattern.search(line)
            if test_match:
                failing_test = test_match.group(1) or test_match.group(2)

            # Check for stack frame
            frame_match = frame_pattern.search(line)
            if frame_match:
                file_path = frame_match.group(1).replace("\\", "/")
                line_no = int(frame_match.group(2))
                func_name = frame_match.group(3)
                
                # Next line usually contains the code snippet
                code_snippet = ""
                if i + 1 < len(lines) and not lines[i + 1].strip().startswith("File "):
                    code_snippet = lines[i + 1].strip()
                    i += 1

                frames.append({
                    "file": file_path,
                    "line": line_no,
                    "function": func_name,
                    "code_snippet": code_snippet
                })
            i += 1

        # Extract exception from final line (e.g. TypeError: unsupported operand...)
        for line in reversed(lines):
            line_str = line.strip()
            if ":" in line_str and not line_str.startswith("File "):
                parts = line_str.split(":", 1)
                first_part = parts[0].strip()
                if first_part.endswith("Error") or first_part.endswith("Exception") or first_part in ["AssertionError", "TypeError", "ValueError", "KeyError", "IndexError", "ZeroDivisionError", "AttributeError"]:
                    exception_type = first_part
                    exception_message = parts[1].strip()
                    break

        # Failing location is the deepest non-test frame if available, else deepest frame
        failing_location = {}
        suspected_root_cause = {}
        evidence_type = "DIRECT_RUNTIME_TRACE"

        if frames:
            # Deepest frame is where execution halted
            deepest = frames[-1]
            failing_location = {
                "file": deepest["file"],
                "line": deepest["line"],
                "function": deepest["function"],
                "code": deepest["code_snippet"]
            }

            # Filter out frames that are inside unittest/pytest internal runners
            app_frames = [
                f for f in frames
                if "unittest" not in f["file"] and "pytest" not in f["file"] and not f["file"].startswith("<")
            ]
            
            if app_frames:
                target_frame = app_frames[-1]
                suspected_root_cause = {
                    "file": target_frame["file"],
                    "line": target_frame["line"],
                    "function": target_frame["function"],
                    "code": target_frame["code_snippet"]
                }
            else:
                suspected_root_cause = failing_location
        else:
            # Fallback for simple error strings without traceback frames
            failing_location = {
                "file": "unknown",
                "line": 0,
                "function": "unknown",
                "code": ""
            }
            suspected_root_cause = failing_location
            evidence_type = "INFERRED_GRAPH_ANALYSIS"

        return FailureEvidence(
            repository_id=repository_id,
            branch=branch,
            commit_sha=commit_sha,
            indexed_revision=commit_sha,
            failing_test=failing_test,
            test_command=test_command,
            exception_type=exception_type,
            exception_message=exception_message,
            stack_frames=frames,
            failing_location=failing_location,
            suspected_root_cause=suspected_root_cause,
            evidence_type=evidence_type,
            raw_traceback=traceback_text
        )
