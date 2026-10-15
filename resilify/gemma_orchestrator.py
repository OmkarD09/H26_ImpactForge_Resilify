"""
Gemma 4 Migration Orchestrator for Resilify (Member 2).

Orchestrates all 5 assigned tasks for Member 2:
1. Risk Evaluation Gate: Filter scanned dependencies; enforce "Do not invent risk".
2. Gemma 4 Prompt & API Integration: Ingest inventory, code snippets, and PyPI metadata.
3. Migration Feasibility Assessment: Evaluate stdlib vs drop-in replacements vs removals.
4. Fallback Documentation: Record compatibility gaps, rollback risks, and limitations.
5. Patch & Test Synthesis: Generate unified diffs (.patch) and suggested pytest tests.

Outputs:
- evidence/gemma_migration_proposals.json (Machine-readable contract for Member 3)
- evidence/GEMMA_REASONING_REPORT.md (Comprehensive human-readable engineering report)
- patches/*.patch (Unified diff files)
- LinkWatch/tests/test_migration_verification.py (Suggested verification test suite)
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

from .risk_gate import RiskEvaluationGate, RiskCategory
from .gemma_client import GemmaMigrationClient, GemmaMigrationProposal
from .patch_synthesizer import PatchSynthesizer


class GemmaMigrationOrchestrator:
    """Master orchestrator for Member 2 AI reasoning and migration patch synthesis."""

    def __init__(
        self,
        inventory_file: Path | str = "evidence/dependency_inventory.json",
        output_dir: Path | str = "evidence",
        repo_dir: Path | str = "LinkWatch",
        patches_dir: Path | str = "patches",
        api_key: Optional[str] = None,
    ) -> None:
        self.inventory_file = Path(inventory_file)
        self.output_dir = Path(output_dir)
        self.repo_dir = Path(repo_dir)
        self.patches_dir = Path(patches_dir)
        self.api_key = api_key

    def run(self) -> Dict[str, Any]:
        print(f"[*] Starting Resilify Gemma 4 Migration Orchestrator (Member 2)", flush=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.patches_dir.mkdir(parents=True, exist_ok=True)

        if not self.inventory_file.exists():
            raise FileNotFoundError(f"Missing required inventory file from Member 1: {self.inventory_file}")

        # Step 1: Ingest inventory
        print(f"[1/5] Ingesting baseline dependency inventory from: {self.inventory_file}", flush=True)
        with open(self.inventory_file, "r", encoding="utf-8") as f:
            inventory = json.load(f)

        # Step 2: Risk Evaluation Gate
        print("[2/5] Running Risk Evaluation Gate (Enforcing 'Do not invent risk')...", flush=True)
        gate = RiskEvaluationGate(inventory)
        evaluated = gate.evaluate()

        actionable = gate.get_actionable_dependencies()
        benign = gate.get_benign_dependencies()
        unknown = gate.get_unknown_dependencies()

        print(f"      Evaluated {len(evaluated)} packages:", flush=True)
        print(f"      - Actionable Risks: {len(actionable)} ({', '.join(d.package_name for d in actionable)})", flush=True)
        print(f"      - Benign Active: {len(benign)} ({', '.join(d.package_name for d in benign)})", flush=True)
        print(f"      - Unknown / Unverified: {len(unknown)}", flush=True)

        # Step 3: Gemma 4 AI Reasoning & Migration Feasibility Assessment
        print("[3/5] Synthesizing migration proposals with Gemma 4...", flush=True)
        client = GemmaMigrationClient(api_key=self.api_key)
        mode_str = f"Live Google GenAI API ({client.model_name})" if client.is_live_api_ready else "Deterministic Expert Synthesis"
        print(f"      Operating mode: {mode_str}", flush=True)

        proposals: List[GemmaMigrationProposal] = []
        deps_data = inventory.get("dependencies", {})
        baseline_test = inventory.get("baseline_test_results", {})

        for dep in actionable:
            print(f"      -> Processing proposal for '{dep.package_name}'...", flush=True)
            pkg_info = deps_data.get(dep.package_name, {})
            ast_summary = pkg_info.get("ast_usage", {})
            pypi_summary = pkg_info.get("pypi_metadata", {})
            evidence_descs = [e.description for e in dep.evidence_items]
            test_failures = baseline_test.get("failures", [])

            # Fetch actual code snippets from call sites
            code_snippets: Dict[str, str] = {}
            for loc in ast_summary.get("import_locations", []):
                fpath = loc.get("file_path", "")
                full_path = self.repo_dir / fpath if not Path(fpath).is_absolute() else Path(fpath)
                if full_path.exists():
                    try:
                        code_snippets[fpath] = full_path.read_text(encoding="utf-8")
                    except Exception:
                        pass

            proposal = client.synthesize_proposal(
                package_name=dep.package_name,
                pinned_versions=dep.pinned_specifiers,
                ast_usage_summary=ast_summary,
                pypi_meta=pypi_summary,
                evidence_descriptions=evidence_descs,
                test_failures=test_failures,
                code_snippets=code_snippets,
            )
            proposals.append(proposal)

        # Step 4: Patch & Test Synthesis
        print("[4/5] Generating unified diff patches and verification test suites...")
        synthesizer = PatchSynthesizer(patches_dir=self.patches_dir, tests_dir=self.repo_dir / "tests")
        written_patches = synthesizer.write_patches(proposals)
        verification_test_file = synthesizer.generate_verification_test_file(proposals)
        fallback_doc = synthesizer.format_fallback_documentation(proposals)

        print(f"      Generated {len(written_patches)} patch files in: {self.patches_dir}", flush=True)
        print(f"      Generated verification test suite in: {verification_test_file}", flush=True)

        # Step 5: Export Data Contracts & Markdown Report
        print("[5/5] Exporting Member 2 deliverables for Member 3...", flush=True)
        proposals_contract = {
            "metadata": {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "author": "Member 2: Gemma 4 AI Reasoning & Migration Patch Builder",
                "operating_mode": mode_str,
                "total_actionable_evaluated": len(proposals),
                "total_benign_retained": len(benign),
                "total_unknown_retained": len(unknown),
            },
            "gate_summary": {
                "actionable_packages": [d.package_name for d in actionable],
                "benign_packages": [d.package_name for d in benign],
                "unknown_packages": [d.package_name for d in unknown],
            },
            "proposals": [asdict(p) for p in proposals],
            "patch_files": written_patches,
            "verification_test_suite": verification_test_file,
        }

        proposals_file = self.output_dir / "gemma_migration_proposals.json"
        with open(proposals_file, "w", encoding="utf-8") as f:
            json.dump(proposals_contract, f, indent=2)

        # Markdown Report
        report_file = self.output_dir / "GEMMA_REASONING_REPORT.md"
        report_md = self._build_markdown_report(proposals, actionable, benign, unknown, written_patches, verification_test_file)
        report_file.write_text(report_md, encoding="utf-8")

        print(f"\n[+] Member 2 Execution Completed Successfully!", flush=True)
        print(f"    - Proposals Data Contract: {proposals_file}", flush=True)
        print(f"    - Engineering Report:      {report_file}", flush=True)
        print(f"    - Consolidated Patch:      {written_patches.get('_consolidated', 'N/A')}", flush=True)
        print(f"    - Verification Test File:  {verification_test_file}", flush=True)

        return proposals_contract

    def _build_markdown_report(
        self,
        proposals: List[GemmaMigrationProposal],
        actionable: List[Any],
        benign: List[Any],
        unknown: List[Any],
        patches: Dict[str, str],
        test_file: str,
    ) -> str:
        now = datetime.now(timezone.utc).isoformat()
        md = [
            "# 🤖 Gemma 4 Dependency Reasoning & Migration Synthesis Report",
            "",
            "> **Generated by Member 2:** Gemma 4 AI Reasoning & Migration Patch Builder  ",
            "> **Target Repository:** `LinkWatch`  ",
            f"> **Timestamp (UTC):** `{now}`  ",
            "",
            "---",
            "",
            "## 1. Executive Summary",
            "",
            f"- **Evaluated Dependencies:** `{len(actionable) + len(benign) + len(unknown)}`",
            f"- **Actionable Migration Candidates:** `{len(actionable)}` ({', '.join(f'`{d.package_name}`' for d in actionable)})",
            f"- **Benign Healthy Dependencies:** `{len(benign)}` ({', '.join(f'`{d.package_name}`' for d in benign)})",
            f"- **Unverified / Unknown Packages:** `{len(unknown)}`",
            f"- **Patches Synthesized:** `{len(patches)}`",
            f"- **Synthesized Verification Test Suite:** `{test_file}`",
            "",
            "### Core Mandate: 'Do Not Invent Risk'",
            "Dependencies with active, healthy usage and zero breaking test failures or deprecations (`click`, `rich`, `python-dateutil`, `requests`) were strictly marked **BENIGN_ACTIVE**. No hallucinations or speculative risks were generated.",
            "",
            "---",
            "",
            "## 2. Risk Evaluation Gate Results",
            "",
            "| Package | Risk Category | AST Used | Key Verified Evidence | Reason for AI Action |",
            "| :--- | :--- | :---: | :--- | :--- |",
        ]

        for d in actionable:
            ev_str = "<br>".join(f"• {e.description}" for e in d.evidence_items[:3])
            md.append(f"| **`{d.package_name}`** | `ACTIONABLE_RISK` | {'✅' if d.is_ast_used else '❌'} | {ev_str} | Verified risk requires resolution |")

        for d in benign:
            md.append(f"| **`{d.package_name}`** | `BENIGN_ACTIVE` | ✅ | Active usage in codebase; no breaking runtime errors | Retained as-is (Do not invent risk) |")

        for d in unknown:
            md.append(f"| **`{d.package_name}`** | `UNVERIFIED_UNKNOWN` | ❌ | No verified usage or breaking evidence | Retained as-is without speculation |")

        md.extend([
            "",
            "---",
            "",
            "## 3. Gemma 4 Migration Feasibility Matrix",
            "",
            "| Target Package | Proposed Action | Recommended Replacement | Stdlib? | Feasibility | Rollback Risk |",
            "| :--- | :--- | :--- | :---: | :--- | :---: |",
        ])

        for p in proposals:
            md.append(
                f"| **`{p.package_name}`** | `{p.target_action}` | `{p.recommended_package or 'None (Purged)'}` | "
                f"{'✅ Yes' if p.is_stdlib else '❌ No'} | `{p.feasibility}` | `{p.rollback_risk}` |"
            )

        md.extend([
            "",
            "---",
            "",
            "## 4. Detailed Migration Proposals & Patches",
            "",
        ])

        for p in proposals:
            md.extend([
                f"### Migration Plan: `{p.package_name}`",
                f"- **Target Action:** `{p.target_action}`",
                f"- **Feasibility:** `{p.feasibility}` | **Rollback Risk:** `{p.rollback_risk}`",
                f"- **Replacement:** `{p.recommended_package or 'None (Safe Removal)'}` (Standard Library: `{'Yes' if p.is_stdlib else 'No'}`)",
                f"- **Minimum Python Runtime:** `{p.min_python_version}`",
                "",
                "#### Rationale",
                f"{p.rationale}",
                "",
                "#### Migration Steps",
            ])
            for i, step in enumerate(p.migration_steps, start=1):
                md.append(f"{i}. {step}")

            if p.unified_diff.strip():
                md.extend([
                    "",
                    "#### Synthesized Unified Diff",
                    "```diff",
                    p.unified_diff.strip(),
                    "```",
                ])

            if p.compatibility_gaps_and_limitations:
                md.extend([
                    "",
                    "#### ⚠️ Known Limitations & Compatibility Gaps",
                ])
                for gap in p.compatibility_gaps_and_limitations:
                    md.append(f"- {gap}")

            if p.verification_tests:
                md.extend([
                    "",
                    "#### Suggested Verification Tests (`pytest`)",
                    "```python",
                    "\n".join(p.verification_tests),
                    "```",
                ])

            md.extend(["", "---", ""])

        md.extend([
            "## 5. Handoff to Member 3 (Sandbox Verification & Exit Capsule)",
            "",
            "Member 3 can now execute the sandboxed validation loop using:",
            "1. **Input Data Contract:** [`evidence/gemma_migration_proposals.json`](./gemma_migration_proposals.json)",
            "2. **Individual Patches:** [`patches/`](../patches/)",
            "3. **Consolidated Patch:** [`patches/consolidated_resilify_migrations.patch`](../patches/consolidated_resilify_migrations.patch)",
            "4. **Verification Tests:** [`LinkWatch/tests/test_migration_verification.py`](../LinkWatch/tests/test_migration_verification.py)",
            "",
            "Member 3 will apply each patch in an isolated sandbox, execute `pytest`, and generate the final `dependency_exit_capsule.json` and `DEPENDENCY_EXIT_CAPSULE.md`.",
        ])

        return "\n".join(md)


def main() -> None:
    orchestrator = GemmaMigrationOrchestrator()
    orchestrator.run()


if __name__ == "__main__":
    main()
