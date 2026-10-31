import os
import shutil
import tempfile
import pytest
from autoheal.agents.llm_client import LLMClient
from autoheal.agents.graph import AutoHealOrchestrator
from autoheal.agents.state import AutoHealState

class MockLLMClient(LLMClient):
    """Mock LLM that returns pre-determined responses for Coder and Critic."""
    def complete(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        if "Lead Coder Agent" in system_prompt:
            return """HYPOTHESIS:
Fix division by zero by returning float('inf') or handling zero.

REVISED_SYMBOL:
```python
def divide(a: int, b: int) -> float:
    if b == 0:
        return 0.0
    return a / b
```"""
        elif "Red-Team Critic Agent" in system_prompt:
            return """CRITIQUE:
APPROVED. The patch handles division by zero safely.

ATTACK_TEST:
```python
def test_autoheal_edgecase_divide():
    from src.calculator import divide
    assert divide(0, 5) == 0.0
    assert divide(10, 2) == 5.0
```"""
        return "OK"

def test_full_orchestrator_graph_cycle():
    # Setup temporary mock repo
    temp_repo = tempfile.mkdtemp(prefix="autoheal_repo_mock_")
    try:
        src_dir = os.path.join(temp_repo, "src")
        tests_dir = os.path.join(temp_repo, "tests")
        os.makedirs(src_dir, exist_ok=True)
        os.makedirs(tests_dir, exist_ok=True)

        calc_file = os.path.join(src_dir, "calculator.py")
        with open(calc_file, "w", encoding="utf-8") as f:
            f.write("def divide(a: int, b: int) -> float:\n    return a / b\n")

        test_file = os.path.join(tests_dir, "test_calculator.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("from src.calculator import divide\n\ndef test_divide():\n    assert divide(10, 2) == 5.0\n")

        mock_llm = MockLLMClient()
        orchestrator = AutoHealOrchestrator(llm_client=mock_llm, repo_path=temp_repo)

        initial_state: AutoHealState = {
            "repo_path": temp_repo,
            "target_branch": "main",
            "commit_sha": "abc1234",
            "raw_error_log": "ZeroDivisionError: division by zero",
            "failing_file": os.path.join("src", "calculator.py"),
            "failing_line": 2,
            "failing_symbol_name": "divide",
            "failing_test_file": os.path.join("tests", "test_calculator.py"),
            "failing_test_name": "tests/test_calculator.py",
            "ast_symbol_slice": "def divide(a: int, b: int) -> float:\n    return a / b",
            "ast_test_slice": "def test_divide():\n    assert divide(10, 2) == 5.0",
            "ast_surrounding_signatures": "",
            "exception_type": "ZeroDivisionError",
            "exception_message": "division by zero",
            "round_count": 0,
            "max_rounds": 3,
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

        final_state = orchestrator.app.invoke(initial_state)

        assert final_state["status"] == "verified"
        assert final_state["failing_test_resolved"] is True
        assert final_state["critic_test_passed"] is True
        assert final_state["regression_suite_passed"] is True
    finally:
        shutil.rmtree(temp_repo, ignore_errors=True)
