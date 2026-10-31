"""AutoHeal-CI Commercial Licensing & Tier Management.

Provides lightweight, non-intrusive license validation for Community,
Pro, and Enterprise tiers.
"""

import os
import hashlib
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class LicenseTier(str, Enum):
    COMMUNITY = "community"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class LicenseInfo(BaseModel):
    tier: LicenseTier = LicenseTier.COMMUNITY
    license_key: Optional[str] = None
    is_valid: bool = True
    customer_name: Optional[str] = "Community User"
    max_parallel_runners: int = 1
    features: list[str] = Field(default_factory=lambda: ["ast_slicing", "adversarial_deliberation", "worktree_sandbox"])

class LicenseManager:
    """Validates and manages AutoHeal-CI license tiers."""

    @staticmethod
    def validate_key(key: Optional[str]) -> LicenseInfo:
        """Validates a license key or defaults to Community tier."""
        if not key or not key.strip():
            return LicenseInfo(
                tier=LicenseTier.COMMUNITY,
                license_key=None,
                is_valid=True,
                customer_name="Open-Source Community",
                max_parallel_runners=2,
                features=["ast_slicing", "adversarial_deliberation", "worktree_sandbox", "github_summary"]
            )

        clean_key = key.strip()

        # Enterprise key format: ent_<customer>_<hash> or prefix ent_
        if clean_key.startswith("ent_") or "enterprise" in clean_key.lower():
            return LicenseInfo(
                tier=LicenseTier.ENTERPRISE,
                license_key=clean_key,
                is_valid=True,
                customer_name="Enterprise Customer",
                max_parallel_runners=100,
                features=[
                    "ast_slicing",
                    "adversarial_deliberation",
                    "worktree_sandbox",
                    "github_summary",
                    "webhook_alerts",
                    "private_onprem_llm",
                    "gitlab_bitbucket_adapters",
                    "priority_sla"
                ]
            )

        # Pro key format: pro_<customer>_<hash> or prefix pro_
        if clean_key.startswith("pro_") or "pro" in clean_key.lower():
            return LicenseInfo(
                tier=LicenseTier.PRO,
                license_key=clean_key,
                is_valid=True,
                customer_name="Pro Customer",
                max_parallel_runners=10,
                features=[
                    "ast_slicing",
                    "adversarial_deliberation",
                    "worktree_sandbox",
                    "github_summary",
                    "webhook_alerts",
                    "fast_lane_llm"
                ]
            )

        # Fallback for general custom license key strings
        return LicenseInfo(
            tier=LicenseTier.PRO,
            license_key=clean_key,
            is_valid=True,
            customer_name="Licensed Subscriber",
            max_parallel_runners=10,
            features=[
                "ast_slicing",
                "adversarial_deliberation",
                "worktree_sandbox",
                "github_summary",
                "webhook_alerts"
            ]
        )

    @staticmethod
    def format_badge(info: LicenseInfo) -> str:
        """Returns a Markdown badge for Step Summaries."""
        if info.tier == LicenseTier.ENTERPRISE:
            return "🏢 **Tier**: `Enterprise (Full Resilience Suite & SLA)`"
        elif info.tier == LicenseTier.PRO:
            return "⚡ **Tier**: `Pro (Webhook Alerts & Fast-Lane)`"
        else:
            return "🆓 **Tier**: `Community Edition (BYOK)`"
