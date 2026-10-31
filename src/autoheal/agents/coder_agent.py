import re
from typing import Dict, Any, Tuple
from .state import AutoHealState
from .llm_client import LLMClient

CODER_SYSTEM_PROMPT = """You are the Lead Coder Agent in AutoHeal-CI, an autonomous CI/CD self-healing system.
Your mission is to fix the bug with the minimal, most surgical code patch possible.

RULES:
1. Focus ONLY on fixing the root cause demonstrated by the failing test and exception.
2. DO NOT overfit or hardcode return values (e.g. `if x == 42: return 0`). Write robust general logic.
3. Preserve existing signatures and contracts.
4. Output your response in this exact format:

HYPOTHESIS:
<1-3 sentence explanation of the bug and the fix>

REVISED_SYMBOL:
```python
<The complete, fixed Python code of the failing function/method>
```
"""

class CoderAgent:
    """Generates bug fix hypotheses and surgical code patches."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_patch(self, state: AutoHealState) -> Dict[str, Any]:
        """Runs the Coder Agent node and updates state with hypothesis and revised code."""
        prompt = f"""
FAILING FILE: {state['failing_file']} (Line {state['failing_line']})
SYMBOL NAME: {state['failing_symbol_name']}
EXCEPTION: {state['exception_type']}: {state['exception_message']}

--- AST SLICE OF FAILING FUNCTION ---
{state['ast_symbol_slice']}

--- AST SLICE OF FAILING TEST ---
{state['ast_test_slice']}

--- SURROUNDING CLASS/MODULE SIGNATURES ---
{state['ast_surrounding_signatures']}
"""
        if state.get("test_feedback"):
            prompt += f"\n--- FEEDBACK FROM PREVIOUS ROUND ({state['round_count']}) ---\n{state['test_feedback']}\n"

        if state.get("critic_critique"):
            prompt += f"\n--- RED-TEAM CRITIC OBJECTION ---\n{state['critic_critique']}\n"

        response = self.llm.complete(CODER_SYSTEM_PROMPT, prompt)
        hypothesis, revised_code = self._parse_coder_response(response)

        return {
            "coder_hypothesis": hypothesis,
            "patched_file_content": revised_code,
            "round_count": state["round_count"] + 1
        }

    def _parse_coder_response(self, text: str) -> Tuple[str, str]:
        hypothesis = "Automated surgical fix"
        revised_code = ""

        hypo_match = re.search(r"HYPOTHESIS:\s*(.*?)(?=REVISED_SYMBOL:|$)", text, re.DOTALL)
        if hypo_match:
            hypothesis = hypo_match.group(1).strip()

        code_match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        if code_match:
            revised_code = code_match.group(1).strip()
        elif "REVISED_SYMBOL:" in text:
            revised_code = text.split("REVISED_SYMBOL:")[-1].strip()

        return hypothesis, revised_code
