# Python Example: AutoHeal-CI in Action

This directory contains a minimal Python project with an intentional edge-case bug in `calculator.py`.

## The Defect
`test_calculator.py` tests `compute_average([])`. In `calculator.py`:
```python
def compute_average(scores: list[float]) -> float:
    return sum(scores) / len(scores) # Raises ZeroDivisionError on empty list!
```

## Running AutoHeal-CI Locally
```bash
# 1. Run pytest (observe 1 failure)
pytest test_calculator.py

# 2. Run AutoHeal-CI to heal the failure
auto-heal --repo-path .
```

AutoHeal-CI will:
1. Parse the `ZeroDivisionError` from pytest output.
2. Use Tree-sitter to slice `compute_average` without loading unrelated files.
3. Formulate an adversarial Coder-Critic hypothesis loop.
4. Verify the fix in an isolated `.autoheal-sandbox` Git Worktree.
5. Create a verified PR with regression shields!
