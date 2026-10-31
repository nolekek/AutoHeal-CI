import os
import sys
import shutil
import subprocess
import tempfile
from typing import Tuple, Optional

class SandboxHarness:
    """
    Manages an ephemeral sandbox for executing tests and verifying patches.
    Uses 'git worktree' when inside a git repository for zero-overhead isolation,
    with an automatic fallback to temp directory copy for non-git environments.
    """

    def __init__(self, repo_path: str, sandbox_dir_name: str = ".autoheal-sandbox"):
        self.repo_path = os.path.abspath(repo_path)
        self.sandbox_path = os.path.join(self.repo_path, sandbox_dir_name)
        self.is_git_repo = os.path.exists(os.path.join(self.repo_path, ".git"))
        self._is_created = False

    def create(self) -> str:
        """Creates the isolated sandbox environment."""
        self.cleanup()  # Clean up any leftover previous sandbox

        if self.is_git_repo:
            try:
                subprocess.run(
                    ["git", "worktree", "add", "--detach", self.sandbox_path, "HEAD"],
                    cwd=self.repo_path,
                    check=True,
                    capture_output=True,
                    text=True
                )
                self._is_created = True
                return self.sandbox_path
            except subprocess.CalledProcessError:
                # If git worktree fails (e.g. bare repo or permission), fallback to copy
                pass

        # Fallback: copy workspace excluding git, cache, and sandbox
        def ignore_patterns(dir, files):
            return {".git", ".autoheal-sandbox", "__pycache__", ".pytest_cache", ".venv", "venv"}

        shutil.copytree(self.repo_path, self.sandbox_path, ignore=ignore_patterns)
        self._is_created = True
        return self.sandbox_path

    def apply_patch(self, patch_diff: str) -> Tuple[bool, str]:
        """
        Applies a unified git diff patch to the sandbox.
        Returns (success: bool, output/error: str).
        """
        if not self._is_created:
            return False, "Sandbox not created"

        try:
            proc = subprocess.run(
                ["git", "apply", "--whitespace=fix", "-"],
                input=patch_diff,
                cwd=self.sandbox_path,
                capture_output=True,
                text=True
            )
            if proc.returncode == 0:
                return True, "Patch applied successfully"
            else:
                return False, f"git apply failed: {proc.stderr or proc.stdout}"
        except Exception as e:
            return False, f"Exception applying patch: {str(e)}"

    def apply_file_content(self, relative_path: str, content: str) -> Tuple[bool, str]:
        """Directly writes or overwrites file content in the sandbox."""
        if not self._is_created:
            return False, "Sandbox not created"
        try:
            target_path = os.path.join(self.sandbox_path, relative_path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True, "File updated successfully"
        except Exception as e:
            return False, str(e)

    def run_tests(self, test_selector: Optional[str] = None, timeout_seconds: int = 60) -> Tuple[bool, str]:
        """
        Executes pytest in the sandbox.
        If test_selector is provided, runs only that test. Otherwise, runs entire test suite.
        """
        if not self._is_created:
            return False, "Sandbox not created"

        cmd = [sys.executable, "-m", "pytest", "-v"]
        if test_selector:
            cmd.append(test_selector)

        try:
            proc = subprocess.run(
                cmd,
                cwd=self.sandbox_path,
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            output = (proc.stdout or "") + "\n" + (proc.stderr or "")
            return proc.returncode == 0, output.strip()
        except subprocess.TimeoutExpired:
            return False, f"Test run timed out after {timeout_seconds} seconds"
        except Exception as e:
            return False, f"Failed to execute pytest: {str(e)}"

    def cleanup(self):
        """Safely cleans up the sandbox."""
        if os.path.exists(self.sandbox_path):
            if self.is_git_repo:
                try:
                    subprocess.run(
                        ["git", "worktree", "remove", "--force", self.sandbox_path],
                        cwd=self.repo_path,
                        capture_output=True,
                        text=True
                    )
                except Exception:
                    pass
            # Force remove if directory still exists
            if os.path.exists(self.sandbox_path):
                shutil.rmtree(self.sandbox_path, ignore_errors=True)
        self._is_created = False
