"""
Unit & Integration Verification Tests for Member 2: Gemma 4 AI Reasoning & Migration Patch Builder.
"""

import json
import subprocess
from pathlib import Path
import pytest

from resilify.risk_gate import RiskEvaluationGate, RiskCategory, RiskFactorType
from resilify.gemma_client import GemmaMigrationClient, GemmaMigrationProposal
from resilify.patch_synthesizer import PatchSynthesizer


@pytest.fixture
def live_inventory():
    inv_path = Path("evidence/dependency_inventory.json")
    assert inv_path.exists(), "evidence/dependency_inventory.json must exist"
    with open(inv_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_risk_gate_benign_packages_do_not_invent_risk(live_inventory):
    """
    Tier 1 Requirement:
    Verify principle of 'Do not invent risk':
    4 benign packages (chardet, click, pytest, requests) remain untouched (BENIGN_ACTIVE).
    """
    gate = RiskEvaluationGate(live_inventory)
    evaluated = gate.evaluate()

    benign_expected = {"chardet", "click", "pytest", "requests"}
    for pkg in benign_expected:
        assert pkg in evaluated, f"Expected {pkg} in evaluated dependencies"
        dep = evaluated[pkg]
        assert dep.risk_category == RiskCategory.BENIGN_ACTIVE, (
            f"Package '{pkg}' should be BENIGN_ACTIVE without invented risk, got {dep.risk_category}"
        )
        assert dep.can_ai_reason is False, f"Package '{pkg}' must not trigger AI speculation"


def test_risk_gate_unverified_packages_marked_unknown(live_inventory):
    """
    Tier 1 Requirement:
    Verify that 2 unverified packages (python-dateutil, rich) are marked as UNKNOWN.
    """
    gate = RiskEvaluationGate(live_inventory)
    evaluated = gate.evaluate()

    unknown_expected = {"python-dateutil", "rich"}
    for pkg in unknown_expected:
        assert pkg in evaluated, f"Expected {pkg} in evaluated dependencies"
        dep = evaluated[pkg]
        assert dep.risk_category == RiskCategory.UNVERIFIED_UNKNOWN, (
            f"Package '{pkg}' should be UNVERIFIED_UNKNOWN, got {dep.risk_category}"
        )
        assert dep.can_ai_reason is False


def test_risk_gate_actionable_packages_trigger_migrations(live_inventory):
    """
    Tier 1 Requirement:
    Verify that 8 actionable packages (toml, appdirs, jinja2, nose, pydantic, setuptools, six, idna)
    are flagged as ACTIONABLE_RISK with verified objective evidence.
    """
    gate = RiskEvaluationGate(live_inventory)
    evaluated = gate.evaluate()

    actionable_expected = {"toml", "appdirs", "jinja2", "nose", "pydantic", "setuptools", "six", "idna"}
    for pkg in actionable_expected:
        assert pkg in evaluated, f"Expected {pkg} in evaluated dependencies"
        dep = evaluated[pkg]
        assert dep.risk_category == RiskCategory.ACTIONABLE_RISK, (
            f"Package '{pkg}' should be ACTIONABLE_RISK, got {dep.risk_category}"
        )
        assert dep.can_ai_reason is True
        assert len(dep.evidence_items) > 0, f"Package '{pkg}' must have verified evidence items"


def test_gemma_client_schema_compliance_all_actionable(live_inventory):
    """
    Tier 1 Requirement:
    Verify schema compliance of all synthesized JSON outputs from the Gemma client.
    """
    gate = RiskEvaluationGate(live_inventory)
    evaluated = gate.evaluate()
    actionable = gate.get_actionable_dependencies()

    client = GemmaMigrationClient(api_key=None)  # deterministic expert mode
    deps_data = live_inventory.get("dependencies", {})

    for dep in actionable:
        pkg_info = deps_data.get(dep.package_name, {})
        proposal = client.synthesize_proposal(
            package_name=dep.package_name,
            pinned_versions=dep.pinned_specifiers,
            ast_usage_summary=pkg_info.get("ast_usage", {}),
            pypi_meta=pkg_info.get("pypi_metadata", {}),
            evidence_descriptions=[e.description for e in dep.evidence_items],
            test_failures=[],
            code_snippets={},
        )

        assert isinstance(proposal, GemmaMigrationProposal)
        assert proposal.package_name == dep.package_name
        assert proposal.target_action in {
            "MIGRATE_TO_STDLIB",
            "REPLACE_PACKAGE",
            "REMOVE_GHOST",
            "REMOVE_BROKEN_DEV_TOOL",
            "BUMP_VERSION",
            "RESOLVE_MANIFEST_CONFLICT",
            "REMOVE_TRANSITIVE_PIN",
        }
        assert proposal.feasibility in {
            "HIGH_FEASIBILITY",
            "MEDIUM_FEASIBILITY",
            "LOW_FEASIBILITY",
            "REMOVAL_CANDIDATE",
        }
        assert proposal.rollback_risk in {"LOW", "MEDIUM", "HIGH"}
        assert len(proposal.rationale.strip()) > 10
        assert len(proposal.migration_steps) > 0
        assert len(proposal.verification_tests) > 0


def test_patch_synthesizer_git_apply_clean_check():
    """
    Tier 2 Requirement:
    Execute git apply --check on every generated patch file to confirm no hunk rejections.
    """
    patches_dir = Path("patches")
    assert patches_dir.exists()

    expected_patches = [
        "toml_migration.patch",
        "appdirs_migration.patch",
        "jinja2_migration.patch",
        "nose_migration.patch",
        "setuptools_migration.patch",
        "six_migration.patch",
        "idna_migration.patch",
        "pydantic_migration.patch",
        "consolidated_resilify_migrations.patch",
    ]

    for patch_name in expected_patches:
        patch_file = patches_dir / patch_name
        assert patch_file.exists(), f"Patch file {patch_name} must exist"
        res = subprocess.run(
            ["git", "apply", "--check", str(patch_file)],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, (
            f"git apply --check failed on {patch_name}:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
        )
