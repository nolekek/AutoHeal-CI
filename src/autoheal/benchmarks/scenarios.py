import os
from typing import List, Dict
from .models import BenchmarkCase

SCENARIO_OFF_BY_ONE = BenchmarkCase(
    id="off_by_one",
    name="Off-by-One List Slicing",
    category="boundary_error",
    bug_description="Off-by-one indexing error in list slicing where page calculation excludes the final element.",
    buggy_code="""def paginate_items(items: list, page: int, page_size: int = 5) -> list:
    \"\"\"Paginate a list of items using 1-indexed page numbers.\"\"\"
    start = (page - 1) * page_size
    end = start + page_size - 1
    return items[start:end]
""",
    test_code="""import pytest
from src.off_by_one import paginate_items

def test_paginate_items():
    data = list(range(10))
    page1 = paginate_items(data, page=1, page_size=5)
    assert page1 == [0, 1, 2, 3, 4]
    page2 = paginate_items(data, page=2, page_size=5)
    assert page2 == [5, 6, 7, 8, 9]
""",
    expected_fixed_code="""def paginate_items(items: list, page: int, page_size: int = 5) -> list:
    \"\"\"Paginate a list of items using 1-indexed page numbers.\"\"\"
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end]""",
    target_file=os.path.join("src", "off_by_one.py"),
    test_file=os.path.join("tests", "test_off_by_one.py"),
    failing_symbol_name="paginate_items",
    failing_line=5,
    exception_type="AssertionError",
    exception_message="assert [0, 1, 2, 3] == [0, 1, 2, 3, 4]"
)

SCENARIO_NONE_DEREFERENCE = BenchmarkCase(
    id="none_dereference",
    name="None Dereference on User Name",
    category="null_pointer",
    bug_description="Calling method on None when user dictionary is None or name field is absent.",
    buggy_code="""from typing import Optional, Dict

def format_user_title(user: Optional[Dict[str, str]]) -> str:
    \"\"\"Formats the title-cased user name or returns empty string if not found.\"\"\"
    return user["name"].strip().title()
""",
    test_code="""import pytest
from src.none_dereference import format_user_title

def test_format_user_title():
    assert format_user_title({"name": " alice "}) == "Alice"
    assert format_user_title(None) == ""
    assert format_user_title({}) == ""
""",
    expected_fixed_code="""def format_user_title(user: Optional[Dict[str, str]]) -> str:
    \"\"\"Formats the title-cased user name or returns empty string if not found.\"\"\"
    if not user:
        return ""
    name = user.get("name")
    if not name:
        return ""
    return name.strip().title()""",
    target_file=os.path.join("src", "none_dereference.py"),
    test_file=os.path.join("tests", "test_none_dereference.py"),
    failing_symbol_name="format_user_title",
    failing_line=5,
    exception_type="TypeError",
    exception_message="'NoneType' object is not subscriptable"
)

SCENARIO_KEY_ERROR_NESTED = BenchmarkCase(
    id="key_error_nested",
    name="Nested Config KeyError",
    category="data_structure",
    bug_description="Accessing nested dictionary keys without default fallback raises KeyError.",
    buggy_code="""from typing import Dict, Any

def get_database_timeout(config: Dict[str, Any]) -> int:
    \"\"\"Extract database connection timeout from nested configuration.\"\"\"
    return config["database"]["timeout"]["seconds"]
""",
    test_code="""import pytest
from src.key_error_nested import get_database_timeout

def test_get_database_timeout():
    full_config = {"database": {"timeout": {"seconds": 60}}}
    assert get_database_timeout(full_config) == 60
    assert get_database_timeout({}) == 30
    assert get_database_timeout({"database": {}}) == 30
""",
    expected_fixed_code="""def get_database_timeout(config: Dict[str, Any]) -> int:
    \"\"\"Extract database connection timeout from nested configuration.\"\"\"
    db = config.get("database", {})
    timeout = db.get("timeout", {})
    return timeout.get("seconds", 30)""",
    target_file=os.path.join("src", "key_error_nested.py"),
    test_file=os.path.join("tests", "test_key_error_nested.py"),
    failing_symbol_name="get_database_timeout",
    failing_line=5,
    exception_type="KeyError",
    exception_message="'database'"
)

