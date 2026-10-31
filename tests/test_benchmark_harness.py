import os
import pytest
import json
from autoheal.benchmarks.models import BenchmarkCase, BenchmarkResult, BenchmarkSuiteReport
from autoheal.benchmarks.scenarios import (
    ALL_SCENARIOS,
    SCENARIOS_MAP,
    get_all_scenarios,
    get_scenario,
    SCENARIO_OFF_BY_ONE,
    SCENARIO_NONE_DEREFERENCE,
    SCENARIO_KEY_ERROR_NESTED,
    SCENARIO_ZERO_DIVISION_GUARD,
    SCENARIO_TYPE_COERCION_MISMATCH,
    SCENARIO_MISSING_BOUNDARY_CHECK,
)
from autoheal.benchmarks.runner import (
    BenchmarkRunner,
    BenchmarkMockLLMClient,
    run_benchmark_suite,
)
from autoheal.agents.llm_client import LLMClient

# --- 1. Model Unit Tests ---

def test_benchmark_case_model():
    case = BenchmarkCase(
        id="sample_bug",
        name="Sample Bug Test",
        category="arithmetic",
        bug_description="Sample bug description",
        buggy_code="def calc(): return 1 / 0",
        test_code="def test_calc(): assert calc() == 1",
        expected_fixed_code="def calc(): return 1"
    )
    assert case.id == "sample_bug"
    assert case.name == "Sample Bug Test"
    assert case.category == "arithmetic"
    assert case.get_target_file() == os.path.join("src", "sample_bug.py")
    assert case.get_test_file() == os.path.join("tests", "test_sample_bug.py")

def test_benchmark_result_model():
    result = BenchmarkResult(
        case_id="sample_bug",
        passed=True,
        rounds_used=1,
        execution_time_s=1.25,
        error_log=""
    )
    assert result.case_id == "sample_bug"
    assert result.passed is True
    assert result.rounds_used == 1
    assert result.execution_time_s == 1.25
    assert result.error_log == ""

def test_benchmark_suite_report():
    results = [
        BenchmarkResult(case_id="case1", passed=True, rounds_used=1, execution_time_s=1.0),
        BenchmarkResult(case_id="case2", passed=True, rounds_used=2, execution_time_s=2.0),
        BenchmarkResult(case_id="case3", passed=False, rounds_used=3, execution_time_s=1.5, error_log="Test failed")
    ]
    report = BenchmarkSuiteReport.from_results(results)

    assert report.total_cases == 3
    assert report.passed_cases == 2
    assert report.pass_rate_pct == pytest.approx(66.67, rel=1e-2)
    assert report.mean_time_s == pytest.approx(1.5, rel=1e-2)
    assert len(report.results) == 3

    table = report.summary_table()
    assert "| `case1` | ✅ PASS | 1 | 1.00s |" in table
    assert "| `case3` | ❌ FAIL | 3 | 1.50s |" in table
    assert "**Total Cases:** 3 | **Passed:** 2 | **Pass Rate:** 66.7%" in table

# --- 2. Scenario Corpus Integrity Tests ---

def test_all_scenarios_presence_and_count():
    scenarios = get_all_scenarios()
    assert len(scenarios) == 6
    assert len(ALL_SCENARIOS) == 6

    expected_ids = {
        "off_by_one",
        "none_dereference",
        "key_error_nested",
        "zero_division_guard",
        "type_coercion_mismatch",
        "missing_boundary_check"
    }
    actual_ids = {s.id for s in scenarios}
    assert actual_ids == expected_ids

def test_get_scenario():
    for case_id in [
        "off_by_one",
        "none_dereference",
        "key_error_nested",
        "zero_division_guard",
        "type_coercion_mismatch",
        "missing_boundary_check"
    ]:
        case = get_scenario(case_id)
        assert case.id == case_id
        assert len(case.bug_description) > 0
        assert len(case.buggy_code) > 0
        assert len(case.test_code) > 0
        assert len(case.expected_fixed_code) > 0
        assert case.failing_symbol_name is not None

    with pytest.raises(KeyError):
        get_scenario("non_existent_id")

