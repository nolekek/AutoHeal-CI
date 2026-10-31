import os
import re
from typing import List, Optional
from pydantic import BaseModel, Field


class StackFrame(BaseModel):
    """Represents a single stack frame in a JavaScript / TypeScript stack trace."""
    file_path: str
    line_number: int
    column_number: Optional[int] = None
    function_name: Optional[str] = None
    code_line: Optional[str] = None
    is_project_internal: bool = True

    model_config = {"extra": "ignore"}


JestStackFrame = StackFrame


class JestFailure(BaseModel):
    """Structured representation of a Jest or Vitest test failure."""
    test_id: str                              # e.g. tests/user.test.ts > UserService › throws when user not found
    test_name: Optional[str] = None           # e.g. UserService › throws when user not found
    test_file: str                            # e.g. tests/user.test.ts
    failing_file: str                         # e.g. src/userService.ts (innermost project frame)
    failing_line: int                         # line number in failing_file
    failing_column: Optional[int] = None      # column number in failing_file
    exception_type: str = "AssertionError"    # e.g. AssertionError, TypeError, Error
    exception_message: str = ""               # e.g. expect(received).toBe(expected)
    expected_diff: Optional[str] = None       # e.g. 5
    received_diff: Optional[str] = None       # e.g. 4
    expected: Optional[str] = None            # alias for expected_diff
    received: Optional[str] = None            # alias for received_diff
    failure_mode: str = "LOGIC_BUG"           # LOGIC_BUG, MISSING_DEPENDENCY, SYNTAX_ERROR, TIMEOUT
    missing_package: Optional[str] = None     # e.g. "axios"
    stack_frames: List[StackFrame] = Field(default_factory=list)
    raw_traceback: str = ""

    model_config = {"extra": "ignore"}


