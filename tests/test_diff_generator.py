import pytest
from autoheal.parsers.diff_generator import UnifiedDiffGenerator

def test_unified_diff_creation():
    orig = "def foo():\n    return 1\n"
    mod = "def foo():\n    return 2\n"
    diff = UnifiedDiffGenerator.create_unified_diff(orig, mod, "src/foo.py")
    assert "--- a/src/foo.py" in diff
    assert "+++ b/src/foo.py" in diff
    assert "-    return 1" in diff
    assert "+    return 2" in diff

def test_replace_symbol_in_file():
    full_file = """import sys

def add(a, b):
    return a + b

def divide(a, b):
    return a / b

def multiply(a, b):
    return a * b
"""
    orig_sym = "def divide(a, b):\n    return a / b"
    rev_sym = "def divide(a, b):\n    if b == 0:\n        return 0.0\n    return a / b"

    updated = UnifiedDiffGenerator.replace_symbol_in_file(full_file, orig_sym, rev_sym)
    assert "if b == 0:" in updated
    assert "def add(a, b):" in updated
    assert "def multiply(a, b):" in updated
