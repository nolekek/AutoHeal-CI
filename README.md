# 🩺 AutoHeal-CI

> **Autonomous Multi-Agent CI/CD Self-Healing Bot with AST-Aware Slicing, Isolated Sandbox Verification & Regression Shielding.**

<p align="left">
  <strong>English</strong> | <a href="README_RU.md">Русский</a>
</p>

[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-AutoHeal--CI-blue.svg?logo=github)](https://github.com/marketplace/actions/autoheal-ci)
[![Test Suite](https://img.shields.io/badge/Tests-105%20Passed%20(100%25)-brightgreen.svg)](#-testing-and-verification)
[![Supported Languages](https://img.shields.io/badge/Languages-Python%20%7C%20TypeScript%20%7C%20JavaScript-blue.svg)](#-multi-language--test-runners)
[![Test Runners](https://img.shields.io/badge/Runners-pytest%20%7C%20Jest%20%7C%20Vitest-orange.svg)](#-quickstart-in-github-actions)
[![Benchmark Suite](https://img.shields.io/badge/SWE--Bench%20Mini-100%25%20Verified%20(9%2F9)-brightgreen.svg)](#-swe-bench-mini-benchmark)
[![AST Engine](https://img.shields.io/badge/AST%20Parser-Tree--sitter-blue.svg)](#1-ast--symbolic-call-graph-slicing-tree-sitter)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-1--Click%20Workflow-purple.svg)](#-1-click-live-cloud-demo)
[![Platform](https://img.shields.io/badge/Platform-GitHub%20Actions%20Runner-black.svg)](#-quickstart-in-github-actions)
[![Pricing](https://img.shields.io/badge/Plans-Free%20%7C%20Pro%20%7C%20Enterprise-success.svg)](PRICING.md)
[![Sponsor](https://img.shields.io/badge/Sponsor-GitHub%20%7C%20Boosty-ff69b4.svg)](.github/FUNDING.yml)
[![License](https://img.shields.io/badge/License-Apache--2.0%20%7C%20Commercial-blueviolet.svg)](COMMERCIAL.md)

---

## 🖥️ Live Terminal Showcase

```text
  ╔═══════════════════════════════════════════════════════════════════════╗
  ║            🩺 AutoHeal-CI: Autonomous CI/CD Self-Healing              ║
  ║      AST Slicing • Adversarial Red-Team • Git Worktree Shield         ║
  ╚═══════════════════════════════════════════════════════════════════════╝

❌ CI Test Failure Detected: tests/test_calculator.py::test_compute_average_empty
   Origin: calculator.py:10 (ZeroDivisionError: division by zero)

🔍 [1/4] Parsing Failure Log...
   ├─ Failure Mode: LOGIC_BUG
   └─ Traceback: Frame 3 in src/calculator.py:10 (compute_average)

🌳 [2/4] Tree-sitter AST Slicing...
   ├─ Target Function: `compute_average` (38 tokens extracted, not 500 lines)
   ├─ Sibling Signatures: [calculate_discount(price, discount_percent)]
   └─ Token Efficiency: 94.2% context savings vs whole-file prompting

⚔️ [3/4] Adversarial Deliberation (Coder vs Red-Team Critic)...
   ├─ Round 1: Lead Coder proposes guard `if not scores: return 0.0`
   │  └─ Git Worktree Sandbox (.autoheal-sandbox): Failing test PASSED!
   ├─ Critic Attack: Red-Team generates test with None & empty generator
   │  └─ Attack Result: Coder refines validation to handle falsy collections
   └─ Round 2: Red-Team Critic votes APPROVED.

🛡️ [4/4] Verification & Delivery...
   ├─ Regression Shield: 100% Green (105/105 tests pass in sandbox)
   ├─ Fallback Artifact: Exported to .autoheal/autoheal-fix.patch
   └─ GitHub Pull Request: Opened #42 (autoheal/fix-compute-average)

🎉 All tests green! Total repair time: 3.4s • LLM Cost: $0.031
```

---

## 📌 About the Project

In modern engineering teams, up to **35% of senior developer time** is lost to routine CI/CD failures: triaging flaky tests, deciphering noisy stack traces, applying trivial patches, and waiting for pipelines to re-run.

**AutoHeal-CI** is an autonomous multi-agent self-healing system designed to run directly inside your GitHub Actions runner on `if: failure()`.

It isolates the exact root cause using **Tree-sitter AST slicing**, reproduces the bug in an ephemeral **`git worktree` sandbox**, runs an internal adversarial debate (**Lead Coder vs Red-Team Critic**), and submits a verified Pull Request with a regression shield **before your engineers even open the CI logs**.

---

## 🚀 1-Click Live Cloud Demo

You can test AutoHeal-CI directly in the cloud without cloning the repo or providing API keys:

1. Navigate to the [**Actions**](../../actions/workflows/demo-live.yml) tab of this repository.
2. Select the **"AutoHeal-CI Live Cloud Demo"** workflow.
3. Click **"Run workflow"** and choose a scenario:
   * `python-zero-division` — autonomous ZeroDivisionError repair;
   * `typescript-undefined-dereference` — TypeScript TypeError / optional chaining repair;
   * `swe-bench-mini-suite` — full synthetic benchmark evaluation.
4. Inspect the **GitHub Step Summary** with interactive Mermaid deliberation diagrams and verified diff artifacts!

---

## ⚡ Key Engineering Advantages

| Metric | Traditional AI (Copilot / Chat) | Heavy Cloud SaaS (Swe-agent, etc.) | 🩺 **AutoHeal-CI** |
| :--- | :--- | :--- | :--- |
| **Integration Point** | IDE (Engineer waits and clicks) | 3rd-party SaaS (Sends code to cloud) | **In-Runner Action (`if: failure()`)** |
| **Data Privacy** | Code sent to external servers | Grants full access to private repos | **Zero Data Leakage (Local-First BYOK)** |
| **Context Window** | Entire files (2k–10k tokens) | Entire repo (Heavy RAG embeddings) | **Tree-sitter AST (<2,000 tokens)** |
| **Patch Verification**| Unverified (Hallucination risk) | Heavy Docker spins (minutes) | **Git Worktree Sandbox (1–2 seconds)** |
| **Overfitting Guard** | None | Single agent (High overfitting rate)| **Adversarial Red-Team Critic Loop** |
| **Regression Shield** | Manual testing required | Slow manual full-suite runs | **Automated Full-Suite Regression Shield** |

---

## 🌐 Multi-Language & Test Runners

AutoHeal-CI natively supports two primary modern software ecosystems:

### 🐍 Python (`pytest`)
* **AST Analysis**: `tree-sitter-python` — extracts functions, `async def`, decorators, and class signatures.
* **Failure Classifier**: `LOGIC_BUG`, `MISSING_DEPENDENCY`, `SYNTAX_ERROR`, `TIMEOUT`.
* **Dependency Healer**: Automatically resolves `ModuleNotFoundError` and patches `pyproject.toml`.

### 🟦 TypeScript / JavaScript (`jest` & `vitest`)
* **AST Analysis**: `tree-sitter-typescript` — arrow functions, class methods, interfaces, type aliases, and JSX/TSX.
* **Jest/Vitest Parser**: Strips `node_modules/` noise, parses assertion diffs (`Expected / Received`), and resolves root-cause call sites.

---

## 🚀 Quickstart in GitHub Actions

### 1. Add to a Python Repository
Add to your `.github/workflows/ci.yml`:

```yaml
name: CI Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write

    steps:
      - name: Checkout Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Dependencies
        run: pip install -e .[dev]

      - name: Run Tests
        run: pytest -v

      # Triggers ONLY when previous test step fails
      - name: AutoHeal-CI Self-Healing Bot
        if: failure()
        uses: nolekek/AutoHeal-CI@v1
        with:
          api_key: ${{ secrets.OPENAI_API_KEY }} # or ANTHROPIC_API_KEY / GEMINI_API_KEY
          model: 'gpt-4o'
          max_rounds: '3'
          create_pr: 'true'
          webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }} # Optional Slack/Teams alert
```

### 2. Add to a TypeScript / Node.js Repository

```yaml
      - name: Run Tests
        run: npm test

      # Triggers ONLY when tests fail
      - name: AutoHeal-CI Self-Healing Bot
        if: failure()
        uses: nolekek/AutoHeal-CI@v1
        with:
          api_key: ${{ secrets.OPENAI_API_KEY }}
          test_command: 'npm test'
          create_pr: 'true'
```

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    Failure["CI Test Failure\n(pytest / jest exit code != 0)"] --> Parser["Stacktrace Log Parser\n(Multi-frame call-graph resolver)"]
    
    subgraph SlicingEngine ["Symbolic & AST Slicing Engine"]
        TreeSitter["Tree-sitter Python / TypeScript Slicer\n- Target function AST\n- Enclosing class / interface signatures\n- Failing test AST (<2k tokens)"]
    end

    subgraph MultiAgentCore ["Adversarial Deliberation Loop (LangGraph)"]
        Coder["Lead Coder Agent\n(Generates hypothesis & surgical patch)"]
        Critic["Red-Team Critic Agent\n(Generates breaking edge-case attack tests)"]
        WorktreeHarness["Git Worktree Sandbox (.autoheal-sandbox)\n(Zero-overhead runner VM isolation)"]
    end

    subgraph ShieldStage ["Verification & Delivery"]
        RegressionShield["Regression Suite Shield\n(Verifies 100% existing tests remain green)"]
        PRDelivery["GitHub PR & Summary Creator\n(Opens autoheal/fix-<sha> PR + Step Summary)"]
    end

    Failure --> Parser
    Parser --> TreeSitter
    TreeSitter --> Coder
    
    Coder --> WorktreeHarness
    WorktreeHarness -->|Test Passes| Critic
    WorktreeHarness -->|Test Fails| Coder
    
    Critic --> WorktreeHarness
    WorktreeHarness -->|Critic Caught Edge Case| Coder
    WorktreeHarness -->|Critic Test Green| RegressionShield
    
    RegressionShield -->|Regressions Found| Coder
    RegressionShield -->|All Green| PRDelivery
```

---

## 📊 SWE-Bench Mini Benchmark

AutoHeal-CI has been verified against a suite of 9 real-world defect scenarios (6 Python + 3 TypeScript):

| ID | Scenario | Language | Defect Category | Rounds | Result | Overfitting Protection |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| `off_by_one` | Substring search & index bounds | Python | Logic | 1 | ✅ PASS | Critic Test Green |
| `none_deref` | Unchecked `None` parameter | Python | Runtime | 1 | ✅ PASS | Critic Attack Resisted |
| `key_error_nested` | Nested JSON payload extraction | Python | Robustness | 1 | ✅ PASS | Critic Test Green |
| `zero_division` | Empty collection average computation | Python | Edge Case | 1 | ✅ PASS | Guard Verified |
| `missing_dependency` | Missing `yaml` package | Python | Environment | 0 | ✅ PASS | Auto-healed `pyproject.toml` |
| `float_precision` | Floating-point delta comparison | Python | Math | 1 | ✅ PASS | Critic Test Green |
| `ts_undefined_deref` | Access to optional property | TypeScript | Runtime | 1 | ✅ PASS | Optional Chaining `?.` |
| `ts_array_index_oob` | Array out of bounds in utility | TypeScript | Logic | 1 | ✅ PASS | Boundary Guard Verified |
| `ts_falsy_empty_string` | Falsy empty string in validator | TypeScript | Validation | 1 | ✅ PASS | Critic Test Green |

**Summary:** **9/9 (100% Pass Rate)** • Median repair latency: **1.8 seconds** • Token cost: **~$0.02 - $0.04** per repair.

---

## 💻 Local CLI Execution

```bash
# Clone and install in development mode
git clone https://github.com/nolekek/AutoHeal-CI.git
cd AutoHeal-CI
pip install -e .[dev]

# Run local self-healing
auto-heal --repo-path .

# Run against a saved CI log file
auto-heal --log-file failure.log --repo-path .

# Dry-Run mode (verifies locally without pushing a PR)
auto-heal --log-file failure.log --dry-run
```

---

## 🧪 Testing and Verification

A comprehensive master test runner covers all submodules:

```bash
pytest -q
```

```text
........................................................................ [ 74%]
.........................                                                [100%]
====================== 105 passed in 30.27s ======================
```

* `tests/test_ast_slicer.py` — Python AST extraction, classes, and decorators.
* `tests/test_ts_slicer.py` — TypeScript/TSX AST extraction and Jest stacktrace parsing.
* `tests/test_pytest_parser.py` — Pytest log parsing, `site-packages` noise filtering.
* `tests/test_dependency_healer.py` — Autonomous `pyproject.toml` resolution.
* `tests/test_sandbox_worktree.py` — Git Worktree lifecycle and isolation.
* `tests/test_graph_deliberation.py` — LangGraph state machine & adversarial loop.
* `tests/test_delivery_ux.py` — GitHub Step Summary, Mermaid generation, and fallback `.patch` export.
* `tests/test_commercial.py` — Enterprise license validation and Slack/Teams webhooks.
* `tests/test_benchmark_harness.py` — SWE-Bench Mini execution harness.

---

## 📁 Repository Structure

```text
AutoHeal-CI/
├── .github/
│   ├── FUNDING.yml                    # Sponsorship configuration (Boosty, Lava)
│   └── workflows/
│       ├── demo-live.yml              # 1-Click interactive cloud showcase
│       ├── self-heal-ci.yml           # Production in-runner action workflow
│       └── test.yml                   # CI test matrix across Python 3.10-3.12
├── action.yml                         # GitHub Action Marketplace specification
├── pyproject.toml                     # Package dependencies and build config
├── README.md                          # Primary English documentation
├── README_RU.md                       # Русскоязычная документация
├── PRICING.md                         # Commercial plans & ROI calculator
├── COMMERCIAL.md                      # Commercial licensing terms & B2B contracts
├── docs/index.html                    # Hosted product landing page
├── src/
│   └── autoheal/
│       ├── cli.py                     # CLI entrypoint
│       ├── config.py                  # Pydantic configuration & env parsing
│       ├── licensing.py               # Enterprise tier validation & badges
│       ├── parsers/                   # AST slicers & log parsers
│       ├── sandbox/                   # Git worktree sandbox harness
│       ├── agents/                    # LangGraph multi-agent orchestration
│       ├── delivery/                  # PR, Step Summary & Webhook notifiers
│       └── benchmarks/                # SWE-Bench Mini test scenarios
└── tests/                             # 105 unit, integration, and e2e tests
```

---

## 💎 Commercial Edition & Plans

AutoHeal-CI is available under three plans:

| Plan | Price | Description |
| :--- | :--- | :--- |
| **🆓 Community** | **\$0 (Free Forever)** | Open-source core, BYOK (OpenAI/Claude/Gemini keys), unlimited repairs, AST slicing & worktree sandboxing. |
| **⚡ Pro** | **\$39 / month** | Zero-config high-speed hosted proxy (no API keys needed), instant **Slack & Teams** alerts, priority queue. |
| **🏢 Enterprise** | **\$499 / month** | Air-gapped on-premise VPC deployment, local LLMs (Ollama, vLLM), GitLab CI & Bitbucket adapters, 99.9% SLA. |

👉 Full plan comparison & ROI calculator: [**PRICING.md**](PRICING.md)  
👉 Instant Pro license checkout (Cards & Worldwide): [**Buy Pro on Lava.top**](https://app.lava.top/products/03e25483-654d-4e28-8231-2a5e5cc8b62a)  
👉 Commercial licensing & B2B contracts: [**COMMERCIAL.md**](COMMERCIAL.md)  
👉 Interactive landing page with live ROI calculator: [**nolekek.github.io/AutoHeal-CI**](https://nolekek.github.io/AutoHeal-CI/)

---

## 📄 License

Distributed under a **Dual-Licensing** model:
* **Apache-2.0** for personal, open-source, and evaluation use.
* **Commercial Enterprise License** for proprietary on-premise deployments and SLA coverage (see [COMMERCIAL.md](COMMERCIAL.md)).
