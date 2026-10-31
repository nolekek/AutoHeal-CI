import pytest
import os
from autoheal.parsers.jest_log_parser import JestLogParser, JestFailure, StackFrame
from autoheal.benchmarks.ts_scenarios import (
    TS_ALL_SCENARIOS,
    get_ts_scenarios,
    get_ts_scenario,
    TS_SCENARIO_OFF_BY_ONE,
    TS_SCENARIO_UNDEFINED_PROPERTY,
    TS_SCENARIO_TYPE_COERCION,
)

SAMPLE_JEST_ASSERTION_OUTPUT = """
FAIL src/__tests__/calculator.test.ts
  ● Calculator › add › correctly adds two numbers

    expect(received).toBe(expected) // Object.is equality

    Expected: 5
    Received: 4

      12 |   it('correctly adds two numbers', () => {
      13 |       const res = add(2, 2);
    > 14 |       expect(res).toBe(5);
         |                   ^
      15 |   });

      at Object.<anonymous> (src/__tests__/calculator.test.ts:14:19)
      at Promise.then.completed (node_modules/jest-circus/build/utils.js:364:28)
      at new Promise (<anonymous>)
"""

SAMPLE_JEST_SOURCE_ERROR_OUTPUT = """
FAIL tests/user.test.ts
  ● UserService › getUser › throws when user not found

    TypeError: Cannot read properties of undefined (reading 'name')

      18 | export function formatUserName(user?: User): string {
    > 19 |   return user.name.trim();
         |               ^
      20 | }

      at formatUserName (src/userService.ts:19:15)
      at Object.<anonymous> (tests/user.test.ts:25:12)
      at Promise.then.completed (node_modules/jest-circus/build/utils.js:364:28)
      at callAsyncCircusFn (node_modules/jest-circus/build/utils.js:295:10)
"""

SAMPLE_VITEST_OUTPUT = """
FAIL  tests/calculator.test.ts > Calculator > add > correctly adds two numbers
AssertionError: expected 4 to be 5 // Object.is equality

- Expected:
5

+ Received:
4

 ❯ tests/calculator.test.ts:14:19
     12|   it('correctly adds two numbers', () => {
     13|     const res = add(2, 2);
     14|     expect(res).toBe(5);
       |                 ^
     15|   });
"""

SAMPLE_VITEST_SOURCE_FRAME_OUTPUT = """
FAIL  tests/user.test.ts > User > get details
TypeError: Cannot read properties of undefined (reading 'name')
 ❯ formatUserName src/userService.ts:19:15
 ❯ tests/user.test.ts:25:12
 ❯ node_modules/vitest/dist/vendor/runner.js:123:45
"""

SAMPLE_JEST_MISSING_MODULE = """
FAIL tests/index.test.ts
  ● Test suite failed to run

    Cannot find module 'axios' from 'src/api.ts'

    Require stack:
      src/api.ts
      tests/index.test.ts

      at Resolver.resolveModule (node_modules/jest-resolve/build/resolver.js:324:11)
      at Object.<anonymous> (src/api.ts:1:1)
"""

SAMPLE_VITEST_MISSING_MODULE = """
FAIL tests/api.test.ts
Error: Failed to resolve import "lodash" from "src/utils.ts". Does the file exist?
 ❯ src/utils.ts:2:8
 ❯ tests/api.test.ts:1:1
"""


# --- 1. Basic Jest Output Parsing Tests ---

def test_parse_jest_assertion_failure():
    failures = JestLogParser.parse(SAMPLE_JEST_ASSERTION_OUTPUT)
    assert len(failures) == 1
    f = failures[0]

    assert "Calculator › add › correctly adds two numbers" in f.test_id
    assert f.test_name == "Calculator › add › correctly adds two numbers"
    assert f.test_file == "src/__tests__/calculator.test.ts"
    assert f.failing_file == "src/__tests__/calculator.test.ts"
    assert f.failing_line == 14
    assert f.failing_column == 19
    assert f.expected_diff == "5"
    assert f.received_diff == "4"
    assert f.expected == "5"
    assert f.received == "4"
    assert f.failure_mode == "LOGIC_BUG"
    assert len(f.stack_frames) >= 2


