from __future__ import annotations
import os
from typing import Optional, Dict, Any, TYPE_CHECKING
from .patch_artifact import PatchArtifactExporter, DEFAULT_PATCH_DIR, DEFAULT_PATCH_FILENAME

if TYPE_CHECKING:
    from ..agents.state import AutoHealState


class StepSummaryGenerator:
    """
    Generates rich, interactive GitHub Step Summary markdown reports for AutoHeal-CI.
    
    Includes:
    - High-level execution status badges and failure metadata
    - Visual Mermaid diagram illustrating Coder vs Critic state transitions
    - Collapsible unified diff preview: `<details><summary>🔍 Unified Diff Preview</summary>`
    - Collapsible Red-Team Critic edge-case test code preview
    - Token Usage and Estimated Cost breakdown table
    - Fallback patch instructions (`curl ... | git apply`) when PR creation is unavailable
    """

    def __init__(
        self,
        state: Optional[AutoHealState] = None,
        usage: Optional[Dict[str, Any]] = None,
        patch_path: Optional[str] = None,
        model: Optional[str] = None,
        license_info: Optional[Any] = None,
    ):
        self.state: Dict[str, Any] = dict(state) if state else {}
        self.usage: Dict[str, Any] = usage or {}
        self.patch_path: Optional[str] = patch_path
        self.model: str = model or self.state.get("model") or "gpt-4o"
        self.license_info = license_info

    def generate_mermaid_diagram(self) -> str:
        """
        Generates a Mermaid state transition diagram showing the adversarial
        Coder vs Critic deliberation and verification loop.
        """
        round_count = self.state.get("round_count", 1)
        max_rounds = self.state.get("max_rounds", 3)
        status = self.state.get("status", "in_progress")

        return f"""```mermaid
stateDiagram-v2
    direction TB
    [*] --> AST_Localization: Failure Detected
    AST_Localization --> Coder_Agent: Sliced Context & AST Signatures
    
    state "Coder Agent" as Coder_Agent
    state "Sandbox Patch Verification" as Sandbox_Patch_Verification
    state "Red-Team Critic" as Critic_Agent
    state "Critic Attack Verification" as Critic_Attack_Verification
    state "Regression Shield" as Regression_Shield
    state "Delivery UX" as Delivery_UX

    Coder_Agent --> Sandbox_Patch_Verification: Synthesize Patch (Round {round_count}/{max_rounds})
    
    Sandbox_Patch_Verification --> Critic_Agent: Failing Test Resolved ✅
    Sandbox_Patch_Verification --> Coder_Agent: Failing Test Broken ❌ (Deliberation Retry)
    
    Critic_Agent --> Critic_Attack_Verification: Synthesize Edge-Case Test
    
    Critic_Attack_Verification --> Regression_Shield: Counter-Test Survived ✅
    Critic_Attack_Verification --> Coder_Agent: Vulnerability Found ❌ (Deliberation Retry)
    
    Regression_Shield --> Delivery_UX: 100% Regression Suite Green ✅
    Regression_Shield --> Coder_Agent: Regression Introduced ❌ (Deliberation Retry)
    
    Delivery_UX --> Verified: Pull Request / Fallback .patch
    Delivery_UX --> [*]
```"""

    def generate_diff_preview(self) -> str:
        """
        Generates the collapsible Unified Diff Preview block.
        Required format: <details><summary>🔍 Unified Diff Preview</summary>...
        """
        patch_diff = self.state.get("patch_diff")
        if patch_diff and patch_diff.strip():
            content = f"```diff\n{patch_diff.strip()}\n```"
        else:
            content = "_No unified diff generated._"

        return (
            "<details>\n"
            "<summary>🔍 Unified Diff Preview</summary>\n\n"
            f"{content}\n"
            "</details>"
        )

    def generate_critic_attack_preview(self) -> str:
        """Generates collapsible Red-Team Critic attack test code preview."""
        attack_code = self.state.get("critic_attack_code")
        if not attack_code or not attack_code.strip():
            return ""

        return (
            "<details>\n"
            "<summary>🛡️ Red-Team Critic Edge-Case Counter-Test</summary>\n\n"
            f"```python\n{attack_code.strip()}\n```\n"
            "</details>"
        )

    def generate_token_usage_table(self) -> str:
        """
        Generates a GitHub-flavored Markdown table showing token consumption
        and estimated USD costs, including budget cap status.
        """
        prompt_tokens = self.usage.get("prompt_tokens", 0)
        completion_tokens = self.usage.get("completion_tokens", 0)
        total_tokens = self.usage.get("total_tokens", prompt_tokens + completion_tokens)
        cost_usd = self.usage.get("total_cost_usd", 0.0)
        max_budget = self.usage.get("max_budget_usd")

        budget_str = f"${max_budget:.4f} USD" if max_budget is not None else "Unlimited"
        status_str = "Within Budget Cap"
        if max_budget is not None and cost_usd >= max_budget:
            status_str = "⚠️ Budget Cap Reached"

        return f"""| Deliberation Metric | Count / Amount |
| :--- | :--- |
| **LLM Model** | `{self.model}` |
| **Prompt Tokens** | `{prompt_tokens:,}` |
| **Completion Tokens** | `{completion_tokens:,}` |
| **Total Tokens Consumed** | `{total_tokens:,}` |
| **Estimated Cost (USD)** | **`${cost_usd:.6f}`** |
| **Configured Budget Cap** | `{budget_str}` ({status_str}) |
"""

    def generate_summary(self) -> str:
        """Assembles the full GitHub Step Summary Markdown document."""
        status = self.state.get("status", "unknown")
        pr_url = self.state.get("pr_url")
        patch_diff = self.state.get("patch_diff")
        failing_symbol = self.state.get("failing_symbol_name", "unknown")
        failing_file = self.state.get("failing_file", "unknown")
        failing_line = self.state.get("failing_line", 0)
        exc_type = self.state.get("exception_type", "Failure")
        exc_msg = self.state.get("exception_message", "N/A")
        hypothesis = self.state.get("coder_hypothesis", "N/A")
        rounds = self.state.get("round_count", 1)
        max_rounds = self.state.get("max_rounds", 3)

        # Status badge & delivery section
        if status == "verified" and pr_url:
            status_header = f"## 🩺 AutoHeal-CI Fix Verified & PR Created! 🎉"
            delivery_section = f"""### 🚀 Pull Request Created
AutoHeal-CI has verified the patch and submitted a Pull Request:
👉 **[{pr_url}]({pr_url})**
"""
        elif status == "verified" and not pr_url:
            status_header = f"## 🩺 AutoHeal-CI Fix Verified (Fallback Patch Exported) 📦"
            p_path = self.patch_path or f"{DEFAULT_PATCH_DIR}/{DEFAULT_PATCH_FILENAME}"
            delivery_section = f"""### 📦 Fallback Patch Exported
Pull Request creation was skipped or the repository is a fork without write permissions.
The verified patch artifact has been saved to `{p_path}`.

```bash
# Apply this fix locally from checkout:
git apply {p_path}

# Or download and apply via curl from CI artifact:
curl -sL "<patch-artifact-url>" | git apply
```
"""
        elif status == "dependency_healed":
            status_header = f"## 🩺 AutoHeal-CI Missing Dependency Auto-Healed! 📦"
            pkg = self.state.get("missing_package", "dependency")
            delivery_section = f"""### 📦 Dependency Auto-Healed
AutoHeal-CI detected missing package `{pkg}` and successfully updated `pyproject.toml`.
"""
        else:
            status_header = f"## ⚠️ AutoHeal-CI Deliberation Finished (Fix Not Verified)"
            delivery_section = f"""### ⚠️ Verification Incomplete
AutoHeal-CI could not arrive at a verified patch within {max_rounds} deliberation rounds.
Manual developer inspection is recommended.
"""

        badge_str = ""
        if self.license_info:
            from ..licensing import LicenseManager
            badge_str = f"\n* {LicenseManager.format_badge(self.license_info)}"

        # Build sections
        sections = [
            status_header,
            delivery_section.strip(),
            "---",
            "### 🎯 Target Failure Context",
            f"* **Failing Symbol:** `{failing_symbol}` in `{failing_file}:{failing_line}`",
            f"* **Exception:** `{exc_type}: {exc_msg}`",
            f"* **Coder Hypothesis:** {hypothesis}",
            f"* **Deliberation Deliberations:** `{rounds}` of `{max_rounds}` rounds completed",
            f"* **Regression Shield:** {'✅ 100% Repo Tests Passed' if self.state.get('regression_suite_passed') else '❌ Incomplete'}{badge_str}",
            "---",
            "### 🔄 Adversarial Deliberation Workflow",
            self.generate_mermaid_diagram(),
            "---",
            "### 🔍 Patch & Attack Verification",
            self.generate_diff_preview(),
        ]

        critic_block = self.generate_critic_attack_preview()
        if critic_block:
            sections.append(critic_block)

        sections.extend([
            "---",
            "### 💰 Token Usage & Cost Breakdown",
            self.generate_token_usage_table(),
            "---",
            "_Generated autonomously by [AutoHeal-CI](https://github.com/auto-heal-ci) enterprise agent engine._"
        ])

        return "\n\n".join(sections) + "\n"

    def write_to_github_summary(self, summary_path: Optional[str] = None) -> bool:
        """
        Writes the generated markdown summary to the file pointed to by
        summary_path or the GITHUB_STEP_SUMMARY environment variable.
        Returns True if successfully written, False otherwise.
        """
        target = summary_path or os.getenv("GITHUB_STEP_SUMMARY")
        if not target:
            return False

        try:
            target_dir = os.path.dirname(os.path.abspath(target))
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            content = self.generate_summary()
            with open(target, "a", encoding="utf-8") as f:
                f.write(content + "\n")
            return True
        except Exception:
            return False


def write_step_summary(
    state: AutoHealState,
    usage: Optional[Dict[str, Any]] = None,
    patch_path: Optional[str] = None,
    summary_path: Optional[str] = None
) -> str:
    """Convenience function to generate and write GitHub Step Summary."""
    generator = StepSummaryGenerator(state=state, usage=usage, patch_path=patch_path)
    generator.write_to_github_summary(summary_path=summary_path)
    return generator.generate_summary()