SCENARIO_ZERO_DIVISION_GUARD = BenchmarkCase(
    id="zero_division_guard",
    name="Zero Division Guard in Throughput Calculation",
    category="arithmetic",
    bug_description="Calculating throughput with zero duration raises ZeroDivisionError.",
    buggy_code="""def calculate_throughput(requests: float, duration_seconds: float) -> float:
    \"\"\"Calculates requests per second.\"\"\"
    return requests / duration_seconds
""",
    test_code="""import pytest
from src.zero_division_guard import calculate_throughput

def test_calculate_throughput():
    assert calculate_throughput(100.0, 10.0) == 10.0
    assert calculate_throughput(50.0, 0.0) == 0.0
    assert calculate_throughput(0.0, 0.0) == 0.0
""",
    expected_fixed_code="""def calculate_throughput(requests: float, duration_seconds: float) -> float:
    \"\"\"Calculates requests per second.\"\"\"
    if duration_seconds <= 0:
        return 0.0
    return requests / duration_seconds""",
    target_file=os.path.join("src", "zero_division_guard.py"),
    test_file=os.path.join("tests", "test_zero_division_guard.py"),
    failing_symbol_name="calculate_throughput",
    failing_line=3,
    exception_type="ZeroDivisionError",
    exception_message="float division by zero"
)

SCENARIO_TYPE_COERCION_MISMATCH = BenchmarkCase(
    id="type_coercion_mismatch",
    name="Type Coercion Mismatch in Accumulator",
    category="type_error",
    bug_description="Adding string representation of integer to int total raises TypeError.",
    buggy_code="""from typing import Any

def accumulate_counter(total: int, delta: Any) -> int:
    \"\"\"Adds delta to running total, coercing string numbers to integers.\"\"\"
    return total + delta
""",
    test_code="""import pytest
from src.type_coercion_mismatch import accumulate_counter

def test_accumulate_counter():
    assert accumulate_counter(10, 5) == 15
    assert accumulate_counter(10, "5") == 15
    assert accumulate_counter(0, "42") == 42
""",
    expected_fixed_code="""def accumulate_counter(total: int, delta: Any) -> int:
    \"\"\"Adds delta to running total, coercing string numbers to integers.\"\"\"
    return total + int(delta)""",
    target_file=os.path.join("src", "type_coercion_mismatch.py"),
    test_file=os.path.join("tests", "test_type_coercion_mismatch.py"),
    failing_symbol_name="accumulate_counter",
    failing_line=5,
    exception_type="TypeError",
    exception_message="unsupported operand type(s) for +: 'int' and 'str'"
)

SCENARIO_MISSING_BOUNDARY_CHECK = BenchmarkCase(
    id="missing_boundary_check",
    name="Missing Boundary Check on Empty Sequence",
    category="boundary_error",
    bug_description="Accessing boundary indices [0] and [-1] on empty sequence raises IndexError.",
    buggy_code="""from typing import List, Tuple, Optional, Any

def get_boundary_elements(items: List[Any]) -> Tuple[Optional[Any], Optional[Any]]:
    \"\"\"Returns the first and last elements of a sequence, or (None, None) if empty.\"\"\"
    return (items[0], items[-1])
""",
    test_code="""import pytest
from src.missing_boundary_check import get_boundary_elements

def test_get_boundary_elements():
    assert get_boundary_elements([10, 20, 30]) == (10, 30)
    assert get_boundary_elements(["solo"]) == ("solo", "solo")
    assert get_boundary_elements([]) == (None, None)
""",
    expected_fixed_code="""def get_boundary_elements(items: List[Any]) -> Tuple[Optional[Any], Optional[Any]]:
    \"\"\"Returns the first and last elements of a sequence, or (None, None) if empty.\"\"\"
    if not items:
        return (None, None)
    return (items[0], items[-1])""",
    target_file=os.path.join("src", "missing_boundary_check.py"),
    test_file=os.path.join("tests", "test_missing_boundary_check.py"),
    failing_symbol_name="get_boundary_elements",
    failing_line=5,
    exception_type="IndexError",
    exception_message="list index out of range"
)

ALL_SCENARIOS: List[BenchmarkCase] = [
    SCENARIO_OFF_BY_ONE,
    SCENARIO_NONE_DEREFERENCE,
    SCENARIO_KEY_ERROR_NESTED,
    SCENARIO_ZERO_DIVISION_GUARD,
    SCENARIO_TYPE_COERCION_MISMATCH,
    SCENARIO_MISSING_BOUNDARY_CHECK
]

SCENARIOS_MAP: Dict[str, BenchmarkCase] = {case.id: case for case in ALL_SCENARIOS}

def get_all_scenarios() -> List[BenchmarkCase]:
    """Returns the complete benchmark scenarios corpus."""
    return list(ALL_SCENARIOS)

def get_scenario(case_id: str) -> BenchmarkCase:
    """Retrieves a single scenario by id or raises KeyError."""
    if case_id not in SCENARIOS_MAP:
        raise KeyError(f"Scenario '{case_id}' not found in benchmark corpus. Available: {list(SCENARIOS_MAP.keys())}")
    return SCENARIOS_MAP[case_id]
