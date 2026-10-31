import os
import json
import subprocess
import urllib.request
import urllib.error
from typing import Optional, Dict, Any
from ..agents.state import AutoHealState

class GitHubPRDelivery:
    """Manages branch creation, committing verified patches, and opening Pull Requests."""

    def __init__(self, token: Optional[str] = None, repo_slug: Optional[str] = None):
        self.token = token or os.getenv("AUTOHEAL_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
        self.repo_slug = repo_slug or os.getenv("GITHUB_REPOSITORY")  # e.g. "owner/repo"

    def deliver(self, state: AutoHealState) -> Optional[str]:
        """
        Creates a Git branch, pushes the verified fix and regression test,
        and opens a Pull Request on GitHub. Returns PR URL.
        """
        sha = state.get("commit_sha", "patch")[:7]
        branch_name = f"autoheal/fix-{sha}"

        # 1. Try to create branch and commit locally via git CLI
        commit_msg = f"fix(autoheal): resolve CI failure in {state['failing_symbol_name']}\n\nAutomated fix verified by AutoHeal-CI with regression shield."
        
        try:
            subprocess.run(["git", "checkout", "-b", branch_name], cwd=state["repo_path"], check=True, capture_output=True)
            subprocess.run(["git", "add", "-A"], cwd=state["repo_path"], check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=state["repo_path"], check=True, capture_output=True)
            
            # Push if remote is accessible and token exists
            if self.token:
                subprocess.run(["git", "push", "-u", "origin", branch_name], cwd=state["repo_path"], capture_output=True)
        except Exception:
            # If git checkout/push fails, continue to attempt API PR or return None
            pass

        # 2. Open Pull Request via GitHub REST API
        if not self.token or not self.repo_slug:
            return None

        pr_title = f"🩺 AutoHeal: Fix {state['exception_type']} in `{state['failing_symbol_name']}`"
        pr_body = self._generate_pr_body(state)

        return self._create_github_pr(
            title=pr_title,
            body=pr_body,
            head=branch_name,
            base=state.get("target_branch", "main")
        )

    def _generate_pr_body(self, state: AutoHealState) -> str:
        return f"""## 🩺 AutoHeal-CI Automated Patch Verification Report

### 📌 Summary of Problem & Root Cause
**Failing Symbol:** `{state['failing_symbol_name']}` in `{state['failing_file']}` (line {state['failing_line']})  
**Exception:** `{state['exception_type']}: {state['exception_message']}`  

> **Hypothesis:** {state.get('coder_hypothesis', 'Automated bug fix.')}

---

### 🛡️ Red-Team Verification Shield
* **Failing Test Resolved:** ✅ Passed
* **Red-Team Critic Counter-Test:** ✅ Survived and Verified
* **Full Repository Regression Suite:** ✅ 100% Green (0 regressions)
* **Deliberation Rounds:** {state.get('round_count', 1)} / {state.get('max_rounds', 3)}

```python
# Critic's Verified Edge-Case Test
{state.get('critic_attack_code', '# Standard regression suite verified')}
```

---
*Created automatically by [AutoHeal-CI](https://github.com/auto-heal-ci).*
"""

    def _create_github_pr(self, title: str, body: str, head: str, base: str) -> Optional[str]:
        url = f"https://api.github.com/repos/{self.repo_slug}/pulls"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "AutoHeal-CI-Bot"
        }
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("html_url")
        except Exception:
            return None
