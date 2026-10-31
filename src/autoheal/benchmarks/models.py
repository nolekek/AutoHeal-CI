import os
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class BenchmarkCase(BaseModel):
    """Represents an individual SWE-Bench mini-harness bug scenario."""
    id: str
    name: str
    category: str
    bug_description: str
    buggy_code: str
    test_code: str
    expected_fixed_code: str
    target_file: Optional[str] = None
    test_file: Optional[str] = None
    failing_symbol_name: Optional[str] = None
    failing_line: Optional[int] = None
    exception_type: str = "Exception"
    exception_message: str = ""

    model_config = {"extra": "ignore"}

    def get_target_file(self) -> str:
        """Returns relative target path inside the repository."""
        return self.target_file or os.path.join("src", f"{self.id}.py")

    def get_test_file(self) -> str:
        """Returns relative test path inside the repository."""
        return self.test_file or os.path.join("tests", f"test_{self.id}.py")


class BenchmarkResult(BaseModel):
    """Result of running AutoHeal deliberation on a single benchmark scenario."""
    case_id: str
    passed: bool
    rounds_used: int = 1
    execution_time_s: float = 0.0
    error_log: str = ""
    hypothesis: Optional[str] = None
    patch_diff: Optional[str] = None
    critic_passed: Optional[bool] = None

    model_config = {"extra": "ignore"}


class BenchmarkSuiteReport(BaseModel):
    """Aggregated evaluation report across all SWE-Bench mini benchmark scenarios."""
    total_cases: int
    passed_cases: int
    pass_rate_pct: float
    mean_time_s: float
    results: List[BenchmarkResult] = Field(default_factory=list)

    model_config = {"extra": "ignore"}

    @classmethod
    def from_results(cls, results: List[BenchmarkResult]) -> "BenchmarkSuiteReport":
        """Calculates suite aggregate metrics from individual benchmark results."""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        pass_rate = round((passed / total * 100.0), 2) if total > 0 else 0.0
        mean_time = round((sum(r.execution_time_s for r in results) / total), 4) if total > 0 else 0.0
        return cls(
            total_cases=total,
            passed_cases=passed,
            pass_rate_pct=pass_rate,
            mean_time_s=mean_time,
            results=results
        )

    def summary_table(self) -> str:
        """Renders an executive markdown summary table of the benchmark run."""
        lines = [
            "| Case ID | Status | Rounds | Time (s) | Notes |",
            "| :--- | :---: | :---: | :---: | :--- |"
        ]
        for r in self.results:
            status_emoji = "✅ PASS" if r.passed else "❌ FAIL"
            notes = r.error_log.replace("\n", " ").strip()[:50] if r.error_log else "Clean pass"
            lines.append(f"| `{r.case_id}` | {status_emoji} | {r.rounds_used} | {r.execution_time_s:.2f}s | {notes} |")
        lines.append("")
        lines.append(f"**Total Cases:** {self.total_cases} | **Passed:** {self.passed_cases} | **Pass Rate:** {self.pass_rate_pct:.1f}% | **Mean Time:** {self.mean_time_s:.2f}s")
        return "\n".join(lines)
