import os
import shutil
import tempfile
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore
import pytest
from pydantic import ValidationError

from autoheal.agents.schemas import CoderPatchOutput, CriticAttackOutput
from autoheal.agents.coder_agent import CoderAgent
from autoheal.agents.critic_agent import CriticAgent
from autoheal.agents.llm_client import LLMClient, BudgetExceededError
from autoheal.parsers.dependency_healer import DependencyHealer
from autoheal.parsers.pytest_log_parser import PytestFailure


# ============================================================================
# 1. Schema Validation Tests
# ============================================================================

def test_coder_patch_output_valid():
    patch = CoderPatchOutput(
        hypothesis="Fixed division by zero error.",
        revised_code="def divide(a, b):\n    return a / b if b != 0 else 0.0",
        explanation="Added conditional guard checking if b is non-zero."
    )
    assert patch.hypothesis == "Fixed division by zero error."
    assert "return a / b if b != 0 else 0.0" in patch.revised_code
    assert patch.explanation == "Added conditional guard checking if b is non-zero."

    # Backwards-compatible tuple unpacking
    hypo, code = patch
    assert hypo == patch.hypothesis
    assert code == patch.revised_code


def test_coder_patch_output_strips_markdown_fences():
    wrapped_code = "```python\ndef solve():\n    return 42\n```"
    patch = CoderPatchOutput(
        hypothesis="Hypothesis test",
        revised_code=wrapped_code
    )
    assert patch.revised_code == "def solve():\n    return 42"


def test_coder_agent_json_parsing():
    llm = LLMClient()
    coder = CoderAgent(llm)

    json_response = """```json
    {
        "hypothesis": "Fix off-by-one boundary check.",
        "revised_code": "def in_range(idx, max_len):\\n    return 0 <= idx < max_len",
        "explanation": "Changed <= max_len to < max_len"
    }
    ```"""
    parsed = coder.parse_response(json_response)
    assert isinstance(parsed, CoderPatchOutput)
    assert parsed.hypothesis == "Fix off-by-one boundary check."
    assert "0 <= idx < max_len" in parsed.revised_code
    assert parsed.explanation == "Changed <= max_len to < max_len"


def test_coder_agent_markdown_fallback():
    llm = LLMClient()
    coder = CoderAgent(llm)

    legacy_markdown = """
HYPOTHESIS:
Prevent IndexError by checking bounds.

REVISED_SYMBOL:
```python
def get_item(lst, index):
    if index < len(lst):
        return lst[index]
    return None
```

EXPLANATION:
Bound check added.
"""
    parsed = coder.parse_response(legacy_markdown)
    assert isinstance(parsed, CoderPatchOutput)
    assert "Prevent IndexError" in parsed.hypothesis
    assert "return lst[index]" in parsed.revised_code
    assert "Bound check added." in parsed.explanation


def test_critic_attack_output_valid():
    critic_output = CriticAttackOutput(
        is_approved=True,
        critique="The patch properly covers edge cases.",
        attack_test_code=None
    )
    assert critic_output.is_approved is True
    assert "properly covers" in critic_output.critique
    assert critic_output.attack_test_code is None

    # Tuple unpacking
    critique, attack = critic_output
    assert critique == critic_output.critique
    assert attack is None


def test_critic_attack_output_coercion_and_stripping():
    # String approval coercion
    output_approved = CriticAttackOutput(
        is_approved="APPROVED",
        critique="LGTM"
    )
    assert output_approved.is_approved is True

    output_rejected = CriticAttackOutput(
        is_approved="REJECTED",
        critique="Fails on negative inputs",
        attack_test_code="```python\ndef test_neg():\n    assert False\n```"
    )
    assert output_rejected.is_approved is False
    assert output_rejected.attack_test_code == "def test_neg():\n    assert False"


