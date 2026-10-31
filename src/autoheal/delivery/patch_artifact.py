from __future__ import annotations
import os
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..agents.state import AutoHealState

DEFAULT_PATCH_DIR = ".autoheal"
DEFAULT_PATCH_FILENAME = "autoheal-fix.patch"


class PatchArtifactExporter:
    """
    Fallback patch exporter when GitHub PR creation fails or the runner repository
    is a fork / read-only repository without push or pull request permissions.
    
    Exports the verified unified diff to `.autoheal/autoheal-fix.patch` with
    ready-to-use apply instructions: `curl ... | git apply`.
    """

    def __init__(self, repo_path: str = "."):
        self.repo_path = os.path.abspath(repo_path)
        self.default_dir = os.path.join(self.repo_path, DEFAULT_PATCH_DIR)

    def get_default_patch_path(self, filename: str = DEFAULT_PATCH_FILENAME) -> str:
        """Returns the absolute path to the default patch artifact."""
        return os.path.join(self.default_dir, filename)

    def export(
        self,
        patch_diff: str,
        output_path: Optional[str] = None,
        filename: str = DEFAULT_PATCH_FILENAME
    ) -> str:
        """
        Exports the given unified diff string to a patch file.
        
        Args:
            patch_diff: The unified diff content.
            output_path: Optional custom destination file path.
            filename: Patch file name if output_path is not specified.
            
        Returns:
            The path of the exported patch file (relative to repo_path if inside repo).
        """
        if not patch_diff or not patch_diff.strip():
            raise ValueError("Cannot export empty patch diff.")

        target_file = output_path or os.path.join(self.default_dir, filename)
        target_dir = os.path.dirname(os.path.abspath(target_file))
        os.makedirs(target_dir, exist_ok=True)

        with open(target_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(patch_diff.strip() + "\n")

        # Return clean relative path if within repo_path, otherwise absolute path
        try:
            rel = os.path.relpath(target_file, self.repo_path)
            return rel.replace("\\", "/")
        except ValueError:
            return target_file

    def export_from_state(
        self,
        state: AutoHealState,
        output_path: Optional[str] = None,
        filename: str = DEFAULT_PATCH_FILENAME
    ) -> Optional[str]:
        """
        Exports the patch diff from an AutoHealState dictionary.
        Returns None if state has no valid patch_diff.
        """
        patch_diff = state.get("patch_diff")
        if not patch_diff or not patch_diff.strip():
            return None

        # Prefer state's repo_path if available
        repo = state.get("repo_path")
        if repo:
            self.repo_path = os.path.abspath(repo)
            self.default_dir = os.path.join(self.repo_path, DEFAULT_PATCH_DIR)

        return self.export(patch_diff, output_path=output_path, filename=filename)

    def get_apply_instructions(
        self,
        patch_path: Optional[str] = None,
        patch_url: Optional[str] = None
    ) -> str:
        """
        Returns ready-to-run terminal instructions for developers to apply the fix.
        Includes both `curl ... | git apply` and local checkout instructions.
        """
        rel_path = patch_path or f"{DEFAULT_PATCH_DIR}/{DEFAULT_PATCH_FILENAME}"
        curl_target = patch_url or "<patch-artifact-url>"

        return (
            f"# To apply this patch locally from checkout:\n"
            f"git apply {rel_path}\n\n"
            f"# Or download and apply via curl:\n"
            f"curl -sL \"{curl_target}\" | git apply"
        )

    def get_instructions_markdown(
        self,
        patch_path: Optional[str] = None,
        patch_url: Optional[str] = None
    ) -> str:
        """Returns Markdown-formatted instructions for GitHub Step Summary and PR notes."""
        rel_path = patch_path or f"{DEFAULT_PATCH_DIR}/{DEFAULT_PATCH_FILENAME}"
        curl_target = patch_url or "<patch-artifact-url>"

        return f"""### 📦 Apply Patch Locally

Pull Request creation was skipped or repository is a fork without write permissions.
The verified patch artifact has been exported to `{rel_path}`.

```bash
# 1. Download and apply directly via curl:
curl -sL "{curl_target}" | git apply

# 2. Or apply from your local repository clone:
git apply {rel_path}
```
"""
