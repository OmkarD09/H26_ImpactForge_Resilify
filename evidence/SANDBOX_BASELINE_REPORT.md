# 🔬 ExitGuard: Sandbox Baseline Reproducibility Report

> **Prepared by:** Member 3 — Migration Verification & Capsule Generation  
> **Target Repository:** `LinkWatch`  
> **Validated Baseline Commit:** `f52f3930c8e7c33d934ccf614955a38e26984bd5`  
> **Validation Timestamp (UTC):** `2026-10-15T08:08:00Z`  
> **Status:** `BASELINE_REPRODUCED_IN_SANDBOX`

---

## 1. Executive Summary

This report establishes and validates the empirical baseline of the target repository (`LinkWatch`) inside an isolated, disposable Git worktree created by `SandboxManager`.

- **Baseline Reproducibility:** **100% Confirmed**. The isolated sandbox test run produced identical outcomes to the non-sandbox baseline.
- **Tested Test Suite:** 10 unit tests collected (`tests/test_cache.py`, `tests/test_checker.py`, `tests/test_config.py`, `tests/test_report.py`).
- **Baseline Verdict:** **`9 PASSED`**, **`1 FAILED`**, **`1 WARNING`** (Exit code `1`).
- **Existing Upstream Defect:** `test_report.py::test_report_renders_all_sites` fails on a fresh install of declared dependencies due to an incompatible dependency interaction between `Jinja2==2.11.3` and `MarkupSafe>=3.0.0` (`cannot import name 'soft_unicode' from 'markupsafe'`). This is an existing baseline characteristic and **must not** be classified as a migration regression.
- **Source Repository Immutability:** The original `LinkWatch` working directory remained 100% clean and unmodified throughout the entire process.

---

## 2. Environment & Interpreter Support Matrix

| Python Version | Host Status | Test Status | Reason / Execution Detail |
| :--- | :--- | :--- | :--- |
| **Python 3.12** | `3.12.10 (64-bit)` installed | **EXECUTED** | Full virtual environment provisioned inside disposable sandbox; test suite executed. |
| **Python 3.13** | Not installed | **NOT_RUN** | Binary not available on host (`py -3.13` unavailable). No claims fabricated. |
| **Python 3.14** | `3.14.5` installed | **EXCLUDED** | Explicitly excluded per project specification (LinkWatch target: 3.12/3.13). |

---

## 3. Sandbox Execution Telemetry

| Parameter | Value |
| :--- | :--- |
| **Sandbox Path** | Temporary directory (auto-cleaned): `exitguard_sb_validation\exitguard_sb_49d1aea8` |
| **Pinned Commit SHA** | `f52f3930c8e7c33d934ccf614955a38e26984bd5` |
| **Sandbox Isolation** | Detached Git Worktree with ownership metadata tag |
| **Virtualenv Creation Command** | `py -3.12 -m venv <sandbox_root>/.venv_sb` (3.63s) |
| **Dependency Install Command** | `<venv>/Scripts/python.exe -m pip install -r requirements.txt -r requirements-dev.txt` |
| **Dependency Install Time** | `6,726 ms` (Exit Code `0`) |
| **Test Execution Command** | `<venv>/Scripts/python.exe -m pytest tests -v` |
| **Test Execution Time** | `9,268 ms` (Exit Code `1`) |
| **Log Artifact Path** | [`artifacts/baseline_logs/py312_sandbox_baseline.log`](file:///c:/Users/kunal/OneDrive/Desktop/V%20%205/H26_ImpactForge_Resilify/artifacts/baseline_logs/py312_sandbox_baseline.log) |

---

## 4. Test Case Breakdown: Non-Sandbox vs. Sandbox

| Test Case | Direct Baseline Run | Sandbox Run | Reproducibility |
| :--- | :--- | :--- | :--- |
| `tests/test_cache.py::test_cache_round_trip` | **PASSED** | **PASSED** | Identical |
| `tests/test_checker.py::test_ok_is_up` | **PASSED** | **PASSED** | Identical |
| `tests/test_checker.py::test_missing_is_down` | **PASSED** | **PASSED** | Identical |
| `tests/test_checker.py::test_redirect_is_up` | **PASSED** | **PASSED** | Identical |
| `tests/test_checker.py::test_slow_is_up` | **PASSED** | **PASSED** | Identical |
| `tests/test_checker.py::test_closed_port_is_down` | **PASSED** | **PASSED** | Identical |
| `tests/test_checker.py::test_latin1_title` | **PASSED** | **PASSED** | Identical |
| `tests/test_checker.py::test_user_agent` | **PASSED** | **PASSED** | Identical |
| `tests/test_config.py::test_sites_file_loads` | **PASSED** | **PASSED** | Identical |
| `tests/test_report.py::test_report_renders_all_sites` | **FAILED** | **FAILED** | Identical (`ImportError: soft_unicode`) |
| **Deprecation Warning (`pkg_resources`)** | **PRESENT** | **PRESENT** | Identical |

---

## 5. Identified Baseline Obstacles & Upstream Notes

1. **Jinja2 / MarkupSafe Transitive Failure:**
   - Manifest declares `Jinja2==2.11.3` with loose `markupsafe>=0.23`.
   - Modern `pip` installs `markupsafe-3.0.4`, which dropped the legacy `soft_unicode` function.
   - Result: `from markupsafe import soft_unicode` fails upon importing `jinja2.filters` during HTML report rendering.
2. **`pkg_resources` Deprecation:**
   - `linkwatch/resources.py` imports `pkg_resources` to locate `templates/status.html.j2`.
   - Setuptools 75.x emits a deprecation warning recommending `importlib.resources`.
3. **`nose` Dev Dependency Incompatibility:**
   - `requirements-dev.txt` lists `nose==1.3.7`.
   - Nose relies on Python's legacy `imp` module, which is completely absent in Python 3.12+. Running `nosetests` fails at interpreter startup.

---

## 6. Original Repository Integrity Verification

Post-validation Git status check confirmed no files were created, modified, or deleted within the canonical `LinkWatch` source tree:
- Canonical path checked: `c:\Users\kunal\OneDrive\Desktop\V  5\H26_ImpactForge_Resilify\LinkWatch`
- Git working tree status: **Clean (0 uncommitted changes)**.