def test_critic_agent_json_parsing():
    llm = LLMClient()
    critic = CriticAgent(llm)

    json_payload = """
    {
        "is_approved": false,
        "critique": "Division by negative zero yields unexpected sign.",
        "attack_test_code": "def test_autoheal_edgecase():\\n    assert divide(1, -0.0) == 0.0"
    }
    """
    parsed = critic.parse_response(json_payload)
    assert isinstance(parsed, CriticAttackOutput)
    assert parsed.is_approved is False
    assert "unexpected sign" in parsed.critique
    assert "assert divide(1, -0.0) == 0.0" in parsed.attack_test_code


def test_critic_agent_markdown_fallback():
    llm = LLMClient()
    critic = CriticAgent(llm)

    markdown_resp = """
CRITIQUE:
APPROVED. Code handles boundary values and None safely.

ATTACK_TEST:
```python
def test_autoheal_edgecase_approved():
    assert safe_calc(None) is None
```
"""
    parsed = critic.parse_response(markdown_resp)
    assert isinstance(parsed, CriticAttackOutput)
    assert parsed.is_approved is True
    assert "handles boundary values" in parsed.critique
    assert "assert safe_calc(None) is None" in parsed.attack_test_code


# ============================================================================
# 2. Dependency Healer Tests
# ============================================================================

def test_dependency_normalization():
    assert DependencyHealer.normalize_package("yaml") == "pyyaml"
    assert DependencyHealer.normalize_package("yaml.scanner") == "pyyaml"
    assert DependencyHealer.normalize_package("PIL") == "pillow"
    assert DependencyHealer.normalize_package("cv2") == "opencv-python"
    assert DependencyHealer.normalize_package("sklearn") == "scikit-learn"
    assert DependencyHealer.normalize_package("bs4") == "beautifulsoup4"
    assert DependencyHealer.normalize_package("requests") == "requests"


def test_add_dependency_multiline_project_table():
    original_toml = """[build-system]
requires = ["setuptools"]

[project]
name = "sample-app"
version = "0.1.0"
dependencies = [
    "pytest>=8.0.0",
    "pydantic>=2.0.0"
]
"""
    patched = DependencyHealer.add_dependency_to_toml_content(original_toml, "yaml", ">=6.0")
    parsed = tomllib.loads(patched)
    deps = parsed["project"]["dependencies"]
    assert "pyyaml>=6.0" in deps
    assert "pytest>=8.0.0" in deps
    assert len(deps) == 3


def test_add_dependency_inline_project_table():
    original_toml = """[project]
name = "tiny-app"
dependencies = ["requests>=2.0.0"]
"""
    patched = DependencyHealer.add_dependency_to_toml_content(original_toml, "PIL")
    parsed = tomllib.loads(patched)
    deps = parsed["project"]["dependencies"]
    assert "pillow" in deps
    assert "requests>=2.0.0" in deps
    assert len(deps) == 2


def test_add_dependency_no_dependencies_key():
    original_toml = """[project]
name = "clean-project"
version = "1.0.0"

[tool.ruff]
line-length = 88
"""
    patched = DependencyHealer.add_dependency_to_toml_content(original_toml, "click")
    parsed = tomllib.loads(patched)
    assert "click" in parsed["project"]["dependencies"]


def test_add_dependency_idempotent():
    original_toml = """[project]
dependencies = [
    "pyyaml>=5.4",
    "requests"
]
"""
    # Adding yaml when pyyaml already exists should be a no-op
    patched = DependencyHealer.add_dependency_to_toml_content(original_toml, "yaml")
    assert patched == original_toml


def test_add_dependency_poetry_table():
    original_toml = """[tool.poetry]
name = "poetry-app"

[tool.poetry.dependencies]
python = "^3.10"
"""
    patched = DependencyHealer.add_dependency_to_toml_content(original_toml, "cv2")
    parsed = tomllib.loads(patched)
    assert "opencv-python" in parsed["tool"]["poetry"]["dependencies"]


