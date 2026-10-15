# TASKS.md — Project Resilify (`H26_ImpactForge_Resilify`)

> **Track:** Track 1: Gemma 4 Dependency Resilience  
> **Target Repository:** `https://github.com/rishrek/LinkWatch` (Python 3.12 / 3.13)  
> **Core Deliverable:** Dynamic Dependency Analysis, Gemma 4 Migration Synthesis, Sandbox Verification (`pytest`), and the **Dependency Exit Capsule** (JSON + Markdown).

---

## **Member 1: Static Analysis, Manifests & Baseline Evidence Collector**
* **Objective:** Parse project configuration and build the objective, evidence-backed dependency inventory without AI assumptions.

### **Assigned Tasks:**
- [x] **Manifest & Lockfile Parser:** Inspect `requirements.txt`, `requirements-dev.txt`, and `pyproject.toml` to extract pinned versions and detect version conflicts (e.g., `pydantic==1.10.13` vs `pydantic>=2`).
- [x] **PyPI Metadata Fetcher:** Query the live PyPI JSON API (`https://pypi.org/pypi/<pkg>/json`) to gather latest version numbers, release dates, and deprecation markers.
- [x] **AST Code Scanner:** Implement Python AST parsing across `LinkWatch/linkwatch/*.py` to map exact file paths, line numbers, import statements, and call-site contexts.
- [x] **Dynamic & Indirect Usage Inspection:** Scan for plugin patterns, configuration settings, or indirect dependencies (flagging unused "ghost" packages like `six` or broken dev tools like `nose`).
- [x] **Baseline Test Execution:** Run the initial `pytest` suite against `LinkWatch` on Python 3.12 / 3.13 and capture baseline logs, warnings, and error output.

---

## **Member 2: Gemma 4 AI Reasoning & Migration Patch Builder**
* **Objective:** Leverage Gemma 4 to analyze risk evidence, filter out unverified risks, and synthesize accurate migration patches.

- [x] **Risk Evaluation Gate:** Filter scanned dependencies; if no evidence of risk or usage exists, record as "unknown" and prevent AI hallucination (*"Do not invent risk"*).
- [x] **Gemma 4 Prompt & API Integration:** Integrate the Google GenAI SDK to send AST usage snippets, manifest data, and PyPI metadata to Gemma 4.
- [x] **Migration Feasibility Assessment:** Evaluate whether a replacement or removal is feasible (e.g., standard library migration like `toml` $\rightarrow$ `tomllib`, or package drop-in like `appdirs` $\rightarrow$ `platformdirs`).
- [x] **Fallback Documentation:** For non-viable replacements, format structured documentation covering alternatives and open limitations.
- [x] **Patch & Test Synthesis:** Generate clean code diffs, migration steps, and suggested verification tests for viable replacements.

---

## **Member 3: Sandbox Verification, Execution Logging & Exit Capsule Generator**
* **Objective:** Execute sandboxed validation, handle execution failures gracefully, and compile the final Dependency Exit Capsule.

### **Assigned Tasks:**
- [x] **Isolated Sandbox Setup:** Create an isolated temporary copy of `LinkWatch` from a clean baseline.
- [x] **Patch Application & Installation:** Apply Gemma's candidate patch and install compatible replacement packages.
- [x] **Post-Migration Verification:** Run targeted and full project `pytest` suites inside the sandbox.
- [x] **Outcome Comparison & Error Handling:** Compare baseline vs. migrated test runs:
  - *Pass within tested scope* $\rightarrow$ Mark tests passed; retain limitations.
  - *Failures or behavioral differences* $\rightarrow$ Record compatibility gaps and rollback risks.
  - *Could not execute* $\rightarrow$ Mark as **NOT VERIFIED** with a clear engineering explanation.
- [x] **Capsule Compilation:** Output the complete **Dependency Exit Capsule** (`dependency_exit_capsule.json` and `DEPENDENCY_EXIT_CAPSULE.md`) containing all required fields (dependency details, risk indicators, usage locations, proposed replacements, migration steps, executed test results, and compatibility gaps) separated clearly into **Observed Evidence** vs. **Gemma 4 Recommendations**.
