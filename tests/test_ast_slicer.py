import os
import tempfile
import pytest
from autoheal.parsers.ast_slicer import PythonASTSlicer

SAMPLE_CODE = """# Top comments
import math

class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b

    def divide(self, a: int, b: int) -> float:
        if b == 0:
            raise ZeroDivisionError("division by zero")
        return a / b

    def multiply(self, a: int, b: int) -> int:
        return a * b

def standalone_func(x: int) -> int:
    y = x * 2
    return y + 10
"""

def test_ast_slice_method_inside_class():
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_CODE)
        temp_path = f.name

    try:
        slicer = PythonASTSlicer()
        # Line 11 is 'return a / b' inside divide
        result = slicer.slice_at_line(temp_path, 11)
        assert result is not None
        assert result.symbol_name == "divide"
        assert result.symbol_type == "method"
        assert result.enclosing_class == "Calculator"
        assert "def divide(self, a: int, b: int) -> float:" in result.code
        assert len(result.neighboring_signatures) == 2
        assert any("add" in s for s in result.neighboring_signatures)
        assert any("multiply" in s for s in result.neighboring_signatures)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_ast_slice_standalone_function():
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_CODE)
        temp_path = f.name

    try:
        slicer = PythonASTSlicer()
        # Line 18 is 'return y + 10' inside standalone_func
        result = slicer.slice_at_line(temp_path, 18)
        assert result is not None
        assert result.symbol_name == "standalone_func"
        assert result.symbol_type == "function"
        assert result.enclosing_class is None
        assert "def standalone_func(x: int) -> int:" in result.code
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
