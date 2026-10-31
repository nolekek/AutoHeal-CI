import json
import re
from typing import Dict, Any, Tuple, Optional
from .state import AutoHealState
from .llm_client import LLMClient
from .schemas import CoderPatchOutput

CODER_SYSTEM_PROMPT = """You are the Lead Coder Agent in AutoHeal-CI, an autonomous CI/CD self-healing system.
Your mission is to fix the bug with the minimal, most surgical code patch possible.

RULES:
1. Focus ONLY on fixing the root cause demonstrated by the failing test and exception.
2. DO NOT overfit or hardcode return values (e.g. `if x == 42: return 0`). Write robust general logic.
3. Preserve existing signatures and contracts.
4. Output your response as a valid JSON object matching the following structure:
```json
{
  "hypothesis": "<1-3 sentence explanation of the bug and the fix>",
  "revised_code": "<The complete, fixed Python code of the failing function/method>",
  "explanation": "<Detailed reasoning for the fix>"
}
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
        parsed = self.parse_response(response)

        return {
            "coder_hypothesis": parsed.hypothesis,
            "patched_file_content": parsed.revised_code,
            "round_count": state["round_count"] + 1
        }

    def parse_response(self, text: str) -> CoderPatchOutput:
        """
        Parses LLM output into CoderPatchOutput schema.
        Prioritizes structured JSON parsing with robust fallback to markdown extraction.
        """
        # 1. Attempt structured JSON parsing
        parsed_json = self._extract_json(text)
        if parsed_json is not None:
            try:
                return CoderPatchOutput.model_validate(parsed_json)
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

    def _fallback_markdown_parse(self, text: str) -> CoderPatchOutput:
        """Legacy and markdown format fallback parser."""
        hypothesis = "Automated surgical fix"
        revised_code = ""
        explanation = ""

        hypo_match = re.search(r"HYPOTHESIS:\s*(.*?)(?=REVISED_SYMBOL:|EXPLANATION:|$)", text, re.DOTALL | re.IGNORECASE)
        if hypo_match:
            hypothesis = hypo_match.group(1).strip()

        code_match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        if code_match:
            revised_code = code_match.group(1).strip()
        elif "REVISED_SYMBOL:" in text:
            revised_code = text.split("REVISED_SYMBOL:")[-1].strip()
        elif "```" in text:
            generic_fence = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
            if generic_fence:
                revised_code = generic_fence.group(1).strip()

        exp_match = re.search(r"EXPLANATION:\s*(.*?)(?=HYPOTHESIS:|REVISED_SYMBOL:|$)", text, re.DOTALL | re.IGNORECASE)
        if exp_match:
            explanation = exp_match.group(1).strip()

        return CoderPatchOutput(
            hypothesis=hypothesis,
            revised_code=revised_code,
            explanation=explanation
        )

    def _parse_coder_response(self, text: str) -> CoderPatchOutput:
        """Backwards compatibility alias for parse_response."""
        return self.parse_response(text)
