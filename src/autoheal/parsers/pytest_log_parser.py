import re
from typing import List, Optional
from pydantic import BaseModel

class StackFrame(BaseModel):
    file_path: str
    line_number: int
    function_name: Optional[str] = None
    code_line: Optional[str] = None

class PytestFailure(BaseModel):
    test_id: str                      # e.g. tests/test_math.py::test_divide
    test_file: str                    # e.g. tests/test_math.py
    failing_file: str                 # e.g. src/math_utils.py (where error happened)
    failing_line: int                 # line number in failing_file
    exception_type: str               # e.g. ZeroDivisionError, AssertionError
    exception_message: str            # e.g. division by zero
    stack_frames: List[StackFrame] = []
    raw_traceback: str = ""

class PytestLogParser:
    """Parses pytest test runner output into structured failure representations."""

    # Regex for pytest FAILURES header
    FAILURES_SECTION_RE = re.compile(r"={3,}\s+FAILURES\s+={3,}(.*?)(={3,}|$)", re.DOTALL)
    # Regex for single failure header e.g. "____ test_division ____"
    FAILURE_HEADER_RE = re.compile(r"_{3,}\s+(.*?)\s+_{3,}")
    # Regex for stack trace file and line e.g. "path/to/file.py:42: in func_name" or "file.py:42: ExceptionType"
    FRAME_RE = re.compile(r"^([a-zA-Z0-9_\-./\\]+\.py):(\d+):(?:\s+in\s+([a-zA-Z0-9_]+))?", re.MULTILINE)
    # Regex for exception line e.g. "E   ZeroDivisionError: division by zero" or "E   AssertionError: assert 1 == 2"
    EXCEPTION_RE = re.compile(r"^E\s+([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning)?):\s*(.*)$", re.MULTILINE)

    @classmethod
    def parse(cls, output: str) -> List[PytestFailure]:
        failures: List[PytestFailure] = []
        
        # Check if FAILURES section exists
        section_match = cls.FAILURES_SECTION_RE.search(output)
        content_to_parse = section_match.group(1) if section_match else output

        # Split into individual failure blocks by "___ test_name ___"
        blocks = cls.FAILURE_HEADER_RE.split(content_to_parse)
        if len(blocks) > 1:
            # blocks will be: [preamble, test_name_1, body_1, test_name_2, body_2, ...]
            for i in range(1, len(blocks), 2):
                test_name = blocks[i].strip()
                body = blocks[i + 1] if i + 1 < len(blocks) else ""
                parsed = cls._parse_single_block(test_name, body)
                if parsed:
                    failures.append(parsed)
        else:
            # Fallback if no explicit failure headers but exceptions exist
            fallback = cls._parse_single_block("unknown_test", content_to_parse)
            if fallback:
                failures.append(fallback)

        return failures

    @classmethod
    def _parse_single_block(cls, test_name: str, block: str) -> Optional[PytestFailure]:
        frames: List[StackFrame] = []
        for match in cls.FRAME_RE.finditer(block):
            fpath = match.group(1)
            line_no = int(match.group(2))
            fn_name = match.group(3)
            frames.append(StackFrame(file_path=fpath, line_number=line_no, function_name=fn_name))

        exc_match = cls.EXCEPTION_RE.search(block)
        exc_type = exc_match.group(1) if exc_match else "AssertionError"
        exc_msg = exc_match.group(2).strip() if exc_match else ""

        if not frames:
            return None

        # The test file is usually the first frame in the stack trace
        test_file = frames[0].file_path
        # The failing file is the last frame where the crash actually occurred
        failing_frame = frames[-1]

        # Extract test selector if possible
        test_id = f"{test_file}::{test_name}" if "::" not in test_name else test_name

        return PytestFailure(
            test_id=test_id,
            test_file=test_file,
            failing_file=failing_frame.file_path,
            failing_line=failing_frame.line_number,
            exception_type=exc_type,
            exception_message=exc_msg,
            stack_frames=frames,
            raw_traceback=block.strip()
        )
