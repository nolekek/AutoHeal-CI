import re
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator

class CoderPatchOutput(BaseModel):
    """Structured response schema for Coder Agent."""
    hypothesis: str = Field(
        ...,
        description="1-3 sentence explanation of the bug and the surgical fix."
    )
    revised_code: str = Field(
        ...,
        description="The complete, fixed Python code of the failing function/method."
    )
    explanation: str = Field(
        default="",
        description="Detailed explanation of the code modifications made."
    )

    model_config = {"extra": "ignore"}

    @field_validator("revised_code", mode="before")
    @classmethod
    def strip_code_fences(cls, v: Any) -> str:
        """Strip enclosing markdown python code fences if the LLM wrapped the code."""
        if not isinstance(v, str):
            return str(v)
        code_fence = re.search(r"```(?:python)?\s*(.*?)\s*```", v, re.DOTALL)
        if code_fence:
            return code_fence.group(1).strip()
        return v.strip()

    def __iter__(self):
        """Allows backwards-compatible tuple unpacking: hypothesis, revised_code = patch."""
        return iter((self.hypothesis, self.revised_code))


class CriticAttackOutput(BaseModel):
    """Structured response schema for Red-Team Critic Agent."""
    is_approved: bool = Field(
        ...,
        description="True if the patch is safe, sound, and regression-free; False if flawed."
    )
    critique: str = Field(
        ...,
        description="Adversarial evaluation detailing potential flaws, regressions, or approval rationale."
    )
    attack_test_code: Optional[str] = Field(
        default=None,
        description="Pytest test body exposing an edge case or verifying regression fix (if any)."
    )

    model_config = {"extra": "ignore"}

    @field_validator("is_approved", mode="before")
    @classmethod
    def parse_approval_string(cls, v: Any) -> bool:
        """Coerce boolean or common LLM approval strings to boolean."""
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            cleaned = v.strip().upper()
            if cleaned in ("TRUE", "APPROVED", "YES", "PASS", "PASSED", "1"):
                return True
            if cleaned in ("FALSE", "REJECTED", "DISAPPROVED", "NO", "FAIL", "FAILED", "0"):
                return False
        return bool(v)

    @field_validator("attack_test_code", mode="before")
    @classmethod
    def strip_attack_fences(cls, v: Any) -> Optional[str]:
        """Strip enclosing markdown code fences from attack test code."""
        if v is None:
            return None
        if not isinstance(v, str):
            return str(v)
        stripped = v.strip()
        if not stripped or stripped.lower() in ("none", "null"):
            return None
        code_fence = re.search(r"```(?:python)?\s*(.*?)\s*```", stripped, re.DOTALL)
        if code_fence:
            return code_fence.group(1).strip()
        return stripped

    def __iter__(self):
        """Allows backwards-compatible tuple unpacking: critique, attack_code = critic_output."""
        return iter((self.critique, self.attack_test_code))