class JestLogParser:
    """
    Parses Jest and Vitest test runner output into structured JestFailure representations.
    Performs call-graph resolution, node_modules filtering to pinpoint the innermost project code frame,
    assertion diff extraction, and missing npm package detection.
    """

    # Matches Jest and Vitest FAIL headers: e.g. FAIL path/to/test.ts or FAIL  path/to/test.ts > Suite > test
    FAIL_HEADER_RE = re.compile(
        r"^(?:FAIL|✕)\s+(?:(?P<flag>[A-Z]+)\s+)?(?P<header>[^\n]+)",
        re.MULTILINE
    )

    # Matches Jest bullet test headers: e.g. ● Suite › testName
    JEST_BULLET_RE = re.compile(
        r"^\s*●\s+(.*?)$",
        re.MULTILINE
    )

    # Matches Jest stack frame:
    # at fn (path:line:col) or at path:line:col
    JEST_FRAME_RE = re.compile(
        r"^\s*at\s+(?:(?P<fn>[^\(\n]+?)\s+\((?P<path_paren>(?:[a-zA-Z]:[\\/])?[^:\n\(\)]+?):(?P<line_paren>\d+):(?P<col_paren>\d+)\)|(?P<path_bare>(?:[a-zA-Z]:[\\/])?[^:\s\n\(\)]+?):(?P<line_bare>\d+):(?P<col_bare>\d+))",
        re.MULTILINE
    )

    # Matches Vitest stack frame:
    # ❯ fn path:line:col or ❯ path:line:col
    VITEST_FRAME_RE = re.compile(
        r"^\s*❯\s+(?:(?P<fn>[^\s\n\(]+(?:\s+[^\s\n\(]+)*)\s+)?\(?(?P<path>(?:[a-zA-Z]:[\\/])?[^:\s\n\(\)]+?):(?P<line>\d+):(?P<col>\d+)\)?",
        re.MULTILINE
    )

    # Matches exception type and message: e.g. TypeError: Cannot read properties of undefined
    EXCEPTION_RE = re.compile(
        r"^\s*([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)?):\s*(.*)$",
        re.MULTILINE
    )

    # Missing npm package patterns
    MISSING_PKG_PATTERNS = [
        re.compile(r"Cannot find module ['\"]([^'\"]+)['\"]"),
        re.compile(r"Cannot find package ['\"]([^'\"]+)['\"]"),
        re.compile(r"Failed to resolve import ['\"]([^'\"]+)['\"]"),
        re.compile(r"Can't resolve ['\"]([^'\"]+)['\"]"),
        re.compile(r"Module not found: Error: Can't resolve ['\"]([^'\"]+)['\"]"),
    ]

    # File from which missing import occurred
    FROM_FILE_RE = re.compile(
        r"(?:from|imported from)\s+['\"]?((?:[a-zA-Z]:[\\/])?[^'\":\n]+?\.[a-zA-Z0-9]+)['\"]?"
    )

    @classmethod
    def parse(cls, output: str, repo_path: Optional[str] = None) -> List[JestFailure]:
        """
        Parses test output containing one or more Jest or Vitest test failures.
        """
        failures: List[JestFailure] = []
        fail_matches = list(cls.FAIL_HEADER_RE.finditer(output))

        if fail_matches:
            for idx, match in enumerate(fail_matches):
                raw_header = match.group("header").strip()
                start_pos = match.end()
                end_pos = fail_matches[idx + 1].start() if idx + 1 < len(fail_matches) else len(output)
                section_content = output[start_pos:end_pos]

                parsed_section_failures = cls._parse_section(raw_header, section_content, repo_path)
                failures.extend(parsed_section_failures)
        else:
            # Fallback if no FAIL header is present (e.g. single test snippet or raw trace)
            bullet_matches = list(cls.JEST_BULLET_RE.finditer(output))
            if bullet_matches:
                for b_idx, b_match in enumerate(bullet_matches):
                    test_name = b_match.group(1).strip()
                    b_start = b_match.end()
                    b_end = bullet_matches[b_idx + 1].start() if b_idx + 1 < len(bullet_matches) else len(output)
                    block = output[b_start:b_end]
                    failure = cls._parse_single_failure("unknown_test_file", test_name, block, repo_path)
                    if failure:
                        failures.append(failure)
            else:
                fallback = cls._parse_single_failure("unknown_test_file", "unknown_test", output, repo_path)
                if fallback:
                    failures.append(fallback)

        return failures

    @classmethod
    def _parse_section(cls, raw_header: str, section_content: str, repo_path: Optional[str] = None) -> List[JestFailure]:
        """Parses a section under a FAIL line."""
        failures: List[JestFailure] = []

        # Check if the header contains a test name (common in Vitest: FAIL tests/foo.test.ts > Suite > test)
        if " > " in raw_header:
            parts = raw_header.split(" > ", 1)
            test_file = parts[0].strip().replace("\\", "/")
            test_name = parts[1].strip()
        else:
            test_file = raw_header.strip().replace("\\", "/")
            test_name = ""

        # Check for Jest bullet points: ● SuiteName › testName
        bullet_matches = list(cls.JEST_BULLET_RE.finditer(section_content))
        if bullet_matches:
            for b_idx, b_match in enumerate(bullet_matches):
                bullet_name = b_match.group(1).strip()
                b_start = b_match.end()
                b_end = bullet_matches[b_idx + 1].start() if b_idx + 1 < len(bullet_matches) else len(section_content)
                block = section_content[b_start:b_end]

                failure = cls._parse_single_failure(test_file, bullet_name, block, repo_path)
                if failure:
                    failures.append(failure)
        else:
            failure = cls._parse_single_failure(test_file, test_name, section_content, repo_path)
            if failure:
                failures.append(failure)

        return failures

    @classmethod
    def _parse_single_failure(
        cls,
        test_file: str,
        test_name: str,
        block: str,
        repo_path: Optional[str] = None
    ) -> Optional[JestFailure]:
        """Parses an individual failure block into a JestFailure instance."""
        frames = cls._extract_frames(block, repo_path)

        # Detect missing packages
        missing_pkg = None
        for pattern in cls.MISSING_PKG_PATTERNS:
            pkg_m = pattern.search(block)
            if pkg_m:
                raw_pkg = pkg_m.group(1).strip()
                if raw_pkg.startswith("@"):
                    parts = raw_pkg.split("/")
                    missing_pkg = f"{parts[0]}/{parts[1]}" if len(parts) > 1 else raw_pkg
                elif "/" in raw_pkg and not raw_pkg.startswith("."):
                    missing_pkg = raw_pkg.split("/")[0]
                else:
                    missing_pkg = raw_pkg
                break

        # Check exception details
        exc_match = cls.EXCEPTION_RE.search(block)
        exc_type = exc_match.group(1) if exc_match else ""
        exc_msg = exc_match.group(2).strip() if exc_match else ""

        # Classify failure mode
        mode = "LOGIC_BUG"
        if missing_pkg:
            mode = "MISSING_DEPENDENCY"
            if not exc_type:
                exc_type = "ModuleNotFoundError"
            if not exc_msg:
                exc_msg = f"Cannot find module '{missing_pkg}'"
        elif exc_type in ("SyntaxError", "IndentationError") or "syntaxerror" in block.lower():
            mode = "SYNTAX_ERROR"
            if not exc_type:
                exc_type = "SyntaxError"
        elif "timeout" in exc_type.lower() or "timeout" in block.lower() or "timed out" in block.lower():
            mode = "TIMEOUT"
            if not exc_type:
                exc_type = "TimeoutError"
        elif not exc_type:
            if "expect(received)" in block or "AssertionError" in block:
                exc_type = "AssertionError"
            elif "TypeError:" in block:
                exc_type = "TypeError"
            else:
                exc_type = "AssertionError"

        # If no explicit message was captured by EXCEPTION_RE, extract snippet if available
        if not exc_msg:
            first_non_empty = [line.strip() for line in block.splitlines() if line.strip() and not line.strip().startswith("at ") and not line.strip().startswith("❯ ")]
            if first_non_empty:
                exc_msg = first_non_empty[0]

        # Extract Expected and Received assertion diffs
        expected_diff, received_diff = cls._extract_assertion_diffs(block)

        # Resolve stack frames and pinpoint the innermost project-owned code frame
        internal_frames = [f for f in frames if f.is_project_internal]
        non_test_internal_frames = [f for f in internal_frames if not cls._is_test_file(f.file_path)]

        # Determine target frame:
        # If there are project source frames (outside tests and outside node_modules), that is where the code broke.
        if non_test_internal_frames:
            target_frame = non_test_internal_frames[0]
        elif internal_frames:
            target_frame = internal_frames[0]
        elif frames:
            target_frame = frames[0]
        else:
            target_frame = None

        # Resolve test file path
        resolved_test_file = test_file
        if (not resolved_test_file or resolved_test_file == "unknown_test_file"):
            test_frames = [f for f in internal_frames if cls._is_test_file(f.file_path)]
            if test_frames:
                resolved_test_file = test_frames[0].file_path
            elif target_frame:
                resolved_test_file = target_frame.file_path

        # If missing dependency, check if import origin file was named
        failing_file = target_frame.file_path if target_frame else resolved_test_file
        failing_line = target_frame.line_number if target_frame else 1
        failing_column = target_frame.column_number if target_frame else None

        if mode == "MISSING_DEPENDENCY" and (not target_frame or target_frame.is_project_internal is False):
            from_m = cls.FROM_FILE_RE.search(block)
            if from_m:
                failing_file = from_m.group(1).replace("\\", "/").strip()
                failing_line = 1

        # If nothing could be extracted, ignore non-failure blocks
        if not frames and not missing_pkg and not exc_msg and not test_name:
            return None

        # Format test_id
        if resolved_test_file and test_name:
            if test_name.startswith(resolved_test_file):
                test_id = test_name
            else:
                test_id = f"{resolved_test_file} > {test_name}"
        else:
            test_id = test_name or resolved_test_file or "unknown_test"

        return JestFailure(
            test_id=test_id,
            test_name=test_name if test_name else None,
            test_file=resolved_test_file,
            failing_file=failing_file,
            failing_line=failing_line,
            failing_column=failing_column,
            exception_type=exc_type or "AssertionError",
            exception_message=exc_msg,
            expected_diff=expected_diff,
            received_diff=received_diff,
            expected=expected_diff,
            received=received_diff,
            failure_mode=mode,
            missing_package=missing_pkg,
            stack_frames=frames,
            raw_traceback=block.strip()
        )

    @classmethod
    def _extract_frames(cls, block: str, repo_path: Optional[str] = None) -> List[StackFrame]:
        """Extracts stack frames from Jest and Vitest trace lines."""
        frames: List[StackFrame] = []

        for line in block.splitlines():
            # Match Jest: at fn (path:line:col) or at path:line:col
            jm = cls.JEST_FRAME_RE.match(line)
            if jm:
                if jm.group("path_paren"):
                    fpath = jm.group("path_paren").replace("\\", "/")
                    line_no = int(jm.group("line_paren"))
                    col_no = int(jm.group("col_paren"))
                    fn = jm.group("fn")
                else:
                    fpath = jm.group("path_bare").replace("\\", "/")
                    line_no = int(jm.group("line_bare"))
                    col_no = int(jm.group("col_bare"))
                    fn = None

                is_internal = cls._is_internal_frame(fpath, repo_path)
                frames.append(StackFrame(
                    file_path=fpath,
                    line_number=line_no,
                    column_number=col_no,
                    function_name=fn.strip() if fn else None,
                    is_project_internal=is_internal
                ))
                continue

            # Match Vitest: ❯ fn path:line:col or ❯ path:line:col
            vm = cls.VITEST_FRAME_RE.match(line)
            if vm:
                fpath = vm.group("path").replace("\\", "/")
                line_no = int(vm.group("line"))
                col_no = int(vm.group("col"))
                fn = vm.group("fn")

                is_internal = cls._is_internal_frame(fpath, repo_path)
                frames.append(StackFrame(
                    file_path=fpath,
                    line_number=line_no,
                    column_number=col_no,
                    function_name=fn.strip() if fn else None,
                    is_project_internal=is_internal
                ))
                continue

        return frames

    @classmethod
    def _extract_assertion_diffs(cls, block: str) -> tuple[Optional[str], Optional[str]]:
        """Extracts expected and received assertion diff values."""
        # 1. Standard Jest single line: Expected: 5 / Received: 4
        exp_m = re.search(r"^\s*Expected:\s*(.*?)$", block, re.MULTILINE)
        rec_m = re.search(r"^\s*Received:\s*(.*?)$", block, re.MULTILINE)
        if exp_m and rec_m:
            return exp_m.group(1).strip(), rec_m.group(1).strip()

        # 2. Vitest multiline diff:
        # - Expected:
        # 5
        # + Received:
        # 4
        vitest_diff_re = re.search(
            r"-\s*Expected:?\s*\n(.*?)\n\+\s*Received:?\s*\n(.*?)(?=\n\s*(?:❯|at\s|\d+\s*\||$))",
            block,
            re.DOTALL
        )
        if vitest_diff_re:
            return vitest_diff_re.group(1).strip(), vitest_diff_re.group(2).strip()

        # 3. Vitest inline diff: - Expected 5 / + Received 4
        inline_diff_re = re.search(
            r"-\s*Expected\s+(.*?)\n\+\s*Received\s+(.*?)(?=\n|$)",
            block
        )
        if inline_diff_re:
            return inline_diff_re.group(1).strip(), inline_diff_re.group(2).strip()

        # 4. Jest array/object diff snippet (- Expected / + Received with lines)
        jest_multi_re = re.search(
            r"-\s*Expected[^\n]*\n\+\s*Received[^\n]*\n\n(.*?)(?=\n\s*(?:at\s|\d+\s*\||\^|$))",
            block,
            re.DOTALL
        )
        if jest_multi_re:
            diff_text = jest_multi_re.group(1).strip()
            # Extract lines prefixed with - (expected) and + (received)
            exp_lines = [l[1:].strip() for l in diff_text.splitlines() if l.startswith("-") and not l.startswith("- Expected")]
            rec_lines = [l[1:].strip() for l in diff_text.splitlines() if l.startswith("+") and not l.startswith("+ Received")]
            exp_val = "\n".join(exp_lines) if exp_lines else diff_text
            rec_val = "\n".join(rec_lines) if rec_lines else diff_text
            return exp_val, rec_val

        # 5. Vitest / Chai: AssertionError: expected X to deeply equal Y or expected X to be Y
        chai_m = re.search(
            r"expected\s+(.+?)\s+to\s+(?:deeply\s+equal|be|equal)\s+(.+?)(?:\s*//.*)?$",
            block,
            re.MULTILINE
        )
        if chai_m:
            # Note: in "expected X to be Y", X is received, Y is expected
            return chai_m.group(2).strip(), chai_m.group(1).strip()

        return None, None

    @classmethod
    def _is_internal_frame(cls, file_path: str, repo_path: Optional[str] = None) -> bool:
        """Determines if a stack frame belongs to the project codebase instead of node_modules or system."""
        normalized = file_path.replace("\\", "/").lower()
        if "node_modules" in normalized:
            return False
        if "<anonymous>" in normalized:
            return False
        if normalized.startswith("node:") or "/node:" in normalized:
            return False
        if "internal/process" in normalized or "internal/modules" in normalized:
            return False
        if normalized.startswith("/usr/") or ":/program files" in normalized:
            return False
        return True

    @classmethod
    def _is_test_file(cls, path: str) -> bool:
        """Determines if a file path represents a test file."""
        normalized = path.replace("\\", "/").lower()
        if any(marker in normalized for marker in [".test.", ".spec.", "__tests__/", "/tests/", "/test/"]):
            return True
        if normalized.startswith("tests/") or normalized.startswith("test/"):
            return True
        return False
