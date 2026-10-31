import os
import shutil
import tempfile
import pytest
from autoheal.sandbox.git_worktree import SandboxHarness

def test_sandbox_create_and_run():
    # Create a temporary workspace with a passing test
    temp_dir = tempfile.mkdtemp(prefix="autoheal_test_repo_")
    try:
        tests_dir = os.path.join(temp_dir, "tests")
        os.makedirs(tests_dir, exist_ok=True)
        
        test_file = os.path.join(tests_dir, "test_dummy.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("def test_ok():\n    assert 1 + 1 == 2\n")

        harness = SandboxHarness(repo_path=temp_dir)
        sandbox_path = harness.create()

        assert os.path.exists(sandbox_path)
        assert os.path.exists(os.path.join(sandbox_path, "tests", "test_dummy.py"))

        # Run test inside sandbox
        success, output = harness.run_tests()
        assert success is True
        assert "passed" in output.lower()

        # Cleanup
        harness.cleanup()
        assert not os.path.exists(sandbox_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