def test_dependency_healer_full_file_flow():
    temp_dir = tempfile.mkdtemp(prefix="autoheal_dep_test_")
    try:
        pyproject_path = os.path.join(temp_dir, "pyproject.toml")
        with open(pyproject_path, "w", encoding="utf-8") as f:
            f.write("""[project]\nname = "test-pkg"\ndependencies = []\n""")

        failure = PytestFailure(
            test_id="tests/test_loader.py::test_yaml_load",
            test_file="tests/test_loader.py",
            failing_file="src/loader.py",
            failing_line=1,
            exception_type="ModuleNotFoundError",
            exception_message="No module named 'yaml'",
            failure_mode="MISSING_DEPENDENCY",
            missing_package="yaml"
        )

        assert DependencyHealer.can_heal(failure) is True
        healed = DependencyHealer.heal_failure(temp_dir, failure, version_spec=">=5.4.1")
        assert healed is True

        with open(pyproject_path, "r", encoding="utf-8") as f:
            content = f.read()

        parsed = tomllib.loads(content)
        assert "pyyaml>=5.4.1" in parsed["project"]["dependencies"]
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dependency_healer_ignores_logic_bugs():
    failure = PytestFailure(
        test_id="tests/test_math.py::test_zero",
        test_file="tests/test_math.py",
        failing_file="src/math.py",
        failing_line=10,
        exception_type="ZeroDivisionError",
        exception_message="division by zero",
        failure_mode="LOGIC_BUG"
    )
    assert DependencyHealer.can_heal(failure) is False


# ============================================================================
# 3. Token & Cost Guardrails Tests
# ============================================================================

def test_token_estimation():
    assert LLMClient.estimate_tokens("") == 0
    assert LLMClient.estimate_tokens("a") == 1
    # 100 characters approx 25 tokens
    text_100 = "a" * 100
    assert LLMClient.estimate_tokens(text_100) == 25


def test_cost_calculation():
    llm_gpt4o = LLMClient(model="gpt-4o")
    # gpt-4o pricing: $2.50 / 1M prompt, $10.00 / 1M completion
    # 1,000,000 prompt tokens = $2.50
    # 1,000,000 completion tokens = $10.00
    cost = llm_gpt4o.calculate_cost(prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert abs(cost - 12.50) < 1e-4

    # claude-3-5-sonnet: $3.00 prompt, $15.00 completion
    llm_claude = LLMClient(provider="anthropic", model="claude-3-5-sonnet")
    cost_claude = llm_claude.calculate_cost(prompt_tokens=500_000, completion_tokens=100_000)
    expected_claude = (0.5 * 3.00) + (0.1 * 15.00)  # 1.50 + 1.50 = 3.00
    assert abs(cost_claude - expected_claude) < 1e-4


def test_usage_tracking_and_reset():
    llm = LLMClient(model="gpt-4o")
    assert llm.get_usage()["total_tokens"] == 0
    assert llm.get_usage()["total_cost_usd"] == 0.0

    llm.track_usage(prompt_tokens=2000, completion_tokens=500)
    usage = llm.get_usage()
    assert usage["prompt_tokens"] == 2000
    assert usage["completion_tokens"] == 500
    assert usage["total_tokens"] == 2500
    assert usage["total_cost_usd"] > 0.0

    llm.reset_usage()
    reset_usage = llm.get_usage()
    assert reset_usage["total_tokens"] == 0
    assert reset_usage["total_cost_usd"] == 0.0


def test_budget_guardrail_enforcement():
    # Set a small budget cap of $0.001
    llm = LLMClient(model="gpt-4o", max_budget_usd=0.001)

    # 100 prompt tokens, 50 completion tokens = very tiny cost (< $0.001)
    llm.track_usage(prompt_tokens=100, completion_tokens=50)
    assert llm.total_cost_usd < 0.001
    # Check budget does not raise
    llm.check_budget()

    # Incur heavy usage that exceeds $0.001
    # 500,000 tokens on gpt-4o = ~$1.25
    llm.track_usage(prompt_tokens=500_000, completion_tokens=100_000)
    assert llm.total_cost_usd > 0.001

    with pytest.raises(BudgetExceededError) as exc_info:
        llm.check_budget()

    assert "LLM budget limit exceeded" in str(exc_info.value)

    # Complete call should also immediately block execution when over budget
    with pytest.raises(BudgetExceededError):
        llm.complete("System prompt", "User prompt")
