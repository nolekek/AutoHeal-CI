from typing import TypedDict, Optional, List, Dict, Any

class AutoHealState(TypedDict):
    # Context & Repo
    repo_path: str
    target_branch: str
    commit_sha: str
    raw_error_log: str
    
    # AST & Localization
    failing_file: str
    failing_line: int
    failing_symbol_name: str
    failing_test_file: str
    failing_test_name: str
    ast_symbol_slice: str            # Exact failing function AST slice
    ast_test_slice: str              # Exact failing test AST slice
    ast_surrounding_signatures: str  # Class/module signatures
    exception_type: str
    exception_message: str

    # Deliberation State
    round_count: int                 # Current round (1..3)
    max_rounds: int
    coder_hypothesis: Optional[str]
    patch_diff: Optional[str]        # Unified git diff
    patched_file_content: Optional[str]
    failing_test_resolved: bool      # Did the original failing test pass?
    
    # Red-Team Critic State
    critic_attack_code: Optional[str] # Critic's edge-case test code
    critic_critique: Optional[str]
    critic_test_passed: bool         # Did the patch survive Critic's test?
    
    # Regression Verification
    regression_suite_passed: bool    # Did all original tests in repo pass?
    test_feedback: str               # Terminal output / error feedback from tests
    
    # Delivery
    status: str                      # 'in_progress', 'verified', 'failed_max_rounds', 'delivered'
    pr_url: Optional[str]
    error_message: Optional[str]
