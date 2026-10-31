import difflib
from typing import Optional

class UnifiedDiffGenerator:
    """Generates standard unified git diffs from original and modified file contents."""

    @staticmethod
    def create_unified_diff(
        original_content: str,
        modified_content: str,
        file_path: str
    ) -> str:
        """
        Creates a git-compatible unified diff header and hunks.
        """
        orig_lines = original_content.splitlines(keepends=True)
        mod_lines = modified_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            orig_lines,
            mod_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            n=3  # Standard 3 lines of context
        )
        return "".join(diff)

    @staticmethod
    def replace_symbol_in_file(
        full_file_content: str,
        original_symbol_slice: str,
        revised_symbol_slice: str
    ) -> str:
        """
        Replaces the exact symbol slice in the file content, preserving
        all existing surrounding indentation, comments, and structure.
        """
        # Exact match
        if original_symbol_slice in full_file_content:
            return full_file_content.replace(original_symbol_slice, revised_symbol_slice, 1)

        # Normalized stripped match fallback
        orig_stripped = original_symbol_slice.strip()
        rev_stripped = revised_symbol_slice.strip()

        if orig_stripped in full_file_content:
            return full_file_content.replace(orig_stripped, rev_stripped, 1)

        # Line-by-line fallback
        orig_lines = [line.strip() for line in original_symbol_slice.splitlines() if line.strip()]
        if not orig_lines:
            return full_file_content

        file_lines = full_file_content.splitlines()
        first_line = orig_lines[0]
        last_line = orig_lines[-1]

        start_idx = None
        end_idx = None

        for idx, line in enumerate(file_lines):
            if start_idx is None and first_line in line:
                start_idx = idx
            if start_idx is not None and last_line in line:
                end_idx = idx + 1
                break

        if start_idx is not None and end_idx is not None:
            # Preserve leading indentation of the first line
            leading_ws = len(file_lines[start_idx]) - len(file_lines[start_idx].lstrip())
            indent = " " * leading_ws
            indented_revised = "\n".join(
                indent + line if line.strip() else "" for line in revised_symbol_slice.splitlines()
            )
            new_lines = file_lines[:start_idx] + [indented_revised] + file_lines[end_idx:]
            return "\n".join(new_lines) + "\n"

        return full_file_content
