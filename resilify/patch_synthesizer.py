"""
Patch Synthesizer & Verification Test Generator for Resilify (Member 2).

Generates:
1. Unified diff `.patch` files ready for sandbox application by Member 3.
2. Suggested verification unit test files (`tests/test_migration_verification.py`).
3. Fallback documentation for complex or non-viable migrations.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Any

from .gemma_client import GemmaMigrationProposal


class PatchSynthesizer:
    """Manages generation, storage, and validation of migration patches and verification tests."""

    def __init__(self, patches_dir: Path | str = "patches", tests_dir: Path | str = "LinkWatch/tests") -> None:
        self.patches_dir = Path(patches_dir)
        self.tests_dir = Path(tests_dir)

    def write_patches(self, proposals: List[GemmaMigrationProposal]) -> Dict[str, str]:
        """
        Writes individual `.patch` files and a consolidated `all_migrations.patch`.
        Returns a mapping of package_name -> patch_file_path.
        """
        self.patches_dir.mkdir(parents=True, exist_ok=True)
        written_patches: Dict[str, str] = {}
        combined_diffs: List[str] = []

        for p in proposals:
            if not p.unified_diff.strip():
                continue

            patch_filename = f"{p.package_name}_migration.patch"
            patch_path = self.patches_dir / patch_filename
            patch_path.write_text(p.unified_diff, encoding="utf-8")
            written_patches[p.package_name] = str(patch_path)
            combined_diffs.append(f"# === Migration Patch for {p.package_name} ({p.target_action}) ===\n" + p.unified_diff)

        if combined_diffs:
            master_patch = self.patches_dir / "consolidated_resilify_migrations.patch"
            master_patch.write_text("\n\n".join(combined_diffs) + "\n", encoding="utf-8")
            written_patches["_consolidated"] = str(master_patch)

        return written_patches

    def generate_verification_test_file(self, proposals: List[GemmaMigrationProposal], output_path: Optional[Path | str] = None) -> str:
        """
        Compiles all proposed verification tests into a runnable pytest file.
        """
        target = Path(output_path) if output_path else self.tests_dir / "test_migration_verification.py"
        target.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            '"""',
            'Verification Test Suite for Resilify Migrations.',
            'Synthesized by Gemma 4 (Member 2) for Sandbox Verification by Member 3.',
            '"""',
            '',
            'import os',
            'import sys',
            'import pytest',
            '',
        ]

        for p in proposals:
            if not p.verification_tests:
                continue

            lines.append(f"# --- Verification tests for {p.package_name} ({p.target_action}) ---")
            for test_code in p.verification_tests:
                lines.append(test_code)
                lines.append("")

        content = "\n".join(lines)
        target.write_text(content, encoding="utf-8")
        return str(target)

    def format_fallback_documentation(self, proposals: List[GemmaMigrationProposal]) -> str:
        """
        Formats markdown fallback documentation covering non-viable replacements,
        open limitations, and rollback risks.
        """
        doc_lines = [
            "# 🛡️ Gemma 4 Migration Feasibility & Fallback Documentation",
            "",
            "This document records feasibility assessments, migration steps, open limitations,",
            "and rollback risks synthesized by Gemma 4 for all evaluated dependencies.",
            "",
            "---",
            "",
        ]

        for p in proposals:
            doc_lines.extend([
                f"## Package: `{p.package_name}`",
                f"- **Target Action:** `{p.target_action}`",
                f"- **Feasibility:** `{p.feasibility}`",
                f"- **Recommended Replacement:** `{p.recommended_package or 'N/A (Pruning/Removal)'}`",
                f"- **Standard Library?:** `{'Yes' if p.is_stdlib else 'No'}`",
                f"- **Minimum Python Runtime:** `{p.min_python_version}`",
                f"- **Rollback Risk Level:** `{p.rollback_risk}`",
                "",
                "### Engineering Rationale",
                f"{p.rationale}",
                "",
                "### Step-by-Step Migration Plan",
            ])
            for i, step in enumerate(p.migration_steps, start=1):
                doc_lines.append(f"{i}. {step}")

            if p.compatibility_gaps_and_limitations:
                doc_lines.extend(["", "### ⚠️ Known Compatibility Gaps & Open Limitations"])
                for gap in p.compatibility_gaps_and_limitations:
                    doc_lines.append(f"- {gap}")

            doc_lines.extend(["", "---", ""])

        return "\n".join(doc_lines)
