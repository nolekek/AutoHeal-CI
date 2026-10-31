import os
import pytest
from unittest.mock import patch, MagicMock
from autoheal.licensing import LicenseManager, LicenseTier, LicenseInfo
from autoheal.delivery.webhook_notifier import WebhookNotifier
from autoheal.delivery.step_summary import StepSummaryGenerator

def test_license_manager_community_default():
    info = LicenseManager.validate_key(None)
    assert info.tier == LicenseTier.COMMUNITY
    assert info.is_valid is True
    assert "ast_slicing" in info.features
    badge = LicenseManager.format_badge(info)
    assert "Community Edition" in badge

def test_license_manager_pro():
    info = LicenseManager.validate_key("pro_sub_12345_token")
    assert info.tier == LicenseTier.PRO
    assert info.is_valid is True
    assert "webhook_alerts" in info.features
    badge = LicenseManager.format_badge(info)
    assert "Pro" in badge

def test_license_manager_enterprise():
    info = LicenseManager.validate_key("ent_corp_999_token")
    assert info.tier == LicenseTier.ENTERPRISE
    assert info.is_valid is True
    assert "private_onprem_llm" in info.features
    assert "gitlab_bitbucket_adapters" in info.features
    badge = LicenseManager.format_badge(info)
    assert "Enterprise" in badge

def test_webhook_notifier_not_configured():
    notifier = WebhookNotifier("")
    assert notifier.is_configured() is False
    assert notifier.send_notification(fixed=True) is False

def test_webhook_notifier_payload_builder():
    notifier = WebhookNotifier("https://hooks.slack.com/services/T00/B00/X00")
    assert notifier.is_configured() is True
    payload = notifier.build_payload(
        fixed=True,
        pr_url="https://github.com/org/repo/pull/42",
        cost_usd=0.045,
        rounds=2,
        repo="my-org/my-repo",
        branch="feature/login",
        failure_mode="LOGIC_BUG"
    )
    assert "CI Build Healed Successfully" in payload["text"]
    assert payload["attachments"][0]["color"] == "#2EB886"
    assert any("my-org/my-repo" in str(f) or "my-org/my-repo" in payload["text"] for f in payload["attachments"][0]["fields"])

def test_webhook_notifier_send_success():
    notifier = WebhookNotifier("https://hooks.slack.com/services/T00/B00/X00")
    with patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        success = notifier.send_notification(
            fixed=True,
            pr_url="https://github.com/org/repo/pull/1",
            cost_usd=0.012
        )
        assert success is True
        mock_post.assert_called_once()

def test_webhook_notifier_send_failure_handled_gracefully():
    notifier = WebhookNotifier("https://hooks.slack.com/services/T00/B00/X00")
    with patch("requests.post", side_effect=Exception("Network error")):
        success = notifier.send_notification(fixed=True)
        assert success is False

def test_step_summary_with_license_badge():
    state = {
        "status": "verified",
        "pr_url": "https://github.com/test/repo/pull/10",
        "failing_symbol_name": "calc",
        "failing_file": "calc.py",
        "failing_line": 5,
        "round_count": 1,
        "max_rounds": 3,
        "regression_suite_passed": True
    }
    lic = LicenseManager.validate_key("pro_customer_1")
    gen = StepSummaryGenerator(state=state, license_info=lic)
    md = gen.generate_summary()
    assert "Pro (Webhook Alerts & Fast-Lane)" in md