def test_parse_jest_source_frame_pinpointing():
    failures = JestLogParser.parse(SAMPLE_JEST_SOURCE_ERROR_OUTPUT)
    assert len(failures) == 1
    f = failures[0]

    # Node modules must be filtered out, and innermost project code frame is src/userService.ts
    assert f.failing_file == "src/userService.ts"
    assert f.failing_line == 19
    assert f.failing_column == 15
    assert f.test_file == "tests/user.test.ts"
    assert f.exception_type == "TypeError"
    assert "Cannot read properties of undefined" in f.exception_message

    # Check frame filtering
    internal_frames = [frame for frame in f.stack_frames if frame.is_project_internal]
    external_frames = [frame for frame in f.stack_frames if not frame.is_project_internal]
    assert len(internal_frames) == 2
    assert any("node_modules" in frame.file_path for frame in external_frames)


def test_node_modules_filtering_sandwich():
    """Verify that node_modules at both the top and bottom of the stack are filtered out."""
    stack_text = """
FAIL tests/config.test.ts
  ● Config › read

    Error: Failed to parse

      at baseGet (node_modules/lodash/get.js:52:10)
      at getValue (src/config.ts:30:8)
      at tests/config.test.ts:12:3
      at node_modules/jest-runner/run.js:100:1
"""
    failures = JestLogParser.parse(stack_text)
    assert len(failures) == 1
    f = failures[0]
    # Innermost project frame should be src/config.ts:30:8, ignoring lodash in node_modules
    assert f.failing_file == "src/config.ts"
    assert f.failing_line == 30
    assert f.failing_column == 8
    assert f.test_file == "tests/config.test.ts"


# --- 2. Vitest Parsing Tests ---

def test_parse_vitest_output():
    failures = JestLogParser.parse(SAMPLE_VITEST_OUTPUT)
    assert len(failures) == 1
    f = failures[0]

    assert "tests/calculator.test.ts" in f.test_file
    assert "Calculator > add > correctly adds two numbers" in f.test_id
    assert f.failing_file == "tests/calculator.test.ts"
    assert f.failing_line == 14
    assert f.failing_column == 19
    assert f.expected_diff == "5"
    assert f.received_diff == "4"
    assert f.exception_type == "AssertionError"


def test_parse_vitest_source_frame():
    failures = JestLogParser.parse(SAMPLE_VITEST_SOURCE_FRAME_OUTPUT)
    assert len(failures) == 1
    f = failures[0]

    assert f.failing_file == "src/userService.ts"
    assert f.failing_line == 19
    assert f.failing_column == 15
    assert f.test_file == "tests/user.test.ts"
    assert f.exception_type == "TypeError"
    assert "Cannot read properties of undefined" in f.exception_message


# --- 3. Missing Package Detection Tests ---

def test_parse_missing_package_jest():
    failures = JestLogParser.parse(SAMPLE_JEST_MISSING_MODULE)
    assert len(failures) == 1
    f = failures[0]

    assert f.failure_mode == "MISSING_DEPENDENCY"
    assert f.missing_package == "axios"
    assert f.failing_file == "src/api.ts"


def test_parse_missing_package_vitest():
    failures = JestLogParser.parse(SAMPLE_VITEST_MISSING_MODULE)
    assert len(failures) == 1
    f = failures[0]

    assert f.failure_mode == "MISSING_DEPENDENCY"
    assert f.missing_package == "lodash"
    assert f.failing_file == "src/utils.ts"


