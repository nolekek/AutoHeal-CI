import os
import sys
import argparse
import subprocess
from typing import Optional

from .config import AutoHealConfig
from .parsers.pytest_log_parser import PytestLogParser
from .parsers.ast_slicer import PythonASTSlicer
from .parsers.dependency_healer import DependencyHealer
from .agents.llm_client import LLMClient
from .agents.graph import AutoHealOrchestrator
from .agents.state import AutoHealState
from .delivery.step_summary import StepSummaryGenerator
from .delivery.patch_artifact import PatchArtifactExporter
from .delivery.webhook_notifier import WebhookNotifier
from .licensing import LicenseManager

def print_banner():
    banner = r"""
  ╔═══════════════════════════════════════════════════════╗
  ║    🩺 AutoHeal-CI: Autonomous CI/CD Self-Healing      ║
  ║  AST Slicing • Adversarial Red-Team • Regression Shield║
  ╚═══════════════════════════════════════════════════════╝
"""
    print(banner)

def run_local_pytest(repo_path: str, test_cmd: str) -> tuple[int, str]:
    """Runs the initial test command to capture the failure log."""
    print(f"🔍 Running test suite with command: '{test_cmd}'...")
    parts = test_cmd.split()
    if parts and parts[0] in ("pytest", "py.test"):
        parts = [sys.executable, "-m", "pytest"] + parts[1:]
    try:
        proc = subprocess.run(
            parts,
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        return proc.returncode, output
    except Exception as e:
        return 1, f"Failed to execute test command: {str(e)}"

def set_github_output(name: str, value: str):
    """Sets a step output parameter in GitHub Actions via $GITHUB_OUTPUT."""
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "a", encoding="utf-8") as f:
            if "\n" in value:
                import uuid
                delimiter = f"ghadelimiter_{uuid.uuid4().hex}"
                f.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                f.write(f"{name}={value}\n")
    except Exception:
        pass

def write_github_summary(content: str):
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path and os.path.exists(os.path.dirname(summary_path)):
        try:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(content + "\n")
        except Exception:
            pass

