"""
Comprehensive Unit Tests for Evidence-Based Diagnosis and Human-Approved Targeted Recovery.
Covers:
1. Extraction of failing function and stack frames from traceback.
2. Candidate commit identification using actual Git diffs.
3. Commit containing both a regression and an unrelated beneficial change.
4. Targeted restoration that preserves the unrelated change.
5. Dirty working-tree / concurrent modification detection.
6. Explicit human approval enforcement before modifying code.
7. Cancellation without modification.
8. Test failure after applying a patch (honest exit code & verified failure).
9. Successful verification and audit recording.
10. Failure to identify a safe targeted fix (flags manual review).
11. Existing sandbox whole-commit revert behavior preservation.
12. Separation of all three FalkorDB graph keyspaces.
"""

import unittest
import os
import shutil
import tempfile
import subprocess
from unittest.mock import patch, MagicMock

from src.failure_analyzer import FailureAnalyzer, FailureEvidence
from src.recovery_engine import (
    TargetedRecoveryEngine,
    RecoverySafetyError,
    DirtyWorkingTreeError,
    StalePatchError
)
from src.sandbox_engine import SandboxEngine
from src.agent_memory import AgentMemoryEngine
from src.code_tools import CodebaseTools
from src.graph_tools import GraphTools

class TestEvidenceBasedRecovery(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = os.path.join(self.temp_dir, "test_repo")
        os.makedirs(os.path.join(self.repo_path, "src"), exist_ok=True)
        os.makedirs(os.path.join(self.repo_path, "tests"), exist_ok=True)

        # Initialize test git repo
        env = os.environ.copy()
        env["GIT_AUTHOR_NAME"] = "TestDev"
        env["GIT_AUTHOR_EMAIL"] = "dev@graphops.dev"
        env["GIT_COMMITTER_NAME"] = "TestDev"
        env["GIT_COMMITTER_EMAIL"] = "dev@graphops.dev"
        self.git_env = env

        subprocess.run(["git", "init"], cwd=self.repo_path, capture_output=True, check=True, env=env)
        subprocess.run(["git", "config", "user.name", "TestDev"], cwd=self.repo_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "dev@graphops.dev"], cwd=self.repo_path, capture_output=True, check=True)

        # Create baseline payment_gateway.py
        self.payment_file = os.path.join(self.repo_path, "src", "payment_gateway.py")
        with open(self.payment_file, "w", encoding="utf-8") as f:
            f.write('''def validate_token(token):
    return bool(token)

def charge_card(card_token, amount):
    if not validate_token(card_token):
        raise ValueError("Invalid token")
    fee = amount * 0.02
    return {"status": "CHARGED", "amount": amount + fee}
''')

        # Baseline test file
        self.test_file = os.path.join(self.repo_path, "tests", "test_payment.py")
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write('''import unittest
from src.payment_gateway import charge_card

class TestPayment(unittest.TestCase):
    def test_charge_success(self):
        res = charge_card("token123", 100.0)
        self.assertEqual(res["status"], "CHARGED")
        self.assertEqual(res["amount"], 102.0)
''')

        subprocess.run(["git", "add", "."], cwd=self.repo_path, capture_output=True, check=True, env=env)
        subprocess.run(["git", "commit", "-m", "chore: baseline working commit"], cwd=self.repo_path, capture_output=True, check=True, env=env)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. Traceback Extraction Test
    def test_traceback_failure_extraction(self):
        tb_text = """Traceback (most recent call last):
  File "D:\\FalkorDB\\sandbox_repo\\tests\\test_payment.py", line 14, in test_charge_card_success
    receipt = charge_card("tok_valid_visa", 100.0)
  File "D:\\FalkorDB\\sandbox_repo\\src\\payment_gateway.py", line 239, in charge_card
    fee = amount * fee_multiplier
TypeError: unsupported operand type(s) for *: 'float' and 'NoneType'
"""
        evidence = FailureAnalyzer.parse_traceback(tb_text, repository_id="test_repo", test_command="pytest")
        self.assertEqual(evidence.exception_type, "TypeError")
        self.assertIn("unsupported operand", evidence.exception_message)
        self.assertEqual(evidence.failing_location["function"], "charge_card")
        self.assertEqual(evidence.failing_location["line"], 239)
        self.assertEqual(evidence.suspected_root_cause["function"], "charge_card")
        self.assertEqual(evidence.evidence_type, "DIRECT_RUNTIME_TRACE")
        self.assertIn("Do not treat a function's presence", evidence.to_dict()["caveat"])

    # 2. Candidate Commit Identification Test
    def test_candidate_commit_identification(self):
        with open(self.payment_file, "w", encoding="utf-8") as f:
            f.write('''def validate_token(token):
    return bool(token)

def charge_card(card_token, amount):
    if not validate_token(card_token):
        raise ValueError("Invalid token")
    fee_multiplier = None
    fee = amount * fee_multiplier
    return {"status": "CHARGED", "amount": amount + fee}
''')
        subprocess.run(["git", "add", "."], cwd=self.repo_path, capture_output=True, check=True, env=self.git_env)
        subprocess.run(["git", "commit", "-m", "feat: breaking change in charge_card"], cwd=self.repo_path, capture_output=True, check=True, env=self.git_env)

        engine = TargetedRecoveryEngine()
        candidates = engine.identify_candidate_commits(self.repo_path, "src/payment_gateway.py", "charge_card")
        self.assertTrue(len(candidates) >= 1)
        top = candidates[0]
        self.assertTrue(top["touches_suspected_function"])
        self.assertEqual(top["confidence"], "HIGH")
        self.assertIn("def charge_card", top["relevant_diff_hunk"])

    # 3 & 4. Commit with Both Regression and Unrelated Feature & Targeted Restoration
    def test_targeted_restoration_preserves_unrelated_feature(self):
        with open(self.payment_file, "w", encoding="utf-8") as f:
            f.write('''def validate_token(token):
    return bool(token)

def charge_card(card_token, amount):
    if not validate_token(card_token):
        raise ValueError("Invalid token")
    # [FEATURE: Structured payment audit logger]
    print(f"[AUDIT] Processing card charge for token {card_token[:4]}**** with amount {amount}")
    # [REGRESSION: fee_multiplier is uninitialized None]
    fee_multiplier = None
    fee = amount * fee_multiplier
    return {"status": "CHARGED", "amount": amount + fee}
''')
        subprocess.run(["git", "add", "."], cwd=self.repo_path, capture_output=True, check=True, env=self.git_env)
        subprocess.run(["git", "commit", "-m", "feat: add audit logging and dynamic fee"], cwd=self.repo_path, capture_output=True, check=True, env=self.git_env)

        engine = TargetedRecoveryEngine()
        candidates = engine.identify_candidate_commits(self.repo_path, "src/payment_gateway.py", "charge_card")
        candidate = candidates[0]

        evidence = FailureAnalyzer.parse_traceback("TypeError: unsupported operand type(s) for *: 'float' and 'NoneType'")
        patch_data = engine.generate_targeted_patch(self.repo_path, "src/payment_gateway.py", "charge_card", candidate, evidence)

        self.assertTrue(patch_data["safe_to_apply"])
        self.assertIn("fee_multiplier = 0.02", patch_data["unified_diff"])
        self.assertTrue(any("audit" in f.lower() for f in patch_data["unrelated_features_preserved"]))

        # Apply targeted patch with human approval
        res = engine.apply_targeted_patch_safely(
            repo_path=self.repo_path,
            patch_data=patch_data,
            human_approved=True,
            approver="Soyam",
            run_verification=True
        )

        self.assertTrue(res["tests_passed"])
        self.assertEqual(res["exit_code"], 0)

        # Ensure [AUDIT] logging was NOT wiped out!
        with open(self.payment_file, "r", encoding="utf-8") as f:
            final_code = f.read()
            self.assertIn("[AUDIT] Processing card charge", final_code)
            self.assertIn("fee_multiplier = 0.02", final_code)

    # 5. Dirty Working-Tree / Concurrent Change Detection
    def test_dirty_working_tree_rejection(self):
        engine = TargetedRecoveryEngine()
        patch_data = {
            "affected_file": "src/payment_gateway.py",
            "affected_function": "charge_card",
            "unified_diff": "--- a/src/payment_gateway.py\n+++ b/src/payment_gateway.py",
            "candidate_commit_sha": "HEAD",
            "reject_on_dirty": True
        }

        with open(self.payment_file, "a", encoding="utf-8") as f:
            f.write("\n# Uncommitted developer scratchpad\n")

        with self.assertRaises(DirtyWorkingTreeError):
            engine.apply_targeted_patch_safely(
                repo_path=self.repo_path,
                patch_data=patch_data,
                human_approved=True,
                approver="Soyam"
            )

    # 6. Explicit Human Approval Required
    def test_approval_required_enforcement(self):
        engine = TargetedRecoveryEngine()
        patch_data = {
            "affected_file": "src/payment_gateway.py",
            "affected_function": "charge_card",
            "unified_diff": "--- a/src/payment_gateway.py\n+++ b/src/payment_gateway.py"
        }

        with self.assertRaises(RecoverySafetyError) as ctx:
            engine.apply_targeted_patch_safely(
                repo_path=self.repo_path,
                patch_data=patch_data,
                human_approved=False,
                approver="Soyam"
            )
        self.assertIn("Human approval required", str(ctx.exception))

    # 7. Cancellation Without Modification
    def test_cancellation_leaves_working_tree_untouched(self):
        with open(self.payment_file, "r", encoding="utf-8") as f:
            before_content = f.read()

        engine = TargetedRecoveryEngine()
        cancel_res = engine.cancel_proposal(ticket_id="TICKET-TEST-001", reason="Developer declined")

        self.assertEqual(cancel_res["status"], "CANCELLED")
        self.assertFalse(cancel_res["working_tree_modified"])

        with open(self.payment_file, "r", encoding="utf-8") as f:
            after_content = f.read()
        self.assertEqual(before_content, after_content)

    # 8. Test Failure After Applying Patch Reports Failure Honestly
    def test_verification_failure_reported_honestly(self):
        engine = TargetedRecoveryEngine()
        patch_data = {
            "affected_file": "src/payment_gateway.py",
            "affected_function": "charge_card",
            "unified_diff": "- dummy\n+ dummy",
            "reject_on_dirty": False
        }

        res = engine.apply_targeted_patch_safely(
            repo_path=self.repo_path,
            patch_data=patch_data,
            human_approved=True,
            approver="Soyam",
            run_verification=True,
            test_command="python -c sys.exit(1)"
        )

        self.assertFalse(res["tests_passed"])
        self.assertEqual(res["status"], "VERIFICATION_FAILED")
        self.assertEqual(res["exit_code"], 1)

    # 9. Failure to Identify Safe Targeted Fix Flags Manual Review
    def test_ambiguous_failure_flags_manual_review(self):
        engine = TargetedRecoveryEngine()
        patch_data = engine.generate_targeted_patch(
            repo_path=self.repo_path,
            suspected_file="src/payment_gateway.py",
            suspected_function="non_existent_function",
            candidate_commit={"sha": "HEAD"}
        )
        self.assertFalse(patch_data["safe_to_apply"])
        self.assertTrue(patch_data["requires_manual_review"])
        self.assertIn("MANUAL_REVIEW_REQUIRED", patch_data["reason"])

    # 10. Existing Sandbox Whole-Commit Revert Behavior Preserved
    def test_sandbox_whole_commit_revert_preserved(self):
        se = SandboxEngine()
        init_res = se.init_sandbox(force=True)
        self.assertEqual(init_res["status"], "INITIALIZED_CLEAN")
        self.assertTrue(init_res.get("baseline_tests_passed", True))

        inj_res = se.inject_regression()
        self.assertEqual(inj_res["status"], "REGRESSION_ACTIVE")
        self.assertEqual(inj_res["exit_code"], 1)

        rev_res = se.execute_revert_and_verify()
        self.assertEqual(rev_res["status"], "VERIFIED_PASSING")
        self.assertEqual(rev_res["exit_code"], 0)
        self.assertTrue(rev_res["test_passed"])

    # 11. Sandbox Mixed Regression & Targeted Fix Verification
    def test_sandbox_targeted_fix_workflow(self):
        se = SandboxEngine()
        se.init_sandbox(force=True)

        inj = se.inject_mixed_regression()
        self.assertEqual(inj["status"], "MIXED_REGRESSION_ACTIVE")
        self.assertIn("Structured payment audit logger", inj["unrelated_feature"])
        self.assertEqual(inj["exit_code"], 1)

        proposal = se.propose_targeted_fix()
        self.assertEqual(proposal["status"], "PROPOSED")
        self.assertTrue(proposal["safe_to_apply"])

        ver = se.apply_targeted_fix_and_verify(approver="Soyam")
        self.assertEqual(ver["status"], "VERIFIED_PASSING")
        self.assertEqual(ver["exit_code"], 0)
        self.assertTrue(ver["audit_logging_preserved"])

    # 12. Separation of All Three FalkorDB Graph Keyspaces
    def test_falkordb_keyspaces_separation(self):
        cb_tools = CodebaseTools(graph_name="codebase_graph")
        mem_engine = AgentMemoryEngine(memory_graph="agent_memory_swarm")
        company_tools = GraphTools(graph_name="company_brain")

        self.assertEqual(cb_tools.graph_name, "codebase_graph")
        self.assertEqual(mem_engine.memory_graph, "agent_memory_swarm")
        self.assertEqual(company_tools.graph_name, "company_brain")
        self.assertNotEqual(cb_tools.graph_name, mem_engine.memory_graph)
        self.assertNotEqual(cb_tools.graph_name, company_tools.graph_name)

if __name__ == "__main__":
    unittest.main()
