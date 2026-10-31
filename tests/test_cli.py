import os
import tempfile
import pytest
from autoheal.cli import main
import sys

def test_cli_all_tests_passing(monkeypatch):
    test_args = ["auto-heal", "--repo-path", "."]
    monkeypatch.setattr(sys, "argv", test_args)
    # Mock run_local_pytest to prevent recursive subprocess execution
    monkeypatch.setattr("autoheal.cli.run_local_pytest", lambda repo_path, test_cmd: (0, "5 passed in 0.05s"))
    result = main()
    assert result == 0

def test_cli_with_log_file_mock(monkeypatch):
    log_content = """
============================= test session starts =============================
platform win32 -- Python 3.10.11, pytest-8.1.1
collected 1 item

tests/test_calc.py F                                                     [100%]

=================================== FAILURES ===================================
________________________________ test_zero _____________________________________

    def test_zero():
>       assert divide(1, 0) == 0

tests/test_calc.py:5: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

    def divide(a, b):
>       return a / b
E       ZeroDivisionError: division by zero

src/calc.py:2: ZeroDivisionError
=========================== short test summary info ===========================
FAILED tests/test_calc.py::test_zero - ZeroDivisionError: division by zero
============================== 1 failed in 0.05s ==============================
"""
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8") as f:
        f.write(log_content)
        log_path = f.name

    try:
        # If target file doesn't exist on disk, AST slicer gracefully handles it
        test_args = ["auto-heal", "--log-file", log_path, "--repo-path", "."]
        monkeypatch.setattr(sys, "argv", test_args)
        # Should execute localization and graph without crashing
        result = main()
        # Mock LLM is unconfigured, so deliberate fails or completes
        assert result in (0, 1)
    finally:
        if os.path.exists(log_path):
            os.remove(log_path)
