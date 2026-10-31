import pytest
from autoheal.parsers.pytest_log_parser import PytestLogParser

SAMPLE_PYTEST_OUTPUT = """
============================= test session starts =============================
platform win32 -- Python 3.10.11, pytest-8.1.1
collected 3 items

tests/test_math.py .F.                                                   [100%]

=================================== FAILURES ===================================
________________________________ test_division ________________________________

    def test_division():
>       res = divide(10, 0)

tests/test_math.py:15: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

a = 10, b = 0

    def divide(a: int, b: int) -> float:
>       return a / b
E       ZeroDivisionError: division by zero

src/calculator.py:8: ZeroDivisionError
=========================== short test summary info ===========================
FAILED tests/test_math.py::test_division - ZeroDivisionError: division by zero
========================= 1 failed, 2 passed in 0.08s =========================
"""

def test_parse_pytest_failure():
    failures = PytestLogParser.parse(SAMPLE_PYTEST_OUTPUT)
    assert len(failures) == 1
    f = failures[0]
    assert "test_division" in f.test_id
    assert f.failing_file == "src/calculator.py"
    assert f.failing_line == 8
    assert f.exception_type == "ZeroDivisionError"
    assert "division by zero" in f.exception_message
    assert len(f.stack_frames) >= 2
