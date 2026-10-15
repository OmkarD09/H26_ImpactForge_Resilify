# 🛡️ ExitGuard — AI Dependency Resilience System

> **Track:** Track 1: Gemma 4 Dependency Resilience  
> **Team:** ImpactForge (`H26_ImpactForge_Resilify`)  
> **Target Upstream:** [LinkWatch](https://github.com/rishrek/LinkWatch) pinned to commit `f52f3930c8e7c33d934ccf614955a38e26984bd5`  
> **Core Principle:** *AI recommends. Deterministic tools inspect. Tests verify. The capsule reports evidence honestly.*

---

## 1. Problem Statement & Project Value

Modern Python projects frequently accumulate unmaintained, abandoned, or incompatible dependencies. Upgrades often fail because:
1. LLMs hallucinate non-existent packages, speculative versions, or unsafe migration code.
2. In-place experimentation mutates repositories and invalidates baseline reproducibility.
3. Teams lack auditable, machine-verifiable proof separating AI hypotheses from empirical test execution.

**ExitGuard** solves this with a zero-trust, evidence-first dependency migration framework:
- **Gemma 4 Reasoning:** Uses hosted `gemma-4-26b-a4b-it` to analyze real AST usages, PyPI metadata, and manifest constraints.
- **Strict Epistemological Separation:** Explicitly distinguishes `OBSERVED`, `EXECUTED`, `AI_RECOMMENDATION`, `NOT_VERIFIED`, and `BLOCKED` claims.
- **Deterministic Worktree Isolation:** Executes all installations and test suites in disposable Git worktrees without touching the upstream repository.
- **Certified Dependency Exit Capsule:** Emits strict, schema-validated JSON and human-readable Markdown capsules documenting test parity, regressions, and rollback steps.

---

## 2. Architecture & Team Deliverables

```
H26_ImpactForge_Resilify/
├── LinkWatch/                  # Upstream target (NEVER modified; 100% clean baseline)
├── exitguard/                  # Member 3: Verification & Execution Engine
│   ├── capsule_schema.py       # Strict data contract & schema validation
│   ├── sandbox_manager.py      # Git worktree isolation with ownership tags
│   ├── execution_runner.py     # Policy-enforced subprocess runner (timeout, secret scrubber)
│   ├── comparator.py           # Deterministic baseline vs. candidate test comparator
│   ├── candidate_evaluator.py  # Dependency risk evaluation & candidate scoring
│   └── gemma_advisor.py        # Official Google GenAI SDK hosted Gemma 4 integration
├── evidence/                   # Human-Readable Reports & Evidence Artifacts
│   ├── BASELINE_REPORT.md               # Member 1: Real baseline execution & log capture
│   ├── dependency_inventory.json        # Member 1: AST usage, manifest & PyPI metadata
│   ├── GEMMA_REASONING_REPORT.md        # Member 2: Gemma 4 migration reasoning & risk gate
│   ├── gemma_migration_proposals.json   # Member 2: Live Gemma 4 migration proposals
│   ├── DEPENDENCY_EXIT_CAPSULE.md       # Member 3: Single-candidate capsule (appdirs -> platformdirs)
│   └── CONSOLIDATED_EXIT_CAPSULE.md     # Member 3: Consolidated migration capsule (10/10 passing)
├── artifacts/                  # Machine-Readable Verified Artifacts
│   ├── dependency_exit_capsule.json     # Single-candidate validated JSON capsule
│   ├── consolidated_exit_capsule.json   # Consolidated validated JSON capsule
│   ├── gemma_advice_evidence.json       # Secret-free provenance of live Gemma 4 advice
│   ├── candidate_selection_evidence.json# Grounded candidate evaluation records
│   └── runner_logs/                     # Raw execution logs
│       └── py312_consolidated_migration.log # Reproducible pytest output (Exit Code 0)
├── patches/
│   └── consolidated_resilify_migrations.patch # Member 2: Surgical migration patch
├── tests_exitguard/            # 56 automated unit & integration tests (100% passing)
├── TASKS.md                    # Complete project delivery checklist across all 3 roles
└── README.md                   # System documentation & reproduction guide
```

---

## 3. Secure Credential Configuration

ExitGuard integrates with Google's official `google-genai` SDK and queries `gemma-4-26b-a4b-it`.

1. Place your API key in a `.env` file at the repository root:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
2. **Security Guarantees:**
   - `.env` is tracked in `.gitignore` and is never committed.
   - `exitguard.execution_runner` and `exitguard.gemma_advisor` redact all matching API key patterns (`AIza...`) from command strings, stdout, stderr, and persistent JSON/Markdown evidence.
   - If credentials are absent, ExitGuard fails gracefully with `CREDENTIALS_MISSING` and never crashes.

---

## 4. 60-Second Demo & Verification Script

### Step 1: Run ExitGuard Automated Test Suite (56 tests)
Validates schema integrity, worktree isolation, sandbox boundary guards, and deterministic comparator logic:
```bash
py -3.12 -m pytest tests_exitguard -v
```
*Expected: `56 passed in ~15s`.*

### Step 2: Query Hosted Gemma 4 Live Advisor
Queries Google's hosted `gemma-4-26b-a4b-it` model to analyze AST citations and evaluate the `appdirs` replacement:
```bash
py -3.12 -m exitguard.gemma_advisor --live
```
*Expected: Model recommends `platformdirs>=3.0.0` with `HIGH` confidence, validates grounded citations (`linkwatch/cache.py:4`), scrubs credentials, and updates the capsule.*

### Step 3: Inspect the Certified Dependency Exit Capsules
Review the audited outcomes:
- **Single-Candidate Migration (`appdirs` $\rightarrow$ `platformdirs`):**
  - Markdown: [`evidence/DEPENDENCY_EXIT_CAPSULE.md`](evidence/DEPENDENCY_EXIT_CAPSULE.md)
  - JSON: [`artifacts/dependency_exit_capsule.json`](artifacts/dependency_exit_capsule.json)
  - Outcome: **Parity achieved (9 passed, 0 regressions, pre-existing Jinja2 baseline failure preserved)**.
- **Consolidated Multi-Dependency Migration Patch:**
  - Markdown: [`evidence/CONSOLIDATED_EXIT_CAPSULE.md`](evidence/CONSOLIDATED_EXIT_CAPSULE.md)
  - JSON: [`artifacts/consolidated_exit_capsule.json`](artifacts/consolidated_exit_capsule.json)
  - Log: [`artifacts/runner_logs/py312_consolidated_migration.log`](artifacts/runner_logs/py312_consolidated_migration.log)
  - Outcome: **`VERIFIED_SUCCESS` (10/10 passed, 0 failed, pre-existing failure resolved)**.

---

## 5. Supported Environments & Honest Limitations

1. **Python 3.12 Tested:**  
   All tests and sandboxed runs were executed on Python 3.12.10 on `Windows-AMD64`.
2. **Python 3.13 Honestly Marked `NOT_RUN`:**  
   The host machine lacks a Python 3.13 interpreter. ExitGuard strictly adheres to its honesty invariant: Python 3.13 is recorded in all capsules as `NOT_RUN` with clear engineering explanations. No speculative success is claimed.
3. **Repository Immutability:**  
   The original `LinkWatch` working tree at `f52f3930c8e7c33d934ccf614955a38e26984bd5` was never altered. `git status` remains 100% clean.
4. **Epistemological Guardrails:**  
   Zero regressions does **not** imply universal equivalence. ExitGuard certificates explicitly scope verdicts to the tests actually executed in the isolated sandbox.
