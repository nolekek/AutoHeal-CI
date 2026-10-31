import os
import sys
import time
import json
import shutil
import tempfile
from typing import Optional, List, Dict, Any, Union, Tuple, Callable

from .models import BenchmarkCase, BenchmarkResult, BenchmarkSuiteReport
from .scenarios import get_all_scenarios, get_scenario, ALL_SCENARIOS
from ..parsers.ast_slicer import PythonASTSlicer, ASTSliceResult
from ..agents.llm_client import LLMClient
from ..agents.graph import AutoHealOrchestrator
from ..agents.state import AutoHealState

class BenchmarkMockLLMClient(LLMClient):
    """
    Deterministic Mock LLM client simulating Coder and Critic agents for benchmark runs.
    Allows SWE-Bench mini-harness to run isolated verification cycles without live LLM API keys.
    """
    def __init__(self, should_fail_critic_rounds: int = 0):
        super().__init__(provider="mock", model="benchmark-mock", api_key="mock-key")
        self.critic_rejections_remaining = should_fail_critic_rounds
        self.call_history: List[Dict[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        self.call_history.append({"system": system_prompt, "user": user_prompt})

        if "Lead Coder Agent" in system_prompt:
            matched_case = self._find_matching_scenario(user_prompt)
            if matched_case:
                payload = {
                    "hypothesis": f"Fix verified for {matched_case.name}: {matched_case.bug_description}",
                    "revised_code": matched_case.expected_fixed_code.strip(),
                    "explanation": f"Automated patch addressing {matched_case.category} edge case."
                }
                return json.dumps(payload)
            else:
                return json.dumps({
                    "hypothesis": "Generic fallback patch",
                    "revised_code": "# Fallback code\n",
                    "explanation": "No matching scenario found"
                })

        elif "Red-Team Critic Agent" in system_prompt:
            if self.critic_rejections_remaining > 0:
                self.critic_rejections_remaining -= 1
                return json.dumps({
                    "is_approved": False,
                    "critique": "Simulated rejection for multi-round benchmark validation.",
                    "attack_test_code": "def test_simulated_critic_attack():\n    assert False, 'Simulated critic failure'\n"
                })
            return json.dumps({
                "is_approved": True,
                "critique": "Approved. The patch resolves the issue and introduces no regressions.",
                "attack_test_code": None
            })

        return "OK"

    def _find_matching_scenario(self, prompt: str) -> Optional[BenchmarkCase]:
        for case in get_all_scenarios():
            if case.failing_symbol_name and case.failing_symbol_name in prompt:
                return case
            if case.id in prompt:
                return case
            if case.name in prompt:
                return case
        return None


class BenchmarkRunner:
    """Executes AutoHeal AST slicer and Mock/Live Orchestrator against SWE-Bench scenarios."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        use_mock: bool = True,
        max_rounds: int = 3,
        verbose: bool = False,
        orchestrator_factory: Optional[Callable[[str], AutoHealOrchestrator]] = None
    ):
        self.use_mock = use_mock
        self.llm_client = llm_client
        self.max_rounds = max_rounds
        self.verbose = verbose
        self.orchestrator_factory = orchestrator_factory
        self.slicer = PythonASTSlicer()

    def _get_llm_client(self) -> LLMClient:
        if self.llm_client:
            return self.llm_client
        return BenchmarkMockLLMClient()

    def verify_ast_slicing(self, case: BenchmarkCase, repo_dir: Optional[str] = None) -> Tuple[bool, Optional[ASTSliceResult]]:
        """Verifies that the PythonASTSlicer can locate and extract the failing symbol accurately."""
        cleanup_needed = False
        if repo_dir is None:
            repo_dir = tempfile.mkdtemp(prefix=f"autoheal_ast_test_{case.id}_")
            cleanup_needed = True

        try:
            target_file_path = os.path.join(repo_dir, case.get_target_file())
            os.makedirs(os.path.dirname(target_file_path), exist_ok=True)
            with open(target_file_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(case.buggy_code)

            slice_res = None
            if case.failing_symbol_name:
                slice_res = self.slicer.slice_function_by_name(target_file_path, case.failing_symbol_name)

            if slice_res is None and case.failing_line:
                slice_res = self.slicer.slice_at_line(target_file_path, case.failing_line)

            success = (
                slice_res is not None and
                (not case.failing_symbol_name or slice_res.symbol_name == case.failing_symbol_name) and
                len(slice_res.code.strip()) > 0
            )
            return success, slice_res
        finally:
            if cleanup_needed:
                self._safe_cleanup(repo_dir)

    def run_case(self, case: BenchmarkCase) -> BenchmarkResult:
        """Runs the benchmark pipeline on a single BenchmarkCase."""
        start_time = time.time()
        temp_repo = tempfile.mkdtemp(prefix=f"autoheal_bench_{case.id}_")

        try:
            # 1. Setup workspace structure
            src_dir = os.path.join(temp_repo, "src")
            tests_dir = os.path.join(temp_repo, "tests")
            os.makedirs(src_dir, exist_ok=True)
            os.makedirs(tests_dir, exist_ok=True)

            with open(os.path.join(src_dir, "__init__.py"), "w", encoding="utf-8") as f:
                f.write("")
            with open(os.path.join(tests_dir, "__init__.py"), "w", encoding="utf-8") as f:
                f.write("")

            # conftest.py ensuring src is on sys.path
            conftest_path = os.path.join(temp_repo, "conftest.py")
            with open(conftest_path, "w", encoding="utf-8", newline="\n") as f:
                f.write("import sys, os\nsys.path.insert(0, os.path.abspath('.'))\n")

            # Write buggy source code
            target_path = os.path.join(temp_repo, case.get_target_file())
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(case.buggy_code)

            # Write test code
            test_path = os.path.join(temp_repo, case.get_test_file())
            os.makedirs(os.path.dirname(test_path), exist_ok=True)
            with open(test_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(case.test_code)

            # 2. Execute Tree-sitter AST slicing
            ast_slice = None
            if case.failing_symbol_name:
                ast_slice = self.slicer.slice_function_by_name(target_path, case.failing_symbol_name)
            if ast_slice is None and case.failing_line:
                ast_slice = self.slicer.slice_at_line(target_path, case.failing_line)

            ast_code = ast_slice.code if ast_slice else case.buggy_code
            symbol_name = ast_slice.symbol_name if ast_slice else (case.failing_symbol_name or case.id)
            failing_line = ast_slice.start_line if ast_slice else (case.failing_line or 1)
            surrounding_sigs = "\n".join(ast_slice.neighboring_signatures) if ast_slice else ""

            # Slice test code
            test_slice = self.slicer.slice_function_by_name(test_path, f"test_{case.id}")
            ast_test_code = test_slice.code if test_slice else case.test_code

            # 3. Construct initial deliberation state
            initial_state: AutoHealState = {
                "repo_path": temp_repo,
                "target_branch": "main",
                "commit_sha": f"bench-{case.id}",
                "raw_error_log": f"{case.exception_type}: {case.exception_message}",
                "failing_file": case.get_target_file(),
                "failing_line": failing_line,
                "failing_symbol_name": symbol_name,
                "failing_test_file": case.get_test_file(),
                "failing_test_name": case.get_test_file(),
                "ast_symbol_slice": ast_code,
                "ast_test_slice": ast_test_code,
                "ast_surrounding_signatures": surrounding_sigs,
                "exception_type": case.exception_type,
                "exception_message": case.exception_message,
                "round_count": 0,
                "max_rounds": self.max_rounds,
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

            # 4. Instantiate and invoke Orchestrator
            if self.orchestrator_factory:
                orchestrator = self.orchestrator_factory(temp_repo)
            else:
                effective_llm = self._get_llm_client()
                orchestrator = AutoHealOrchestrator(llm_client=effective_llm, repo_path=temp_repo)

            final_state = orchestrator.app.invoke(initial_state)

            # 5. Measure outcome
            elapsed = time.time() - start_time
            passed = (
                final_state.get("status") == "verified" and
                final_state.get("failing_test_resolved") is True and
                final_state.get("regression_suite_passed") is True
            )
            rounds = final_state.get("round_count", 1)
            error_msg = ""
            if not passed:
                error_msg = final_state.get("error_message") or final_state.get("test_feedback") or "Deliberation failed to verify fix."

            return BenchmarkResult(
                case_id=case.id,
                passed=bool(passed),
                rounds_used=rounds,
                execution_time_s=round(elapsed, 4),
                error_log=error_msg,
                hypothesis=final_state.get("coder_hypothesis"),
                patch_diff=final_state.get("patch_diff"),
                critic_passed=final_state.get("critic_test_passed")
            )
        except Exception as e:
            elapsed = time.time() - start_time
            return BenchmarkResult(
                case_id=case.id,
                passed=False,
                rounds_used=0,
                execution_time_s=round(elapsed, 4),
                error_log=f"Benchmark execution exception: {str(e)}"
            )
        finally:
            self._safe_cleanup(temp_repo)

    def run_suite(
        self,
        cases: Optional[Union[List[BenchmarkCase], List[str]]] = None
    ) -> BenchmarkSuiteReport:
        """Executes benchmark cases and returns aggregated BenchmarkSuiteReport."""
        target_cases: List[BenchmarkCase] = []
        if cases is None:
            target_cases = get_all_scenarios()
        else:
            for item in cases:
                if isinstance(item, str):
                    target_cases.append(get_scenario(item))
                elif isinstance(item, BenchmarkCase):
                    target_cases.append(item)

        results: List[BenchmarkResult] = []
        for case in target_cases:
            if self.verbose:
                print(f"▶ Running benchmark case: {case.id} ({case.name})...")
            result = self.run_case(case)
            results.append(result)
            if self.verbose:
                status = "PASS" if result.passed else "FAIL"
                print(f"  [{status}] in {result.execution_time_s:.2f}s (rounds: {result.rounds_used})")

        return BenchmarkSuiteReport.from_results(results)

    def _safe_cleanup(self, path: str, max_retries: int = 3, delay: float = 0.2):
        """Safely cleans up temporary directory with retries for Windows file locks."""
        if not os.path.exists(path):
            return
        for _ in range(max_retries):
            try:
                shutil.rmtree(path)
                return
            except Exception:
                time.sleep(delay)
        shutil.rmtree(path, ignore_errors=True)


def run_benchmark_suite(
    cases: Optional[Union[List[BenchmarkCase], List[str]]] = None,
    use_mock: bool = True,
    llm_client: Optional[LLMClient] = None
) -> BenchmarkSuiteReport:
    """Convenience function to execute the SWE-Bench mini suite."""
    runner = BenchmarkRunner(llm_client=llm_client, use_mock=use_mock)
    return runner.run_suite(cases=cases)


if __name__ == "__main__":
    runner = BenchmarkRunner(verbose=True)
    report = runner.run_suite()
    print("\n" + report.summary_table())
