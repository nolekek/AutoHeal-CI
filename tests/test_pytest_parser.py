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
    assert f.failure_mode == "LOGIC_BUG"
    assert len(f.stack_frames) >= 2

def test_external_frame_filtering():
    stack_with_site_packages = """
=================================== FAILURES ===================================
_________________________________ test_api_call ________________________________
tests/test_client.py:10: in test_api_call
    data = fetch_json()
src/service.py:22: in fetch_json
    return json.loads(bad_text)
C:/Python/Lib/site-packages/urllib3/response.py:105: in read
    raise ValueError("Corrupt body")
E   ValueError: Corrupt body
"""
    failures = PytestLogParser.parse(stack_with_site_packages)
    assert len(failures) == 1
    f = failures[0]
    # The external site-packages frame should be filtered out; target points to src/service.py
    assert f.failing_file == "src/service.py"
    assert f.failing_line == 22

def test_missing_dependency_mode():
    missing_dep_output = """
==================================== ERRORS ====================================
_______________________ ERROR collecting tests/test_api.py ______________________
ImportError while importing test module 'tests/test_api.py'.
tests/test_api.py:3: in <module>
    import fastapi
E   ModuleNotFoundError: No module named 'fastapi'
"""
    failures = PytestLogParser.parse(missing_dep_output)
    assert len(failures) == 1
    f = failures[0]
    assert f.failure_mode == "MISSING_DEPENDENCY"
    assert f.missing_package == "fastapi"
