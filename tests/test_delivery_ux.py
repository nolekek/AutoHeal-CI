import os
import shutil
import tempfile
import yaml
import pytest
from typing import Dict, Any

from autoheal.delivery.patch_artifact import PatchArtifactExporter, DEFAULT_PATCH_DIR, DEFAULT_PATCH_FILENAME
from autoheal.delivery.step_summary import StepSummaryGenerator, write_step_summary
from autoheal.cli import set_github_output
from autoheal.agents.state import AutoHealState


SAMPLE_DIFF = """--- a/src/math_utils.py
+++ b/src/math_utils.py
@@ -10,7 +10,7 @@ def divide(a: int, b: int) -> float:
-    return a / b
+    if b == 0:
+        return 0.0
+    return a / b
"""

SAMPLE_ATTACK_TEST = """def test_divide_zero_attack():
    from src.math_utils import divide
    assert divide(10, 0) == 0.0
    assert divide(-5, 0) == 0.0
"""


@pytest.fixture
def temp_repo():
    path = tempfile.mkdtemp(prefix="autoheal_test_repo_")
    yield path
    shutil.rmtree(path, ignore_errors=True)


# ============================================================================
# 1. PatchArtifactExporter Tests
# ============================================================================

def test_patch_export_creates_directory_and_file(temp_repo):
    exporter = PatchArtifactExporter(repo_path=temp_repo)
    exported_path = exporter.export(SAMPLE_DIFF)

    expected_file = os.path.join(temp_repo, DEFAULT_PATCH_DIR, DEFAULT_PATCH_FILENAME)
    assert os.path.isfile(expected_file)
    assert exported_path == f"{DEFAULT_PATCH_DIR}/{DEFAULT_PATCH_FILENAME}"

    with open(expected_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert "--- a/src/math_utils.py" in content
    assert "+        return 0.0" in content


def test_patch_export_custom_filename_and_output_path(temp_repo):
    exporter = PatchArtifactExporter(repo_path=temp_repo)
    custom_dest = os.path.join(temp_repo, "custom_patches", "fix-123.patch")

    result = exporter.export(SAMPLE_DIFF, output_path=custom_dest)
    assert os.path.isfile(custom_dest)
    assert result == "custom_patches/fix-123.patch"


def test_patch_export_empty_diff_raises_error(temp_repo):
    exporter = PatchArtifactExporter(repo_path=temp_repo)
    with pytest.raises(ValueError, match="Cannot export empty patch diff"):
        exporter.export("")

    with pytest.raises(ValueError, match="Cannot export empty patch diff"):
        exporter.export("   \n\t  ")


def test_patch_export_from_state_success(temp_repo):
    state: AutoHealState = {
        "repo_path": temp_repo,
        "target_branch": "main",
        "commit_sha": "abc1234",
        "raw_error_log": "ZeroDivisionError",
        "failing_file": "src/math_utils.py",
        "failing_line": 10,
        "failing_symbol_name": "divide",
        "failing_test_file": "tests/test_math.py",
        "failing_test_name": "test_divide",
        "ast_symbol_slice": "def divide(a, b): return a / b",
        "ast_test_slice": "def test_divide(): divide(1, 0)",
        "ast_surrounding_signatures": "",
        "exception_type": "ZeroDivisionError",
        "exception_message": "division by zero",
        "round_count": 1,
        "max_rounds": 3,
        "coder_hypothesis": "Guard against zero divisor",
        "patch_diff": SAMPLE_DIFF,
        "patched_file_content": "def divide(a, b):\n    if b == 0: return 0.0\n    return a / b",
        "failing_test_resolved": True,
        "critic_attack_code": SAMPLE_ATTACK_TEST,
        "critic_critique": "Approved",
        "critic_test_passed": True,
        "regression_suite_passed": True,
        "test_feedback": "",
        "status": "verified",
        "pr_url": None,
        "patch_path": None,
        "error_message": None,
    }

    exporter = PatchArtifactExporter(repo_path=temp_repo)
    patch_path = exporter.export_from_state(state)

    assert patch_path == f"{DEFAULT_PATCH_DIR}/{DEFAULT_PATCH_FILENAME}"
    full_path = os.path.join(temp_repo, DEFAULT_PATCH_DIR, DEFAULT_PATCH_FILENAME)
    assert os.path.isfile(full_path)


def test_patch_export_from_state_no_diff_returns_none(temp_repo):
    state: AutoHealState = {
        "repo_path": temp_repo,
        "patch_diff": None,
    }  # type: ignore

    exporter = PatchArtifactExporter(repo_path=temp_repo)
    result = exporter.export_from_state(state)
    assert result is None


def test_patch_instructions_include_curl_and_git_apply(temp_repo):
    exporter = PatchArtifactExporter(repo_path=temp_repo)
    instructions = exporter.get_apply_instructions(
        patch_path=".autoheal/autoheal-fix.patch",
        patch_url="https://api.github.com/repos/org/repo/actions/artifacts/123/zip"
    )

    assert "git apply .autoheal/autoheal-fix.patch" in instructions
    assert "curl -sL" in instructions
    assert "| git apply" in instructions

    md = exporter.get_instructions_markdown()
    assert "curl -sL" in md
    assert "git apply" in md


# ============================================================================
# 2. StepSummaryGenerator Tests
# ============================================================================

def test_step_summary_mermaid_diagram():
    generator = StepSummaryGenerator()
    diagram = generator.generate_mermaid_diagram()

    assert "```mermaid" in diagram
    assert "stateDiagram-v2" in diagram
    assert "Coder_Agent" in diagram
    assert "Critic_Agent" in diagram
    assert "Sandbox_Patch_Verification" in diagram
    assert "Critic_Attack_Verification" in diagram
    assert "Regression_Shield" in diagram
    assert "Delivery_UX" in diagram
    assert "```" in diagram


def test_step_summary_collapsible_diff_preview():
    state = {"patch_diff": SAMPLE_DIFF}
    generator = StepSummaryGenerator(state=state)  # type: ignore
    diff_block = generator.generate_diff_preview()

    assert "<details>" in diff_block
    assert "<summary>🔍 Unified Diff Preview</summary>" in diff_block
    assert "```diff" in diff_block
    assert "--- a/src/math_utils.py" in diff_block
    assert "+    if b == 0:" in diff_block
    assert "</details>" in diff_block


def test_step_summary_collapsible_diff_preview_fallback():
    generator = StepSummaryGenerator(state={})
    diff_block = generator.generate_diff_preview()

    assert "<details>" in diff_block
    assert "<summary>🔍 Unified Diff Preview</summary>" in diff_block
    assert "_No unified diff generated._" in diff_block
    assert "</details>" in diff_block


def test_step_summary_token_usage_table():
    usage = {
        "prompt_tokens": 1500,
        "completion_tokens": 420,
        "total_tokens": 1920,
        "total_cost_usd": 0.00795,
        "max_budget_usd": 2.0,
    }
    generator = StepSummaryGenerator(usage=usage, model="gpt-4o")
    table = generator.generate_token_usage_table()

    assert "| Deliberation Metric | Count / Amount |" in table
    assert "`gpt-4o`" in table
    assert "`1,500`" in table
    assert "`420`" in table
    assert "`1,920`" in table
    assert "$0.007950" in table
    assert "$2.0000 USD" in table
    assert "Within Budget Cap" in table


def test_step_summary_token_usage_table_budget_exceeded():
    usage = {
        "prompt_tokens": 200000,
        "completion_tokens": 50000,
        "total_tokens": 250000,
        "total_cost_usd": 1.05,
        "max_budget_usd": 1.00,
    }
    generator = StepSummaryGenerator(usage=usage)
    table = generator.generate_token_usage_table()

    assert "⚠️ Budget Cap Reached" in table


def test_full_step_summary_verified_with_pr():
    state: AutoHealState = {
        "failing_symbol_name": "compute_total",
        "failing_file": "src/billing.py",
        "failing_line": 42,
        "exception_type": "ValueError",
        "exception_message": "Negative total calculation",
        "coder_hypothesis": "Enforce minimum total of zero.",
        "round_count": 2,
        "max_rounds": 3,
        "patch_diff": SAMPLE_DIFF,
        "critic_attack_code": SAMPLE_ATTACK_TEST,
        "regression_suite_passed": True,
        "status": "verified",
        "pr_url": "https://github.com/auto-heal-ci/demo/pull/42",
        "patch_path": None,
    }  # type: ignore

    generator = StepSummaryGenerator(state=state)
    summary = generator.generate_summary()

    # Outcome check
    assert "AutoHeal-CI Fix Verified & PR Created! 🎉" in summary
    assert "https://github.com/auto-heal-ci/demo/pull/42" in summary

    # Failure context
    assert "`compute_total`" in summary
    assert "`src/billing.py:42`" in summary
    assert "ValueError: Negative total calculation" in summary

    # Mermaid diagram
    assert "```mermaid" in summary
    assert "stateDiagram-v2" in summary

    # Collapsible diff
    assert "<summary>🔍 Unified Diff Preview</summary>" in summary

    # Red-Team Critic edge-case test
    assert "<summary>🛡️ Red-Team Critic Edge-Case Counter-Test</summary>" in summary
    assert "def test_divide_zero_attack():" in summary

    # Token table
    assert "| Deliberation Metric | Count / Amount |" in summary


def test_full_step_summary_fallback_patch_when_no_pr():
    state: AutoHealState = {
        "failing_symbol_name": "format_date",
        "failing_file": "src/date_utils.py",
        "failing_line": 15,
        "exception_type": "TypeError",
        "exception_message": "invalid format",
        "coder_hypothesis": "Handle None date string safely.",
        "round_count": 1,
        "max_rounds": 3,
        "patch_diff": SAMPLE_DIFF,
        "regression_suite_passed": True,
        "status": "verified",
        "pr_url": None,
        "patch_path": ".autoheal/autoheal-fix.patch",
    }  # type: ignore

    generator = StepSummaryGenerator(state=state, patch_path=".autoheal/autoheal-fix.patch")
    summary = generator.generate_summary()

    assert "Fallback Patch Exported" in summary
    assert "`.autoheal/autoheal-fix.patch`" in summary
    assert "curl -sL" in summary
    assert "| git apply" in summary
    assert "git apply .autoheal/autoheal-fix.patch" in summary


def test_full_step_summary_failed_deliberation():
    state: AutoHealState = {
        "failing_symbol_name": "complex_calc",
        "failing_file": "src/calc.py",
        "failing_line": 99,
        "exception_type": "RuntimeError",
        "exception_message": "Deadlock detected",
        "coder_hypothesis": "Attempted lock release",
        "round_count": 3,
        "max_rounds": 3,
        "patch_diff": None,
        "regression_suite_passed": False,
        "status": "failed_max_rounds",
        "pr_url": None,
        "patch_path": None,
    }  # type: ignore

    generator = StepSummaryGenerator(state=state)
    summary = generator.generate_summary()

    assert "Fix Not Verified" in summary
    assert "Verification Incomplete" in summary
    assert "_No unified diff generated._" in summary


def test_write_to_github_summary_file(temp_repo, monkeypatch):
    summary_file = os.path.join(temp_repo, "step_summary.md")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", summary_file)

    state: AutoHealState = {
        "status": "verified",
        "pr_url": "https://github.com/test/repo/pull/1",
        "patch_diff": SAMPLE_DIFF,
    }  # type: ignore

    generator = StepSummaryGenerator(state=state)
    success = generator.write_to_github_summary()

    assert success is True
    assert os.path.isfile(summary_file)
    with open(summary_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "AutoHeal-CI Fix Verified" in content
    assert "<summary>🔍 Unified Diff Preview</summary>" in content


def test_write_step_summary_convenience_function(temp_repo):
    dest = os.path.join(temp_repo, "convenience_summary.md")
    state: AutoHealState = {
        "status": "verified",
        "patch_diff": SAMPLE_DIFF,
        "patch_path": ".autoheal/autoheal-fix.patch",
    }  # type: ignore

    summary_text = write_step_summary(state=state, patch_path=".autoheal/autoheal-fix.patch", summary_path=dest)
    assert os.path.isfile(dest)
    assert "Fallback Patch Exported" in summary_text
    assert "<summary>🔍 Unified Diff Preview</summary>" in summary_text


# ============================================================================
# 3. Action.yml Configuration & Step Outputs Wiring Tests
# ============================================================================

def test_action_yml_structure_and_output_wiring():
    action_path = os.path.join(os.path.dirname(__file__), "..", "action.yml")
    assert os.path.isfile(action_path)

    with open(action_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data.get("name") == "AutoHeal-CI"
    assert data.get("runs", {}).get("using") == "composite"

    # Verify outputs are properly wired up to the composite step id
    outputs = data.get("outputs", {})
    assert "fixed" in outputs
    assert outputs["fixed"]["value"] == "${{ steps.autoheal.outputs.fixed }}"

    assert "pr_url" in outputs
    assert outputs["pr_url"]["value"] == "${{ steps.autoheal.outputs.pr_url }}"

    assert "patch_diff" in outputs
    assert outputs["patch_diff"]["value"] == "${{ steps.autoheal.outputs.patch_diff }}"

    assert "patch_path" in outputs
    assert outputs["patch_path"]["value"] == "${{ steps.autoheal.outputs.patch_path }}"

    # Verify steps have the matching id
    steps = data.get("runs", {}).get("steps", [])
    step_ids = [s.get("id") for s in steps]
    assert "autoheal" in step_ids


# ============================================================================
# 4. GITHUB_OUTPUT Writer Tests
# ============================================================================

def test_set_github_output_single_and_multiline(temp_repo, monkeypatch):
    out_file = os.path.join(temp_repo, "github_outputs.txt")
    monkeypatch.setenv("GITHUB_OUTPUT", out_file)

    set_github_output("fixed", "true")
    set_github_output("pr_url", "https://github.com/org/repo/pull/99")
    set_github_output("patch_diff", SAMPLE_DIFF)
    set_github_output("patch_path", ".autoheal/autoheal-fix.patch")

    assert os.path.isfile(out_file)
    with open(out_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert "fixed=true\n" in content
    assert "pr_url=https://github.com/org/repo/pull/99\n" in content
    assert "patch_path=.autoheal/autoheal-fix.patch\n" in content
    assert "patch_diff<<ghadelimiter_" in content
    assert "--- a/src/math_utils.py" in content
