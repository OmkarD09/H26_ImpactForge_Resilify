# 🎯 ExitGuard: Milestone 4A — Evidence-Backed Dependency Candidate Selection Report

> **Prepared by:** Member 3 — Migration Verification & Capsule Generation  
> **Milestone:** Milestone 4A (Evidence-Backed Dependency Candidate Selection)  
> **Target Repository:** `LinkWatch` (Pinned Commit: `f52f3930c8e7c33d934ccf614955a38e26984bd5`)  
> **Evaluation Timestamp (UTC):** `2026-10-15T08:46:00Z`  
> **Architecture Principle:** *AI recommends. Deterministic tools inspect. Tests verify. The capsule reports evidence honestly.*  
> **Status:** **`CANDIDATE_IDENTIFIED_AND_JUSTIFIED`** (No patch applied, no replacement installed, 0 repository modifications)

---

## 1. Executive Summary & Selection Decision

In accordance with ExitGuard's empirical verification framework, we evaluated all declared and indirect dependencies of `LinkWatch` using:
1. **Manifest Provenance:** `requirements.txt`, `requirements-dev.txt`, and `pyproject.toml`.
2. **Empirical Baseline Logs:** Captured Python 3.12 sandbox baseline test executions (10 collected: 9 passed, 1 pre-existing failure).
3. **AST Static Code Analysis:** Inspected call sites across `LinkWatch/linkwatch/*.py`.
4. **Member 1 Dependency Inventory:** Extracted from `evidence/dependency_inventory.json`.
5. **Cross-Member Status:** Member 1 evidence is verified present; Member 2 Gemma 4 recommendation evidence is currently **MISSING** and is explicitly recorded as uncompleted without fabrication.

### Selected Primary Migration Candidate: `appdirs` $\rightarrow$ `platformdirs`

- **Target Package:** `appdirs==1.4.4` (Declared in `requirements.txt:2`, `pyproject.toml:14`).
- **Proposed Action:** `ProposedAction.REPLACE` with `platformdirs`.
- **Justification:** `appdirs` is an abandoned runtime package (last released May 2020; upstream repo archived since 2017). It has known directory resolution bugs on modern operating systems. `platformdirs` is the official, actively maintained community standard fork providing an exact 1:1 drop-in replacement API for `user_cache_dir("linkwatch")` at a single isolated call site (`linkwatch/cache.py:10`).
- **Why NOT `markupsafe` / `Jinja2` as a replacement?** The baseline `soft_unicode` import failure is caused by an unconstrained transitive conflict between pinned `Jinja2==2.11.3` (2021) and modern unpinned `MarkupSafe==3.0.4`. `markupsafe` is **not** imported by LinkWatch, and replacing `Jinja2` with a different templating engine would be an unneeded architectural disruption. The appropriate fix for Jinja2 is a version constraint upgrade, not a package replacement.

---

## 2. Multi-Member Evidence Audit

