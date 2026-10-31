import re
from typing import Dict, Any, Tuple
from .state import AutoHealState
from .llm_client import LLMClient

CRITIC_SYSTEM_PROMPT = """You are the Red-Team Critic Agent in AutoHeal-CI.
Your sole mission is to find vulnerabilities, regressions, or test-suite overfitting in the Coder's proposed patch.

RULES:
1. Scrutinize edge cases: boundary values, None, empty collections, division by zero, invalid types, or performance traps.
2. If the patch looks completely sound, declare "APPROVED" and provide a regression test verifying the fix.
3. If the patch has an edge case, write a new pytest test function that exposes the flaw.
4. Output your response in this exact format:

CRITIQUE:
<Analysis of potential flaws or verification rationale>

ATTACK_TEST:
```python
def test_autoheal_edgecase_<symbol>():
    <pytest test body>
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
        critique, attack_test = self._parse_critic_response(response)

        return {
            "critic_critique": critique,
            "critic_attack_code": attack_test
        }

    def _parse_critic_response(self, text: str) -> Tuple[str, str]:
        critique = "Critic review"
        attack_test = ""

        crit_match = re.search(r"CRITIQUE:\s*(.*?)(?=ATTACK_TEST:|$)", text, re.DOTALL)
        if crit_match:
            critique = crit_match.group(1).strip()

        code_match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        if code_match:
            attack_test = code_match.group(1).strip()

        return critique, attack_test
