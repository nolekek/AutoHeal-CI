"""AutoHeal-CI Team Webhook Notification Delivery (Slack, Discord, MS Teams).

Enables instant enterprise alerts directly into team communication channels
when AutoHeal heals a broken build.
"""

import json
import logging
from typing import Optional, Any
import requests

logger = logging.getLogger(__name__)

class WebhookNotifier:
    """Delivers rich Slack / Discord / Teams webhook notifications."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url.strip() if webhook_url else None

    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("http"))

    def build_payload(
        self,
        fixed: bool,
        pr_url: Optional[str] = None,
        patch_path: Optional[str] = None,
        cost_usd: float = 0.0,
        rounds: int = 1,
        repo: Optional[str] = None,
        branch: Optional[str] = None,
        failure_mode: Optional[str] = None
    ) -> dict[str, Any]:
        """Constructs an enterprise Slack-compatible webhook message."""
        status_emoji = "🎉" if fixed else "⚠️"
        status_text = "CI Build Healed Successfully" if fixed else "Self-Healing Deliberation Incomplete"
        color = "#2EB886" if fixed else "#E01E5A"

        repo_info = f"{repo} ({branch})" if repo and branch else (repo or "Repository")
        header = f"{status_emoji} *[AutoHeal-CI]* {status_text} in `{repo_info}`"

        fields = [
            {"title": "Deliberation Rounds", "value": f"{rounds} rounds", "short": True},
            {"title": "LLM Compute Cost", "value": f"${cost_usd:.4f} USD", "short": True},
        ]

        if failure_mode:
            fields.append({"title": "Failure Mode", "value": f"`{failure_mode}`", "short": True})

        if pr_url:
            fields.append({"title": "Pull Request", "value": f"<{pr_url}|View Fix PR>", "short": True})
        elif patch_path:
            fields.append({"title": "Fallback Patch", "value": f"`{patch_path}`", "short": True})

        payload = {
            "text": header,
            "attachments": [
                {
                    "color": color,
                    "title": "Autonomous Multi-Agent Deliberation Report",
                    "fields": fields,
                    "footer": "AutoHeal-CI Enterprise • AST Slicing & Regression Shield",
                    "ts": None
                }
            ]
        }
        return payload

    def send_notification(
        self,
        fixed: bool,
        pr_url: Optional[str] = None,
        patch_path: Optional[str] = None,
        cost_usd: float = 0.0,
        rounds: int = 1,
        repo: Optional[str] = None,
        branch: Optional[str] = None,
        failure_mode: Optional[str] = None,
        timeout: int = 5
    ) -> bool:
        """Sends the notification to the configured webhook URL. Returns True if successful."""
        if not self.is_configured():
            return False

        payload = self.build_payload(
            fixed=fixed,
            pr_url=pr_url,
            patch_path=patch_path,
            cost_usd=cost_usd,
            rounds=rounds,
            repo=repo,
            branch=branch,
            failure_mode=failure_mode
        )

        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout
            )
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.warning(f"Failed to deliver AutoHeal webhook notification: {e}")
            return False
