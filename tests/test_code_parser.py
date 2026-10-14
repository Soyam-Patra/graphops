"""
Test suite verifying Codebase AST and Git Parser.
"""

import unittest
from src.code_parser import CodebaseParser

class TestCodeParser(unittest.TestCase):
    def test_parse_current_repository(self):
        parser = CodebaseParser(".")
        data = parser.parse_repository()

        self.assertGreater(len(data["files"]), 0)
        self.assertGreater(len(data["functions"]), 0)
        self.assertGreater(len(data["calls"]), 0)
        self.assertGreater(len(data["commits"]), 0)

        # Check function properties
        fn = data["functions"][0]
        self.assertIn("id", fn)
        self.assertIn("name", fn)
        self.assertIn("start_line", fn)

        # Check commit properties
        cm = data["commits"][0]
        self.assertIn("sha", cm)
        self.assertIn("author", cm)
        self.assertIn("message", cm)

        print(f"[OK] Parsed {len(data['files'])} files, {len(data['functions'])} functions, {len(data['calls'])} calls, {len(data['commits'])} commits.")

if __name__ == "__main__":
    unittest.main()
