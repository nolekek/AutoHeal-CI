import os
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END

from .state import AutoHealState
from .llm_client import LLMClient
from .coder_agent import CoderAgent
from .critic_agent import CriticAgent
from ..sandbox.git_worktree import SandboxHarness
from ..delivery.github_pr import GitHubPRDelivery

class AutoHealOrchestrator:
    """Orchestrates the LangGraph multi-agent deliberation and verification cycle."""

    def __init__(self, llm_client: LLMClient, repo_path: str):
        self.llm = llm_client
        self.repo_path = repo_path
        self.coder = CoderAgent(llm_client)
        self.critic = CriticAgent(llm_client)
        self.sandbox = SandboxHarness(repo_path)
        self.delivery = GitHubPRDelivery()
        self.app = self._build_graph().compile()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(AutoHealState)

        # Register nodes
        graph.add_node("coder", self._node_coder)
        graph.add_node("verify_patch", self._node_verify_patch)
        graph.add_node("critic", self._node_critic)
        graph.add_node("verify_critic", self._node_verify_critic)
        graph.add_node("regression_shield", self._node_regression_shield)
        graph.add_node("deliver", self._node_deliver)

        # Define flow
        graph.add_edge(START, "coder")
        graph.add_edge("coder", "verify_patch")

        # Routing after verifying Coder's patch on original failing test
        graph.add_conditional_edges(
            "verify_patch",
            self._route_after_patch_verify,
            {
                "critic": "critic",
                "retry_coder": "coder",
                "failed": END
            }
        )

        graph.add_edge("critic", "verify_critic")

        # Routing after verifying Critic's attack test
        graph.add_conditional_edges(
            "verify_critic",
            self._route_after_critic_verify,
            {
                "regression": "regression_shield",
                "retry_coder": "coder",
                "failed": END
            }
        )

        # Routing after Regression Shield
        graph.add_conditional_edges(
            "regression_shield",
            self._route_after_regression,
            {
                "deliver": "deliver",
                "retry_coder": "coder",
                "failed": END
            }
        )

        graph.add_edge("deliver", END)

        return graph

    # --- Node implementations ---

    def _node_coder(self, state: AutoHealState) -> Dict[str, Any]:
        """Coder Agent generates hypothesis and patch."""
        return self.coder.generate_patch(state)

    def _node_verify_patch(self, state: AutoHealState) -> Dict[str, Any]:
        """Applies patch to sandbox and verifies if the original failing test passes."""
        self.sandbox.create()

        # Update failing file with revised code in sandbox
        if state.get("patched_file_content"):
            rel_path = state["failing_file"]
            # Apply revised code or replace target function
            self._apply_replacement_to_sandbox(rel_path, state)

        # Run specific failing test
        test_selector = state.get("failing_test_name") or state.get("failing_test_file")
        success, output = self.sandbox.run_tests(test_selector=test_selector)

        return {
            "failing_test_resolved": success,
            "test_feedback": output
        }

    def _node_critic(self, state: AutoHealState) -> Dict[str, Any]:
        """Red-Team Critic Agent analyses patch and writes edge-case test."""
        return self.critic.review_and_attack(state)

    def _node_verify_critic(self, state: AutoHealState) -> Dict[str, Any]:
        """Applies Critic's edge-case test into sandbox and tests patch against it."""
        attack_code = state.get("critic_attack_code")
        if not attack_code:
            return {"critic_test_passed": True, "test_feedback": "Critic approved patch directly."}

        # Inject critic's test into a temporary test file in sandbox
        critic_test_file = os.path.join(self.sandbox.sandbox_path, "tests", "test_autoheal_critic.py")
        os.makedirs(os.path.dirname(critic_test_file), exist_ok=True)
        with open(critic_test_file, "w", encoding="utf-8") as f:
            f.write(f"import pytest\n\n{attack_code}\n")

        # Run critic's test
        success, output = self.sandbox.run_tests(test_selector="tests/test_autoheal_critic.py")
        return {
            "critic_test_passed": success,
            "test_feedback": output
        }

    def _node_regression_shield(self, state: AutoHealState) -> Dict[str, Any]:
        """Runs the entire test suite in sandbox to guarantee zero regressions."""
        success, output = self.sandbox.run_tests(test_selector=None)
        return {
            "regression_suite_passed": success,
            "test_feedback": output
        }

    def _node_deliver(self, state: AutoHealState) -> Dict[str, Any]:
        """Commits verified fix and opens Pull Request."""
        pr_url = self.delivery.deliver(state)
        self.sandbox.cleanup()
        return {
            "status": "verified",
            "pr_url": pr_url
        }

    # --- Routing functions ---

    def _route_after_patch_verify(self, state: AutoHealState) -> Literal["critic", "retry_coder", "failed"]:
        if state["failing_test_resolved"]:
            return "critic"
        if state["round_count"] < state["max_rounds"]:
            return "retry_coder"
        return "failed"

    def _route_after_critic_verify(self, state: AutoHealState) -> Literal["regression", "retry_coder", "failed"]:
        if state["critic_test_passed"]:
            return "regression"
        if state["round_count"] < state["max_rounds"]:
            return "retry_coder"
        return "failed"

    def _route_after_regression(self, state: AutoHealState) -> Literal["deliver", "retry_coder", "failed"]:
        if state["regression_suite_passed"]:
            return "deliver"
        if state["round_count"] < state["max_rounds"]:
            return "retry_coder"
        return "failed"

    # --- Helpers ---

    def _apply_replacement_to_sandbox(self, rel_path: str, state: AutoHealState):
        sandbox_target = os.path.join(self.sandbox.sandbox_path, rel_path)
        if not os.path.exists(sandbox_target):
            return

        with open(sandbox_target, "r", encoding="utf-8") as f:
            original = f.read()

        # Surgical AST replacement: replace the original function slice with the revised code
        orig_slice = state.get("ast_symbol_slice", "").strip()
        revised = state.get("patched_file_content", "").strip()

        if orig_slice and orig_slice in original:
            updated = original.replace(orig_slice, revised, 1)
        else:
            # Fallback if whitespace differs: replace by lines
            lines = original.splitlines(keepends=True)
            start = max(0, state["failing_line"] - 1)
            # Find boundaries or overwrite if single function
            updated = revised if len(lines) <= 20 else original

        with open(sandbox_target, "w", encoding="utf-8") as f:
            f.write(updated)