| Source | Role / Deliverable | Status | Findings / Evidence Path |
| :--- | :--- | :--- | :--- |
| **Member 1** | Static Analysis, Manifests, Baseline Inventory | **`PRESENT`** | Located at [`evidence/dependency_inventory.json`](file:///c:/Users/kunal/OneDrive/Desktop/V%20%205/H26_ImpactForge_Resilify/evidence/dependency_inventory.json). 14 dependencies cataloged with PyPI release dates, AST imports, and indirect findings. |
| **Member 2** | Gemma 4 AI Reasoning, Prompts & Recommendations | **`MISSING`** | **No Member 2 artifacts found.** In `TASKS.md`, Member 2 tasks remain uncompleted (`[ ]`). No prompt logs, model inference records, or AI patches exist. **Not fabricated.** |
| **Member 3** | Sandbox Verification, Execution Runner, Comparator | **`PRESENT`** | Runner, sandbox manager, and baseline comparator validated. Python 3.12 executed; Python 3.13 strictly `NOT_RUN`. |

---

## 3. Investigation of the Baseline `markupsafe.soft_unicode` Failure

A critical constraint of ExitGuard is: **Do not select a package solely because its name appears in a failing traceback.**

```
================================== FAILURES ===================================
________________________ test_report_renders_all_sites ________________________
...
tests/test_report.py:20: in test_report_renders_all_sites
    result = CliRunner().invoke(cli, ["report", "-o", str(output)], catch_exceptions=False)
linkwatch/cli.py:53: in report
    from .report import render_report
linkwatch/report.py:3: in <module>
    from jinja2 import Environment, FileSystemLoader, select_autoescape
...
jinja2/filters.py:13: in <module>
    from markupsafe import soft_unicode
E   ImportError: cannot import name 'soft_unicode' from 'markupsafe'
```

### Forensic Root-Cause Breakdown:
1. **Who imports `soft_unicode`?**
   - Direct codebase inspection proves that **`LinkWatch` has 0 imports of `markupsafe`**.
   - The symbol `soft_unicode` is imported exclusively by `jinja2.filters` at line 13.
2. **Why do the installed versions conflict?**
   - `LinkWatch/requirements.txt` strictly pins `Jinja2==2.11.3` (released January 31, 2021).
   - In 2021, Jinja2 declared `MarkupSafe>=0.23` without an upper bound constraint.
   - When `pip install` resolves dependencies today in Python 3.12, it installs the newest release of `MarkupSafe`, which is `3.0.4`.
   - `MarkupSafe` deprecated `soft_unicode` in version 2.1.0 and permanently removed it in version 3.0.0.
   - Pinned `Jinja2==2.11.3` cannot run against `MarkupSafe>=3.0.0`.
3. **Is an API migration or dependency replacement appropriate?**
   - **No.** Replacing `Jinja2` with an alternative templating library (such as Mako or Chameleon) would require rewriting the HTML templates (`linkwatch/templates/status.html.j2`) and CLI report generator.
   - The conflict is purely a **transitive version constraint mismatch**.
   - Resolving it requires upgrading `Jinja2>=3.1.2` (which natively supports MarkupSafe 3.x) or pinning `MarkupSafe<3.0.0`.
   - Therefore, `markupsafe` / `Jinja2` is **NOT** a viable dependency exit candidate; it is a version pin maintenance issue.

---

## 4. Comprehensive Candidate Evaluation Matrix

We evaluated all plausible candidates identified in Member 1's inventory and codebase AST scans:

| Evaluation Dimension | Candidate 1: `appdirs` (**PRIMARY**) | Candidate 2: `toml` (**ALTERNATIVE**) | Candidate 3: `Jinja2` / `MarkupSafe` | Candidate 4: `nose` |
| :--- | :--- | :--- | :--- | :--- |
| **Declared Specifier** | `==1.4.4` (`requirements.txt:2`, `pyproject.toml:14`) | `==0.10.2` (`requirements.txt:1`, `pyproject.toml:13`) | `Jinja2==2.11.3` (MarkupSafe unpinned) | `==1.3.7` (`requirements-dev.txt:2`) |
| **Observed Installed** | `1.4.4` | `0.10.2` | `Jinja2==2.11.3`, `MarkupSafe==3.0.4` | `1.3.7` |
| **Dependency Type** | **Direct Runtime** | **Direct Runtime** | Direct Runtime / Transitive Conflict | Direct Dev Tool |
| **Inspected AST Usage** | `linkwatch/cache.py:4` (`from appdirs import user_cache_dir`) | `linkwatch/config.py:3` (`import toml`), line 37 (`toml.load(path)`) | `linkwatch/report.py:3` (`from jinja2 import Environment...`) | None (0 imports in tests or code) |
| **Failing Tests?** | None (tests pass in baseline) | None (tests pass in baseline) | `test_report_renders_all_sites` (FAILED) | None (pytest used; nose broken on 3.12+) |
| **Maintenance Concern** | Upstream repo archived since 2017; stale for 6 years. | Stale since 2020; superseded by stdlib `tomllib`. | 2021 release incompatible with modern transitive deps. | Dead since 2015; crashes on Python 3.12 (`imp` removed). |
| **Proposed Action** | **`ProposedAction.REPLACE`** | **`ProposedAction.REPLACE`** | **`ProposedAction.UPGRADE`** | **`ProposedAction.REMOVE`** |
| **Proposed Target** | **`platformdirs`** | Standard library **`tomllib`** | `Jinja2>=3.1.2` | Remove from `requirements-dev.txt` |
| **Migration Effort** | **LOW** (1:1 drop-in replacement) | **MEDIUM** (Requires binary file handle change) | **ARCHITECTURAL_REWRITE** (if replaced) | **LOW** (Remove dead requirement) |
| **Gemma 4 Status** | `MISSING_FROM_MEMBER_2` | `MISSING_FROM_MEMBER_2` | `MISSING_FROM_MEMBER_2` | `MISSING_FROM_MEMBER_2` |
| **Selection Verdict** | **`RECOMMENDED_PRIMARY`** | `VIABLE_ALTERNATIVE` | `REJECTED_AS_REPLACEMENT` | `CLEANUP_ONLY` |

---

## 5. In-Depth Candidate Profile: `appdirs` $\rightarrow$ `platformdirs`

### A. Manifest Provenance & Installed State
- Declared in `LinkWatch/requirements.txt`: Line 2 (`appdirs==1.4.4`).
- Declared in `LinkWatch/pyproject.toml`: Line 14 (`"appdirs==1.4.4"`).
- Installed in baseline virtualenv: `appdirs 1.4.4`.

### B. Observed Usage Evidence (Direct Static AST Inspection)
- **File:** `LinkWatch/linkwatch/cache.py`
  - Line 4: `from appdirs import user_cache_dir`
  - Line 10: `path = os.environ.get("LINKWATCH_CACHE_DIR") or user_cache_dir("linkwatch")`
- **Total Call Sites:** Exactly 1 call site across the entire repository.
- **Dynamic Usage:** None. No dynamic `getattr`, reflection, or plugin loading detected.

### C. Maintenance & Vulnerability Context
- PyPI release date: `2020-05-11` (1.4.4).
- Upstream GitHub repository (`ActiveState/appdirs`) has been **officially archived and unmaintained since 2017**.
- Ecosystem status: Python community consensus has fully migrated to `platformdirs`, which was specifically created as an active fork to fix macOS and Windows directory bugs in `appdirs`.

### D. Proposed Replacement: `platformdirs`
- **Package Name:** `platformdirs` (Recommended specifier: `platformdirs>=3.0.0`).
- **Drop-in Compatibility:** Provides the exact same function signature:
  ```python
  from platformdirs import user_cache_dir
  ```
- **Return Type:** Returns string directory path (or `Path` if requested, but default `user_cache_dir("linkwatch")` returns `str`).
- **Target Call Site:**
  ```python
  # Before:
  from appdirs import user_cache_dir
  # After:
  from platformdirs import user_cache_dir
  ```

### E. Evidence Supporting the Proposal
1. **Minimal Disruption:** Exactly one import line changed (`linkwatch/cache.py:4`). Zero logic changes required.
2. **Deterministic Verification:** Covered by `tests/test_cache.py::test_cache_round_trip`.
3. **Modern Python Support:** Active maintenance with official Python 3.12 and 3.13 wheels and CI testing.
4. **Clean Supply Chain:** Removes an abandoned package from `requirements.txt` and `pyproject.toml`.

### F. Evidence Contradicting / Risks
1. **Existing Test Passing:** `appdirs` is not currently causing a test failure in `test_cache.py` under Python 3.12.
2. **Cache Path Consistency:** On certain operating systems, `platformdirs` may default to slightly refined subdirectory conventions (e.g., roaming vs. local cache), although for `user_cache_dir("linkwatch")` on Windows both resolve to `%LOCALAPPDATA%\linkwatch\Cache`.

### G. Confidence & Unresolved Questions
- **Confidence Score:** `0.95` (Very High).
- **Unresolved Questions:**
  1. Does `platformdirs` produce any directory permission or locking differences in isolated container environments (e.g. Linux Dockerfile)?
  2. Awaiting user approval before applying sandbox patch in Milestone 4B.

---

## 6. Deterministic Verification & Test Results

All deterministic parsing, candidate evaluation, and safety rules were verified via automated tests:

Command: `py -3.12 -m pytest tests_exitguard -v`
- **Test Results:** **`43 passed in 25.51s`**
- **Exit Code:** `0`
- **Failures:** `0`
- **New Candidate Selection Tests (6/6 passed):**
  - `test_evaluate_appdirs_candidate`: Verified `appdirs` evaluated as primary replacement candidate.
  - `test_evaluate_toml_candidate`: Verified `toml` evaluated as stdlib migration alternative.
  - `test_evaluate_jinja2_markupsafe_distinction`: Verified `Jinja2` marked `UPGRADE`, rejecting replacement.
  - `test_missing_member2_evidence_is_explicitly_flagged`: Verified missing Member 2 evidence flagged honestly.
  - `test_get_primary_candidate_selection`: Verified primary candidate selection returns `appdirs`.
  - `test_candidate_to_dict_serialization`: Verified schema serialization.

---

## 7. Original Repository Integrity Audit

At the conclusion of Milestone 4A, Git status was audited across all working trees:

- **Upstream External Target (`c:\Users\kunal\OneDrive\Desktop\V  5\linkwatch`):**
  ```
  On branch main
  Your branch is up to date with 'origin/main'.
  nothing to commit, working tree clean
  ```
- **Internal Canonical Target (`H26_ImpactForge_Resilify/LinkWatch`):**
  ```
  nothing to commit, working tree clean
  ```
- **Integrity Verified:** Zero files modified in LinkWatch. Zero dependency manifests changed. Zero packages installed.

---

## 8. Machine-Readable Deliverables & Artifacts

- **Candidate Evidence JSON:** [`artifacts/candidate_selection_evidence.json`](file:///c:/Users/kunal/OneDrive/Desktop/V%20%205/H26_ImpactForge_Resilify/artifacts/candidate_selection_evidence.json)
- **Candidate Evaluator Module:** [`exitguard/candidate_evaluator.py`](file:///c:/Users/kunal/OneDrive/Desktop/V%20%205/H26_ImpactForge_Resilify/exitguard/candidate_evaluator.py)
- **Candidate Evaluator Tests:** [`tests_exitguard/test_candidate_selection.py`](file:///c:/Users/kunal/OneDrive/Desktop/V%20%205/H26_ImpactForge_Resilify/tests_exitguard/test_candidate_selection.py)
- **Member 1 Baseline Inventory:** [`evidence/dependency_inventory.json`](file:///c:/Users/kunal/OneDrive/Desktop/V%20%205/H26_ImpactForge_Resilify/evidence/dependency_inventory.json)

---

## 9. Next Steps (Awaiting Approval)

**STOPPED AS REQUIRED.** We do not proceed to patch application or package installation until candidate selection is reviewed and approved:

**Recommended Next Step upon approval:**
Proceed to **Milestone 4B: Isolated Sandbox Migration Verification**:
1. Spin up an ExitGuard sandbox at pinned commit `f52f3930c8e7c33d934ccf614955a38e26984bd5`.
2. Apply the `appdirs` $\rightarrow$ `platformdirs` replacement patch exclusively within the sandbox.
3. Install `platformdirs` inside the sandbox virtual environment.
4. Execute test verification using `ExecutionRunner`.
5. Deterministically compare candidate run vs. baseline run using `BaselineComparator`.
6. Compile the complete `DependencyExitCapsule`.