def test_parse_missing_scoped_npm_package():
    scoped_output = """
FAIL tests/types.test.ts
  ● Test suite failed to run

    Cannot find module '@types/node' from 'src/index.ts'
"""
    failures = JestLogParser.parse(scoped_output)
    assert len(failures) == 1
    f = failures[0]

    assert f.failure_mode == "MISSING_DEPENDENCY"
    assert f.missing_package == "@types/node"
    assert f.failing_file == "src/index.ts"


# --- 4. Multiple Failures in One Test Output ---

def test_parse_multiple_jest_failures():
    multi_output = """
FAIL tests/math.test.ts
  ● Math › addition

    expect(received).toBe(expected)

    Expected: 10
    Received: 9

      at Object.<anonymous> (tests/math.test.ts:5:10)

  ● Math › division

    ZeroDivisionError: division by zero

      at divide (src/math.ts:12:5)
      at Object.<anonymous> (tests/math.test.ts:15:10)
"""
    failures = JestLogParser.parse(multi_output)
    assert len(failures) == 2

    assert failures[0].test_name == "Math › addition"
    assert failures[0].failing_file == "tests/math.test.ts"
    assert failures[0].failing_line == 5
    assert failures[0].expected == "10"
    assert failures[0].received == "9"

    assert failures[1].test_name == "Math › division"
    assert failures[1].failing_file == "src/math.ts"
    assert failures[1].failing_line == 12


def test_fallback_parsing_without_fail_header():
    raw_trace = """
  ● StandaloneTest › testSomething

    expect(received).toEqual(expected)

    Expected: "expected value"
    Received: "actual value"

      at tests/standalone.test.ts:20:8
"""
    failures = JestLogParser.parse(raw_trace)
    assert len(failures) == 1
    assert failures[0].failing_file == "tests/standalone.test.ts"
    assert failures[0].failing_line == 20
    assert failures[0].expected == '"expected value"'
    assert failures[0].received == '"actual value"'


# --- 5. TypeScript Benchmark Scenarios Integrity Tests ---

def test_ts_scenarios_presence_and_count():
    scenarios = get_ts_scenarios()
    assert len(scenarios) == 3
    assert len(TS_ALL_SCENARIOS) == 3

    scenario_ids = {s.id for s in scenarios}
    assert scenario_ids == {"ts_off_by_one", "ts_undefined_property", "ts_type_coercion"}


def test_ts_off_by_one_scenario():
    case = get_ts_scenario("ts_off_by_one")
    assert case.id == "ts_off_by_one"
    assert case.category == "boundary_error"
    assert case.target_file.endswith(".ts")
    assert case.test_file.endswith(".test.ts")
    assert "paginateItems" in case.buggy_code
    assert "pageSize - 1" in case.buggy_code
    assert "pageSize;" in case.expected_fixed_code or "pageSize\n" in case.expected_fixed_code
    assert case.failing_symbol_name == "paginateItems"


def test_ts_undefined_property_scenario():
    case = get_ts_scenario("ts_undefined_property")
    assert case.id == "ts_undefined_property"
    assert case.category == "null_pointer"
    assert case.target_file.endswith(".ts")
    assert case.test_file.endswith(".test.ts")
    assert "getUserContactEmail" in case.buggy_code
    assert "user?.profile?.contact?.email ??" in case.expected_fixed_code
    assert case.failing_symbol_name == "getUserContactEmail"
    assert case.exception_type == "TypeError"


def test_ts_type_coercion_scenario():
    case = get_ts_scenario("ts_type_coercion")
    assert case.id == "ts_type_coercion"
    assert case.category == "type_error"
    assert case.target_file.endswith(".ts")
    assert case.test_file.endswith(".test.ts")
    assert "comparePriority" in case.buggy_code
    assert "Number(a)" in case.expected_fixed_code
    assert case.failing_symbol_name == "comparePriority"


def test_get_ts_scenario_key_error():
    with pytest.raises(KeyError):
        get_ts_scenario("non_existent_ts_scenario")
