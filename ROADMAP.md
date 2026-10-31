# 🗺️ AutoHeal-CI — Engineering Roadmap

> **Target**: Transforming the MVP into a production-grade, enterprise-ready CI/CD self-healing platform.

---

## 📌 Milestones Overview

```mermaid
flowchart LR
    M0["Milestone 0: Working MVP\n(Completed ✅)"] --> M1["Milestone 1: Robust AST & Unified Diff Engine\n(Completed ✅)"]
    M1 --> M2["Milestone 2: Failure Classifier & Structured Outputs\n(Completed ✅)"]
    M2 --> M3["Milestone 3: Enterprise GitHub UX & Fallbacks\n(Completed ✅)"]
    M3 --> M4["Milestone 4: SWE-Bench Suite & Benchmarks\n(Completed ✅)"]
```

---

## 🎯 Milestone 1: Robust AST & Unified Diff Engine
- [x] **1.1. Multi-Frame Call-Graph Resolver**:
  - Traverse all project-internal frames in the stacktrace (filtering out `site-packages` / system libs) to locate the root cause file/function.
- [x] **1.2. AST-Based Unified Diff Generator**:
  - Generate standards-compliant unified git diffs (`git apply` compatible) preserving line endings, comments, and project formatting.
- [x] **1.3. Complex Syntax Support**:
  - Advanced Tree-sitter queries for async functions, decorators, class hierarchies, and type annotations.

---

## 🎯 Milestone 2: Failure Classifier & Structured Multi-Agent Deliberation
- [x] **2.1. Pydantic Structured Outputs**:
  - Strict JSON schema responses for Coder and Critic agents (`CoderPatchOutput`, `CriticAttackOutput`) with robust fallback to markdown parsing.
- [x] **2.2. Pre-Flight Failure Classifier & Auto-Healer**:
  - Categorize failures before running LLM:
    * `LOGIC_BUG`: Run Coder vs Critic loop.
    * `MISSING_DEPENDENCY`: Detect missing packages (`ModuleNotFoundError`) and patch `pyproject.toml` directly via `DependencyHealer`.
- [x] **2.3. Token & Cost Guardrails**:
  - Token tracking, multi-model USD cost calculation, and hard budget limit enforcement (`BudgetExceededError`).

---

## 🎯 Milestone 3: Enterprise GitHub UX & Security
- [x] **3.1. Rich GitHub Step Summary**:
  - Collapsible `<details>` blocks with Mermaid diagrams of agent deliberation, side-by-side diff previews, and token usage tables.
- [x] **3.2. Fork PR & Read-Only Fallbacks**:
  - Export `.patch` artifacts (`.autoheal/autoheal-fix.patch`) if `GITHUB_TOKEN` lacks write permissions for forked PRs, with one-click `curl ... | git apply` instructions.
- [x] **3.3. GitHub Action Outputs Wiring**:
  - Wire `fixed`, `pr_url`, `patch_diff`, and `patch_path` into GitHub Actions composite outputs.

---

## 🎯 Milestone 4: Verification Benchmark Suite & SWE-Bench Mini-Harness
- [x] **4.1. Mini SWE-Bench Test Suite**:
  - 6 reproducible real-world bug scenarios (`off_by_one`, `none_dereference`, `key_error_nested`, `zero_division_guard`, `type_coercion_mismatch`, `missing_boundary_check`).
- [x] **4.2. Automated Benchmark Runner & Reporter**:
  - `BenchmarkRunner` with isolated ephemeral sandboxes, execution timing, and formatted markdown suite reports.
- [x] **4.3. 100% Test Coverage**:
  - 69 tests across the entire repository passing with 0 failures.
