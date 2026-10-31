import json
import re
from typing import Dict, Any, Tuple, Optional
from .state import AutoHealState
from .llm_client import LLMClient
from .schemas import CriticAttackOutput

CRITIC_SYSTEM_PROMPT = """You are the Red-Team Critic Agent in AutoHeal-CI.
Your sole mission is to find vulnerabilities, regressions, or test-suite overfitting in the Coder's proposed patch.

RULES:
1. Scrutinize edge cases: boundary values, None, empty collections, division by zero, invalid types, or performance traps.
2. If the patch looks completely sound, set "is_approved" to true and provide verification rationale in "critique".
3. If the patch has flaws or edge cases, set "is_approved" to false, detail the flaw in "critique", and provide a pytest attack test in "attack_test_code".
4. Output your response as a valid JSON object matching the following structure:
```json
{
  "is_approved": true,
  "critique": "<Analysis of potential flaws or verification rationale>",
  "attack_test_code": "<Optional pytest test code body exposing the flaw, or null>"
}
```
"""

class CriticAgent:
    """Adversarial agent that attacks patches with property and edge-case tests."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def review_and_attack(self, state: AutoHealState) -> Dict[str, Any]:
        """Evaluates the patch and generates a counter-test."""
        prompt = f"""
FAILING FUNCTION ORIGINAL:
{state['ast_symbol_slice']}

CODER'S HYPOTHESIS:
{state['coder_hypothesis']}

CODER'S REVISED CODE:
{state['patched_file_content']}

ORIGINAL TEST THAT FAILED:
{state['ast_test_slice']}
"""
        response = self.llm.complete(CRITIC_SYSTEM_PROMPT, prompt)
        parsed = self.parse_response(response)

        return {
            "critic_critique": parsed.critique,
            "critic_attack_code": parsed.attack_test_code
        }

    def parse_response(self, text: str) -> CriticAttackOutput:
        """
        Parses LLM output into CriticAttackOutput schema.
        Prioritizes structured JSON parsing with robust fallback to markdown extraction.
        """
        # 1. Attempt structured JSON parsing
        parsed_json = self._extract_json(text)
        if parsed_json is not None:
            try:
                return CriticAttackOutput.model_validate(parsed_json)
            except Exception:
                pass

        # 2. Robust fallback: regex/markdown extraction
        return self._fallback_markdown_parse(text)

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extracts and deserializes a JSON object from raw response text if present."""
        # Try finding json in markdown code fence ```json ... ```
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence_match:
            try:
                return json.loads(fence_match.group(1))
            except Exception:
                pass

        # Try finding outermost braces { ... }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass

        return None

    def _fallback_markdown_parse(self, text: str) -> CriticAttackOutput:
        """Legacy and markdown format fallback parser."""
        critique = "Critic review"
        attack_test: Optional[str] = None

        crit_match = re.search(r"CRITIQUE:\s*(.*?)(?=ATTACK_TEST:|$)", text, re.DOTALL | re.IGNORECASE)
        if crit_match:
            critique = crit_match.group(1).strip()
        else:
            critique = text.strip()

        code_match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        if code_match:
            attack_test = code_match.group(1).strip()
        elif "ATTACK_TEST:" in text:
            rem = text.split("ATTACK_TEST:")[-1].strip()
            if rem and not rem.lower().startswith("none") and not rem.lower().startswith("null"):
                attack_test = rem

        # Determine approval
        crit_upper = critique.upper()
        text_upper = text.upper()
        is_approved = (
            ("APPROVED" in crit_upper or "APPROVED" in text_upper)
            and "NOT APPROVED" not in crit_upper
            and "DISAPPROVED" not in crit_upper
        )

        return CriticAttackOutput(
            is_approved=is_approved,
            critique=critique,
            attack_test_code=attack_test
        )

    def _parse_critic_response(self, text: str) -> CriticAttackOutput:
        """Backwards compatibility alias for parse_response."""
        return self.parse_response(text)