def main():
    print_banner()
    parser = argparse.ArgumentParser(description="AutoHeal-CI Autonomous Self-Healing Bot")
    parser.add_argument("--log-file", type=str, help="Path to existing pytest failure log file")
    parser.add_argument("--repo-path", type=str, default=".", help="Path to repository root")
    parser.add_argument("--dry-run", action="store_true", help="Run without pushing git PR")
    args = parser.parse_args()

    config = AutoHealConfig(repo_path=os.path.abspath(args.repo_path))
    license_info = LicenseManager.validate_key(config.license_key)
    print(f"💎 {LicenseManager.format_badge(license_info)}")

    # 1. Obtain test failure log
    if args.log_file and os.path.exists(args.log_file):
        with open(args.log_file, "r", encoding="utf-8") as f:
            raw_log = f.read()
        exit_code = 1
    else:
        exit_code, raw_log = run_local_pytest(config.repo_path, config.test_command)

    if exit_code == 0:
        print("✅ All tests are passing! AutoHeal-CI found 0 issues to fix.")
        set_github_output("fixed", "true")
        set_github_output("pr_url", "")
        set_github_output("patch_diff", "")
        set_github_output("patch_path", "")
        return 0

    print("❌ Test failures detected in CI pipeline. Commencing AST localization...")

    # 2. Parse pytest log
    failures = PytestLogParser.parse(raw_log)
    if not failures:
        print("⚠️ Could not extract structured test failures from log.")
        return 1

    failure = failures[0]
    print(f"🎯 Target failure located: {failure.test_id}")
    print(f"   Origin: {failure.failing_file}:{failure.failing_line} ({failure.exception_type}: {failure.exception_message})")

    # 2.5 Pre-flight check: MISSING_DEPENDENCY auto-healer
    if failure.failure_mode == "MISSING_DEPENDENCY" and failure.missing_package:
        print(f"📦 Pre-Flight Classifier: Detected missing dependency '{failure.missing_package}'.")
        print("🔧 Attempting automatic healing via DependencyHealer...")
        if DependencyHealer.heal_failure(config.repo_path, failure):
            print(f"✅ Successfully added '{failure.missing_package}' to pyproject.toml.")
            healed_state = {
                "status": "dependency_healed",
                "failing_file": failure.failing_file,
                "failing_line": failure.failing_line,
                "failing_symbol_name": failure.missing_package,
                "exception_type": failure.exception_type,
                "exception_message": failure.exception_message,
                "missing_package": failure.missing_package,
                "round_count": 0,
                "max_rounds": config.max_rounds,
            }
            StepSummaryGenerator(state=healed_state, model=config.model).write_to_github_summary()
            set_github_output("fixed", "true")
            set_github_output("pr_url", "")
            set_github_output("patch_diff", "")
            set_github_output("patch_path", "")
            return 0
        else:
            print("⚠️ DependencyHealer could not patch pyproject.toml. Proceeding to deliberation...")

    # 3. Perform Tree-sitter AST slicing
    slicer = PythonASTSlicer()
    full_failing_path = os.path.join(config.repo_path, failure.failing_file)
    symbol_slice = slicer.slice_at_line(full_failing_path, failure.failing_line)

    full_test_path = os.path.join(config.repo_path, failure.test_file)
    test_slice = slicer.slice_function_by_name(full_test_path, failure.test_id.split("::")[-1])

    ast_code = symbol_slice.code if symbol_slice else f"# At {failure.failing_file}:{failure.failing_line}"
    test_code = test_slice.code if test_slice else "# Test code"
    surrounding_signatures = "\n".join(symbol_slice.neighboring_signatures) if symbol_slice else ""
    symbol_name = symbol_slice.symbol_name if symbol_slice else "unknown"

    print(f"🔬 AST Slicing completed. Symbol: `{symbol_name}` ({len(ast_code)} chars context)")

    # 4. Initialize Multi-Agent LangGraph State
    initial_state: AutoHealState = {
        "repo_path": config.repo_path,
        "target_branch": os.getenv("GITHUB_REF_NAME", "main"),
        "commit_sha": os.getenv("GITHUB_SHA", "HEAD"),
        "raw_error_log": failure.raw_traceback,
        "failing_file": failure.failing_file,
        "failing_line": failure.failing_line,
        "failing_symbol_name": symbol_name,
        "failing_test_file": failure.test_file,
        "failing_test_name": failure.test_id,
        "ast_symbol_slice": ast_code,
        "ast_test_slice": test_code,
        "ast_surrounding_signatures": surrounding_signatures,
        "exception_type": failure.exception_type,
        "exception_message": failure.exception_message,
        "round_count": 0,
        "max_rounds": config.max_rounds,
        "coder_hypothesis": None,
        "patch_diff": None,
        "patched_file_content": None,
        "failing_test_resolved": False,
        "critic_attack_code": None,
        "critic_critique": None,
        "critic_test_passed": False,
        "regression_suite_passed": False,
        "test_feedback": "",
        "status": "in_progress",
        "pr_url": None,
        "error_message": None
    }

    # 5. Execute LangGraph Orchestrator
    llm = LLMClient(
        provider=config.provider,
        model=config.model,
        api_key=config.api_key,
        max_budget_usd=config.max_budget_usd
    )
    orchestrator = AutoHealOrchestrator(llm_client=llm, repo_path=config.repo_path)

    print("🤖 Starting LangGraph Adversarial Deliberation (Coder vs Red-Team Critic)...")
    final_state = orchestrator.app.invoke(initial_state)

    print(f"\n🏁 Deliberation completed with status: {final_state.get('status')}")
    usage = llm.get_usage()
    patch_path = final_state.get("patch_path")

    if final_state.get("status") == "verified":
        print("🎉 SUCCESS! Patch verified by Red-Team Critic and passed 100% regression suite.")
        if final_state.get("pr_url"):
            print(f"🔗 Pull Request Created: {final_state['pr_url']}")
        else:
            if not patch_path and final_state.get("patch_diff"):
                exporter = PatchArtifactExporter(repo_path=config.repo_path)
                patch_path = exporter.export_from_state(final_state)
            if patch_path:
                print(f"📦 Fallback patch artifact generated at: {patch_path}")
                print(PatchArtifactExporter(config.repo_path).get_apply_instructions(patch_path))

        summary_gen = StepSummaryGenerator(
            state=final_state,
            usage=usage,
            patch_path=patch_path,
            model=config.model,
            license_info=license_info
        )
        summary_gen.write_to_github_summary()

        if config.webhook_url:
            WebhookNotifier(config.webhook_url).send_notification(
                fixed=True,
                pr_url=final_state.get("pr_url"),
                patch_path=patch_path,
                cost_usd=usage.get("total_cost_usd", 0.0),
                rounds=final_state.get("round_count", 1),
                repo=os.getenv("GITHUB_REPOSITORY", os.path.basename(config.repo_path)),
                branch=os.getenv("GITHUB_REF_NAME", "main"),
                failure_mode=final_state.get("failure_mode")
            )

        set_github_output("fixed", "true")
        set_github_output("pr_url", final_state.get("pr_url") or "")
        set_github_output("patch_diff", final_state.get("patch_diff") or "")
        set_github_output("patch_path", patch_path or "")
        return 0
    else:
        print("❌ Could not reach a verified patch within maximum deliberation rounds.")
        summary_gen = StepSummaryGenerator(
            state=final_state,
            usage=usage,
            patch_path=patch_path,
            model=config.model,
            license_info=license_info
        )
        summary_gen.write_to_github_summary()

        if config.webhook_url:
            WebhookNotifier(config.webhook_url).send_notification(
                fixed=False,
                pr_url=None,
                patch_path=patch_path,
                cost_usd=usage.get("total_cost_usd", 0.0),
                rounds=final_state.get("round_count", 1),
                repo=os.getenv("GITHUB_REPOSITORY", os.path.basename(config.repo_path)),
                branch=os.getenv("GITHUB_REF_NAME", "main"),
                failure_mode=final_state.get("failure_mode")
            )

        set_github_output("fixed", "false")
        set_github_output("pr_url", "")
        set_github_output("patch_diff", final_state.get("patch_diff") or "")
        set_github_output("patch_path", patch_path or "")
        return 1

if __name__ == "__main__":
    sys.exit(main())
