"""
Unit tests for Member 2: Gemma 4 AI Reasoning & Migration Patch Builder.
"""

import json
from pathlib import Path
import pytest

from resilify.risk_gate import RiskEvaluationGate, RiskCategory, RiskFactorType
from resilify.gemma_client import GemmaMigrationClient, GemmaMigrationProposal
from resilify.patch_synthesizer import PatchSynthesizer


@pytest.fixture
def sample_inventory():
    return {
        "metadata": {"target_repository": "LinkWatch"},
        "manifest_summary": {
            "dependencies": {
                "toml": [{"specifier": "==0.10.2"}],
                "click": [{"specifier": ">=7"}],
                "unknown_pkg": [{"specifier": "==1.0.0"}],
            }
        },
        "dependencies": {
            "toml": {
                "package_name": "toml",
                "declarations": [{"specifier": "==0.10.2"}],
                "has_objective_risk": True,
                "objective_risks": [
                    "PYPI_DEPRECATION: Ecosystem Advisory: Python 3.11+ includes standard library 'tomllib'",
                    "DEPRECATED_RUNTIME_API: Direct import and usage of external 'toml' library",
                ],
                "ast_usage": {"is_imported": True, "call_sites": ["toml.load(f)"]},
                "pypi_metadata": {"latest_version": "0.10.2"},
            },
            "click": {
                "package_name": "click",
                "declarations": [{"specifier": ">=7"}],
                "has_objective_risk": False,
                "objective_risks": [],
                "ast_usage": {"is_imported": True, "call_sites": ["@click.group()"]},
                "pypi_metadata": {"latest_version": "8.1.7"},
            },
            "unknown_pkg": {
                "package_name": "unknown_pkg",
                "declarations": [{"specifier": "==1.0.0"}],
                "has_objective_risk": False,
                "objective_risks": [],
                "ast_usage": {"is_imported": False, "call_sites": []},
                "pypi_metadata": {"latest_version": "1.0.0"},
            },
        },
        "baseline_test_results": {"failures": []},
    }


def test_risk_gate_does_not_invent_risk(sample_inventory):
    gate = RiskEvaluationGate(sample_inventory)
    evaluated = gate.evaluate()

    # toml should be ACTIONABLE_RISK due to objective deprecation evidence
    assert evaluated["toml"].risk_category == RiskCategory.ACTIONABLE_RISK
    assert evaluated["toml"].can_ai_reason is True

    # click should be BENIGN_ACTIVE without invented risk
    assert evaluated["click"].risk_category == RiskCategory.BENIGN_ACTIVE
    assert evaluated["click"].can_ai_reason is False

    # unknown_pkg should be UNVERIFIED_UNKNOWN
    assert evaluated["unknown_pkg"].risk_category == RiskCategory.UNVERIFIED_UNKNOWN
    assert evaluated["unknown_pkg"].can_ai_reason is False


def test_gemma_client_synthesis():
    client = GemmaMigrationClient(api_key=None)  # Tests deterministic expert fallback
    proposal = client.synthesize_proposal(
        package_name="toml",
        pinned_versions=["==0.10.2"],
        ast_usage_summary={"call_sites": ["toml.load(path)"]},
        pypi_meta={"latest_version": "0.10.2"},
        evidence_descriptions=["Deprecated in Python 3.11+ in favor of tomllib"],
        test_failures=[],
        code_snippets={},
    )

    assert isinstance(proposal, GemmaMigrationProposal)
    assert proposal.package_name == "toml"
    assert proposal.target_action == "MIGRATE_TO_STDLIB"
    assert proposal.recommended_package == "tomllib"
    assert proposal.is_stdlib is True
    assert "--- a/linkwatch/config.py" in proposal.unified_diff
    assert len(proposal.verification_tests) > 0


def test_patch_synthesizer(tmp_path):
    proposal = GemmaMigrationProposal(
        package_name="test_dep",
        target_action="REPLACE_PACKAGE",
        feasibility="HIGH_FEASIBILITY",
        recommended_package="new_dep",
        is_stdlib=False,
        min_python_version="3.10",
        rationale="Upgrade to active fork",
        migration_steps=["pip install new_dep"],
        unified_diff="--- a/test.py\n+++ b/test.py\n-import old\n+import new\n",
        verification_tests=["def test_new(): assert True"],
        compatibility_gaps_and_limitations=[],
        rollback_risk="LOW",
    )

    patches_dir = tmp_path / "patches"
    tests_dir = tmp_path / "tests"
    synthesizer = PatchSynthesizer(patches_dir=patches_dir, tests_dir=tests_dir)

    written = synthesizer.write_patches([proposal])
    assert "test_dep" in written
    assert (patches_dir / "test_dep_migration.patch").exists()
    assert (patches_dir / "consolidated_resilify_migrations.patch").exists()

    test_file = synthesizer.generate_verification_test_file([proposal])
    assert Path(test_file).exists()
    assert "def test_new(): assert True" in Path(test_file).read_text()
