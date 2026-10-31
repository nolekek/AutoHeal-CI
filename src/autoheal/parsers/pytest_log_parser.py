import os
import re
from typing import List, Optional
from pydantic import BaseModel

class StackFrame(BaseModel):
    file_path: str
    line_number: int
    function_name: Optional[str] = None
    code_line: Optional[str] = None
    is_project_internal: bool = True

class PytestFailure(BaseModel):
    test_id: str                              # e.g. tests/test_math.py::test_divide
    test_file: str                            # e.g. tests/test_math.py
    failing_file: str                         # e.g. src/math_utils.py (innermost project frame)
    failing_line: int                         # line number in failing_file
    exception_type: str                       # e.g. ZeroDivisionError, AssertionError
    exception_message: str                    # e.g. division by zero
    failure_mode: str = "LOGIC_BUG"           # LOGIC_BUG, MISSING_DEPENDENCY, SYNTAX_ERROR, TIMEOUT
    missing_package: Optional[str] = None     # if ModuleNotFoundError
    stack_frames: List[StackFrame] = []
    raw_traceback: str = ""

class PytestLogParser:
    """
    Parses pytest test runner output into structured failure representations
    with multi-frame call-graph resolution and pre-flight failure classification.
    """

    FAILURES_SECTION_RE = re.compile(r"={3,}\s+FAILURES\s+={3,}(.*?)(={3,}|$)", re.DOTALL)
    ERRORS_SECTION_RE = re.compile(r"={3,}\s+ERRORS\s+={3,}(.*?)(={3,}|$)", re.DOTALL)
    FAILURE_HEADER_RE = re.compile(r"_{3,}\s+(.*?)\s+_{3,}")
    FRAME_RE = re.compile(r"^([a-zA-Z0-9_\-./\\]+\.py):(\d+):(?:\s+in\s+([a-zA-Z0-9_]+))?", re.MULTILINE)
    EXCEPTION_RE = re.compile(r"^E\s+([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning)?):\s*(.*)$", re.MULTILINE)
    
    # Missing package detector
    MISSING_PKG_RE = re.compile(r"No module named ['\"]([^'\"]+)['\"]")

    @classmethod
    def parse(cls, output: str, repo_path: Optional[str] = None) -> List[PytestFailure]:
        failures: List[PytestFailure] = []
        
        # Combine FAILURES and ERRORS sections
        sections = []
        f_match = cls.FAILURES_SECTION_RE.search(output)
        if f_match:
            sections.append(f_match.group(1))
        e_match = cls.ERRORS_SECTION_RE.search(output)
        if e_match:
            sections.append(e_match.group(1))

        content_to_parse = "\n".join(sections) if sections else output

        # Split by failure headers
        blocks = cls.FAILURE_HEADER_RE.split(content_to_parse)
        if len(blocks) > 1:
            for i in range(1, len(blocks), 2):
                test_name = blocks[i].strip()
                body = blocks[i + 1] if i + 1 < len(blocks) else ""
                parsed = cls._parse_single_block(test_name, body, repo_path)
                if parsed:
                    failures.append(parsed)
        else:
            fallback = cls._parse_single_block("unknown_test", content_to_parse, repo_path)
            if fallback:
                failures.append(fallback)

        return failures

    @classmethod
    def _parse_single_block(cls, test_name: str, block: str, repo_path: Optional[str] = None) -> Optional[PytestFailure]:
        frames: List[StackFrame] = []
        for match in cls.FRAME_RE.finditer(block):
            fpath = match.group(1).replace("\\", "/")
            line_no = int(match.group(2))
            fn_name = match.group(3)

            is_internal = cls._is_internal_frame(fpath, repo_path)
            frames.append(StackFrame(
                file_path=fpath,
                line_number=line_no,
                function_name=fn_name,
                is_project_internal=is_internal
            ))

        exc_match = cls.EXCEPTION_RE.search(block)
        exc_type = exc_match.group(1) if exc_match else "AssertionError"
        exc_msg = exc_match.group(2).strip() if exc_match else ""

        if not frames:
            return None

        # Determine failure mode
        mode = "LOGIC_BUG"
        missing_pkg = None

        if exc_type in ("ModuleNotFoundError", "ImportError"):
            mode = "MISSING_DEPENDENCY"
            pkg_m = cls.MISSING_PKG_RE.search(exc_msg)
            if pkg_m:
                missing_pkg = pkg_m.group(1).split(".")[0]
        elif exc_type in ("SyntaxError", "IndentationError", "TabError"):
            mode = "SYNTAX_ERROR"
        elif "timed out" in exc_msg.lower() or "timeout" in exc_type.lower():
            mode = "TIMEOUT"

        # The test file is usually the first internal frame
        internal_frames = [f for f in frames if f.is_project_internal]
        test_file = internal_frames[0].file_path if internal_frames else frames[0].file_path

        # Innermost internal frame is where the actual project code failed
        # (skipping external site-packages/standard library frames)
        target_frame = internal_frames[-1] if internal_frames else frames[-1]

        # Extract test selector
        test_id = f"{test_file}::{test_name}" if "::" not in test_name else test_name

        return PytestFailure(
            test_id=test_id,
            test_file=test_file,
            failing_file=target_frame.file_path,
            failing_line=target_frame.line_number,
            exception_type=exc_type,
            exception_message=exc_msg,
            failure_mode=mode,
            missing_package=missing_pkg,
            stack_frames=frames,
            raw_traceback=block.strip()
        )

    @classmethod
    def _is_internal_frame(cls, file_path: str, repo_path: Optional[str] = None) -> bool:
        normalized = file_path.lower()
        # External markers
        if any(marker in normalized for marker in ["site-packages", "dist-packages", "/lib/python", "\\lib\\python"]):
            return False
        if normalized.startswith("/usr/") or ":/program files" in normalized:
            return False
        return True
