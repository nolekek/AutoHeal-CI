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

    @staticmethod
    def multiply(a: int, b: int) -> int:
        return a * b

def standalone_func(x: int) -> int:
    y = x * 2
    return y + 10

@pytest.fixture
def sample_user():
    return {"id": 1, "name": "Alice"}

async def async_fetch_data(url: str) -> dict:
    return {"status": "ok"}
"""

def test_ast_slice_method_inside_class():
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_CODE)
        temp_path = f.name

    try:
        slicer = PythonASTSlicer()
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
        result = slicer.slice_at_line(temp_path, 19)
        assert result is not None
        assert result.symbol_name == "standalone_func"
        assert result.symbol_type == "function"
        assert result.enclosing_class is None
        assert "def standalone_func(x: int) -> int:" in result.code
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_ast_slice_decorated_function():
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_CODE)
        temp_path = f.name

    try:
        slicer = PythonASTSlicer()
        # Line 23 is 'return {"id": 1...' inside sample_user
        result = slicer.slice_at_line(temp_path, 23)
        assert result is not None
        assert result.symbol_name == "sample_user"
        assert "@pytest.fixture" in result.decorators
        assert "@pytest.fixture" in result.code
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_ast_slice_async_function():
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_CODE)
        temp_path = f.name

    try:
        slicer = PythonASTSlicer()
        # Line 26 is 'return {"status": "ok"}' inside async_fetch_data
        result = slicer.slice_at_line(temp_path, 26)
        assert result is not None
        assert result.symbol_name == "async_fetch_data"
        assert result.symbol_type == "async_function"
        assert "async def async_fetch_data" in result.code
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