# --- 3. AST Slicing Localization Tests ---

@pytest.mark.parametrize("case", ALL_SCENARIOS, ids=lambda c: c.id)
def test_ast_slicing_localizes_each_scenario(case: BenchmarkCase):
    runner = BenchmarkRunner(use_mock=True)
    success, slice_res = runner.verify_ast_slicing(case)
    assert success is True, f"Failed to slice scenario {case.id}"
    assert slice_res is not None
    assert slice_res.symbol_name == case.failing_symbol_name
    assert f"def {case.failing_symbol_name}" in slice_res.code

# --- 4. Benchmark Mock LLM Client Tests ---

def test_benchmark_mock_llm_client_coder_responses():
    client = BenchmarkMockLLMClient()
    for case in ALL_SCENARIOS:
        prompt = f"SYMBOL NAME: {case.failing_symbol_name}\nFAILING FILE: {case.get_target_file()}"
        response = client.complete("You are the Lead Coder Agent", prompt)
        data = json.loads(response)
        assert data["revised_code"] == case.expected_fixed_code.strip()
        assert case.name in data["hypothesis"]

def test_benchmark_mock_llm_client_critic_approval():
    client = BenchmarkMockLLMClient(should_fail_critic_rounds=0)
    response = client.complete("You are the Red-Team Critic Agent", "Check patch")
    assert '"is_approved": true' in response

def test_benchmark_mock_llm_client_critic_rejection_cycle():
    client = BenchmarkMockLLMClient(should_fail_critic_rounds=1)
    response_round1 = client.complete("You are the Red-Team Critic Agent", "Check patch")
    assert '"is_approved": false' in response_round1

    response_round2 = client.complete("You are the Red-Team Critic Agent", "Check revised patch")
    assert '"is_approved": true' in response_round2

# --- 5. Benchmark Runner Execution Tests ---

def test_benchmark_runner_single_case():
    runner = BenchmarkRunner(use_mock=True)
    case = get_scenario("zero_division_guard")
    result = runner.run_case(case)

    assert result.case_id == "zero_division_guard"
    assert result.passed is True
    assert result.rounds_used == 1
    assert result.execution_time_s > 0.0
    assert result.error_log == ""

def test_benchmark_runner_full_suite_100_pct_pass():
    runner = BenchmarkRunner(use_mock=True)
    report = runner.run_suite()

    assert report.total_cases == 6
    assert report.passed_cases == 6
    assert report.pass_rate_pct == 100.0
    assert report.mean_time_s > 0.0

    for result in report.results:
        assert result.passed is True
        assert result.rounds_used >= 1

    table = report.summary_table()
    assert "✅ PASS" in table
    assert "**Total Cases:** 6 | **Passed:** 6 | **Pass Rate:** 100.0%" in table

def test_benchmark_runner_subset_execution():
    runner = BenchmarkRunner(use_mock=True)
    report = runner.run_suite(cases=["off_by_one", "none_dereference"])

    assert report.total_cases == 2
    assert report.passed_cases == 2
    assert report.pass_rate_pct == 100.0
    assert [r.case_id for r in report.results] == ["off_by_one", "none_dereference"]

def test_benchmark_runner_handles_failed_patch():
    class FailingMockLLM(LLMClient):
        def complete(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
            if "Lead Coder Agent" in system_prompt:
                # Return buggy patch that still fails
                return '{"hypothesis": "Buggy attempt", "revised_code": "def calculate_throughput(requests, duration_seconds):\\n    return requests / duration_seconds", "explanation": "Still fails"}'
            return '{"is_approved": true, "critique": "Approved", "attack_test_code": null}'

    runner = BenchmarkRunner(llm_client=FailingMockLLM(), max_rounds=1)
    case = get_scenario("zero_division_guard")
    result = runner.run_case(case)

    assert result.case_id == "zero_division_guard"
    assert result.passed is False
