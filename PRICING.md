# 💎 AutoHeal-CI — Pricing & Commercial Plans

> **Stop wasting \$1,200+/month per developer on trivial CI triage.**  
> AutoHeal-CI fixes broken builds autonomously in 3–15 seconds with verified regression shielding.

---

## 📊 The ROI Equation: Why Engineering Teams Pay for AutoHeal-CI

| Metric | Without AutoHeal-CI | With AutoHeal-CI | Net Gain per 10 Devs |
| :--- | :--- | :--- | :--- |
| **Average CI Failures / Week** | ~20 failures across PRs | ~20 failures | Handled automatically |
| **Developer MTTR (Time to Fix)** | 25–45 min per failure | **3–15 seconds** | **~10 hours saved / week** |
| **Context Switching Penalty** | 23 min to regain focus | 0 min (PR ready to merge) | Continuous Flow State |
| **Monthly Engineering Cost** | \$100/hr × 40 hrs = **\$4,000/mo** | \$39/mo Pro or Free BYOK | **\$3,961 / mo Net Savings** |
| **Annualized ROI** | Baseline | **> 100x return on investment** | **\$47,500+ / year** |

---

## 🎯 Tier Comparison Matrix (Good-Better-Best)

| Feature | 🆓 Community (Open Source) | ⚡ Pro (Fast-Moving Teams) | 🏢 Enterprise (Scale & Security) |
| :--- | :---: | :---: | :---: |
| **Price** | **\$0 / Free Forever** | **\$39 / month**<br>*(or \$390/year — 2 months free)* | **\$499 / month**<br>*(custom annual contracts)* |
| **Ideal For** | Solo hackers & Open-Source | High-velocity product teams (5–30 devs) | Scaleups, Fintech, Healthtech (30+ devs) |
| **LLM Key Setup** | BYOK (Your OpenAI/Claude Key) | **Zero-Config Hosted High-Speed Proxy** *(or BYOK)* | **Private On-Prem (Ollama / vLLM / Bedrock / Azure)** |
| **Supported Languages** | Python, TypeScript, JavaScript | Python, TypeScript, JavaScript, Go *(Beta)* | All + Custom Grammar Plugins |
| **Deliberation Speed** | Standard | **Priority Fast-Lane LLM Routing** | Dedicated LLM Cluster / VPC |
| **Regression Shielding** | Git Worktree Sandbox | Git Worktree Sandbox | Worktree + Custom Integration Staging |
| **Team Notifications** | GitHub Step Summary & PR | **Instant Slack / Discord / Teams Alerts** | Custom Enterprise Webhooks & PagerDuty |
| **Monthly Fixes** | Unlimited (BYOK) | Unlimited Fixes | Unlimited Fixes |
| **Platform Support** | GitHub Actions | GitHub Actions | **GitHub Actions, GitLab CI, Bitbucket, Jenkins** |
| **Security & Compliance** | Client-side only | Zero data retention | **Air-gapped deployment, SOC2 readiness, NDA** |
| **Support & SLA** | GitHub Community Discussions | Priority Email & Discord (24h turnaround) | **Dedicated Slack channel & 99.9% Uptime SLA** |

---

## 🚀 How to Upgrade

### ⚡ Upgrading to Pro (\$39/mo)

We support multiple flexible checkout methods for international and local teams:

1. **💳 Bank Cards (Visa / Mastercard / MIR worldwide)**: Instant checkout via [Lava.top AutoHeal-CI Storefront](https://app.lava.top/products/03e25483-654d-4e28-8231-2a5e5cc8b62a) (instant digital license key download).
2. **🪙 Cryptocurrency (USDT TRC20 / BEP20 / TON / BTC)**: Instant key delivery with zero payment processor friction via [Telegram @nolekek](https://t.me/nolekek).
3. **🏢 Corporate Invoicing (B2B Wire / Безналичный расчет)**: Available for companies and startups (ООО / ИП / International wire) with official service contracts, invoices, and accounting closing documents.

After payment, you will receive your `AUTOHEAL_LICENSE_KEY`. Add the secret to your GitHub Repository Settings (`Settings -> Secrets and variables -> Actions`):
```yaml
- name: AutoHeal-CI Pro
  if: failure()
  uses: nolekek/AutoHeal-CI@v1
  with:
    license_key: ${{ secrets.AUTOHEAL_LICENSE_KEY }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }} # Optional Slack/Discord alert
```

### 🏢 Inquiring about Enterprise (\$499/mo)
For private on-premise deployments (GitLab CI, self-hosted LLMs, air-gapped VPCs, or custom SLAs):
* 📧 Email: **enterprise@autoheal-ci.dev** or **sales@autoheal-ci.dev**
* 💬 Book a 15-minute architectural walkthrough with the lead engineer.
* 📄 Standard MSA, Security Whitepaper, and SOC2 compliance addendum available upon request.

---

## 🛡️ 30-Day Risk-Free Guarantee
Try AutoHeal-CI Pro on your active repositories for 30 days. If your team does not save at least **10x** the subscription cost in saved engineering hours, email us for a **100% unconditional refund** within 30 days. Zero risk, zero hassle.
