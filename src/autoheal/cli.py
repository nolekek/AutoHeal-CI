import os
import sys
import argparse
import subprocess
from typing import Optional

from .config import AutoHealConfig
from .parsers.pytest_log_parser import PytestLogParser
from .parsers.ast_slicer import PythonASTSlicer
from .agents.llm_client import LLMClient
from .agents.graph import AutoHealOrchestrator
from .agents.state import AutoHealState

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

    # 1. Obtain test failure log
    if args.log_file and os.path.exists(args.log_file):
        with open(args.log_file, "r", encoding="utf-8") as f:
            raw_log = f.read()
        exit_code = 1
    else:
        exit_code, raw_log = run_local_pytest(config.repo_path, config.test_command)

    if exit_code == 0:
        print("✅ All tests are passing! AutoHeal-CI found 0 issues to fix.")
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
    llm = LLMClient(provider=config.provider, model=config.model, api_key=config.api_key)
    orchestrator = AutoHealOrchestrator(llm_client=llm, repo_path=config.repo_path)

    print("🤖 Starting LangGraph Adversarial Deliberation (Coder vs Red-Team Critic)...")
    final_state = orchestrator.app.invoke(initial_state)

    print(f"\n🏁 Deliberation completed with status: {final_state.get('status')}")
    if final_state.get("status") == "verified":
        print("🎉 SUCCESS! Patch verified by Red-Team Critic and passed 100% regression suite.")
        if final_state.get("pr_url"):
            print(f"🔗 Pull Request Created: {final_state['pr_url']}")
            write_github_summary(f"### 🩺 AutoHeal-CI Fix Verified!\nPull Request: {final_state['pr_url']}")
        return 0
    else:
        print("❌ Could not reach a verified patch within maximum deliberation rounds.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
