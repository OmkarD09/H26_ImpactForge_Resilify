"""
test_schema.py - Automated tests for ExitGuard capsule_schema.

Verifies:
  1. Valid synthetic fixture loading and round-trip serialization.
  2. Draft capsules with omitted target/proposal.
  3. Status validation and rejection of invalid enums/provenance.
  4. Mandatory reason for blocked or unexecuted test runs.
  5. Correct handling of nullable fields for unexecuted tests.
  6. Independent multi-version Python results (e.g. 3.12 vs 3.13).
  7. Strict prevention of false claims (e.g., claiming untested version as tested,
     or issuing VERIFIED_SUCCESS with regressions or zero executed tests).
"""

import json
from pathlib import Path
import pytest

from exitguard.capsule_schema import (
    DependencyExitCapsule,
    EvidenceStatus,
    MigrationProposal,
    ProposedAction,
    RepositoryMetadata,
    RiskEvidence,
    RunRecord,
    RunStatus,
    SchemaValidationError,
    TargetDependency,
    TestCounts,
    UsageLocation,
    VerificationSummary,
    VerificationVerdict,
    VersionVerification,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def get_base_repo() -> RepositoryMetadata:
    return RepositoryMetadata(
        url="https://github.com/rishrek/linkwatch",
        commit_sha="f52f3930c8e7c33d934ccf614955a38e26984bd5",
        branch="main",
        is_dirty=False,
    )


def test_load_synthetic_fixture():
    """Verify that the synthetic fixture file loads, validates, and serializes cleanly."""
    fixture_path = FIXTURES_DIR / "synthetic_capsule_example.json"
    assert fixture_path.exists(), f"Fixture file not found at {fixture_path}"

    with open(fixture_path, "r", encoding="utf-8") as fh:
        raw_data = json.load(fh)

    capsule = DependencyExitCapsule.from_dict(raw_data)
    assert capsule.is_synthetic_fixture is True
    assert capsule.capsule_id.startswith("SYNTHETIC_FIXTURE")
    assert capsule.repository.commit_sha == "f52f3930c8e7c33d934ccf614955a38e26984bd5"
    assert capsule.verification.verdict == VerificationVerdict.VERIFIED_SUCCESS

    # Test JSON round-trip
    serialized = capsule.to_json()
    reloaded = DependencyExitCapsule.from_json(serialized)
    assert reloaded.capsule_id == capsule.capsule_id
    assert reloaded.verification.tested_python_versions == ["3.12"]
    assert "3.13" in reloaded.verification.python_version_results
    assert reloaded.verification.python_version_results["3.13"].tested is False


def test_draft_capsule_allowed_with_none_target_and_proposal():
    """Verify that a draft capsule with no chosen dependency or proposal is valid."""
    verif = VerificationSummary(
        verdict=VerificationVerdict.NO_MIGRATION_PROPOSED,
        verdict_scope_explanation="Draft status: no dependency or migration patch selected yet.",
        supported_python_versions=["3.12", "3.13"],
        tested_python_versions=[],
        python_version_results={},
    )
    draft = DependencyExitCapsule(
        capsule_id="SYNTHETIC_FIXTURE-draft-001",
        is_synthetic_fixture=True,
        is_draft=True,
        repository=get_base_repo(),
        verification=verif,
        target_dependency=None,
        migration_proposal=None,
    )
    draft.validate()
    d = draft.to_dict()
    assert d["is_draft"] is True
    assert d["target_dependency"] is None
    assert d["migration_proposal"] is None


def test_non_draft_capsule_rejects_missing_target():
    """Verify that non-draft capsules must have target_dependency and proposal."""
    verif = VerificationSummary(
        verdict=VerificationVerdict.NOT_VERIFIED,
        verdict_scope_explanation="Not verified.",
    )
    capsule = DependencyExitCapsule(
        capsule_id="SYNTHETIC_FIXTURE-invalid-non-draft",
        is_synthetic_fixture=True,
        is_draft=False,  # Not marked draft
        repository=get_base_repo(),
        verification=verif,
        target_dependency=None,
    )
    with pytest.raises(SchemaValidationError, match="Capsule without target_dependency or migration_proposal must have is_draft=True"):
        capsule.validate()


def test_synthetic_fixture_must_have_synthetic_prefix():
    """Verify that synthetic fixtures must have explicit SYNTHETIC_FIXTURE in ID."""
    verif = VerificationSummary(
        verdict=VerificationVerdict.NOT_VERIFIED,
        verdict_scope_explanation="Test.",
    )
    capsule = DependencyExitCapsule(
        capsule_id="real-looking-id-12345",
        is_synthetic_fixture=True,
        is_draft=True,
        repository=get_base_repo(),
        verification=verif,
    )
    with pytest.raises(SchemaValidationError, match="Synthetic fixture capsules must have capsule_id prefixed"):
        capsule.validate()


def test_migration_proposal_must_be_ai_recommendation():
    """Verify that migration proposals cannot masquerade as observed facts or executed tests."""
    with pytest.raises(SchemaValidationError, match="MigrationProposal status must be AI_RECOMMENDATION"):
        prop = MigrationProposal(
            proposed_action=ProposedAction.REPLACE,
            replacement_package="some-pkg",
            status=EvidenceStatus.EXECUTED,  # Invalid for a proposal
        )
        prop.validate()


def test_blocked_run_record_requires_reason():
    """Verify that a BLOCKED or NOT_RUN record must provide a reason."""
    record = RunRecord(
        command_args=[],
        python_version="3.12",
        platform="Windows",
        status=RunStatus.BLOCKED,
        block_or_skip_reason=None,  # Missing reason
    )
    with pytest.raises(SchemaValidationError, match="must supply block_or_skip_reason"):
        record.validate()

    # Valid with reason
    record.block_or_skip_reason = "Missing dependency 'rich' in environment."
    record.validate()  # Passes without error


def test_executed_run_record_requires_exit_code():
    """Verify that a PASSED/FAILED run record must have an integer exit code."""
    record = RunRecord(
        command_args=["py", "-3.12", "-m", "pytest"],
        python_version="3.12.10",
        platform="Windows",
        status=RunStatus.PASSED,
        exit_code=None,  # Invalid for PASSED
    )
    with pytest.raises(SchemaValidationError, match="must include exit_code"):
        record.validate()

    record.exit_code = 0
    record.validate()  # Passes


def test_independent_python_version_reporting():
    """
    Verify that Python 3.12 and 3.13 are independently tracked,
    and tested_python_versions cannot falsely claim an unexecuted version.
    """
    py312_run = RunRecord(
        command_args=["py", "-3.12", "-m", "pytest"],
        python_version="3.12.10",
        platform="Windows",
        status=RunStatus.PASSED,
        exit_code=0,
        duration_ms=1000,
    )
    py312_verif = VersionVerification(
        python_version="3.12",
        tested=True,
        baseline_run=py312_run,
        tests_passed_before=4,
    )

    py313_verif = VersionVerification(
        python_version="3.13",
        tested=False,  # NOT tested
        baseline_run=None,
    )

    # Valid configuration: 3.12 tested, 3.13 not tested
    verif = VerificationSummary(
        verdict=VerificationVerdict.VERIFIED_SUCCESS,
        verdict_scope_explanation="Passed all 4 unit tests under Python 3.12.",
        supported_python_versions=["3.12", "3.13"],
        tested_python_versions=["3.12"],
        python_version_results={
            "3.12": py312_verif,
            "3.13": py313_verif,
        },
    )
    verif.validate()

    # Invalid configuration: Claiming 3.13 was tested when tested=False
    verif.tested_python_versions = ["3.12", "3.13"]
    with pytest.raises(SchemaValidationError, match="marked in tested_python_versions but tested=False"):
        verif.validate()


def test_verified_success_cannot_be_claimed_with_zero_tested_versions():
    """Verify that VERIFIED_SUCCESS is rejected if no version was actually tested."""
    verif = VerificationSummary(
        verdict=VerificationVerdict.VERIFIED_SUCCESS,
        verdict_scope_explanation="All good.",
        tested_python_versions=[],  # None tested!
        python_version_results={},
    )
    with pytest.raises(SchemaValidationError, match="Cannot issue VERIFIED_SUCCESS when zero Python versions were tested"):
        verif.validate()


def test_verified_success_cannot_be_claimed_with_regressions():
    """Verify that VERIFIED_SUCCESS is rejected if regressions occurred in any tested version."""
    py312_run = RunRecord(
        command_args=["py", "-3.12", "-m", "pytest"],
        python_version="3.12.10",
        platform="Windows",
        status=RunStatus.PASSED,
        exit_code=0,
    )
    py312_verif = VersionVerification(
        python_version="3.12",
        tested=True,
        baseline_run=py312_run,
        regressions=["test_cache_round_trip failed"],  # Regression recorded!
    )
    verif = VerificationSummary(
        verdict=VerificationVerdict.VERIFIED_SUCCESS,
        verdict_scope_explanation="Testing.",
        tested_python_versions=["3.12"],
        python_version_results={"3.12": py312_verif},
    )
    with pytest.raises(SchemaValidationError, match="Cannot issue VERIFIED_SUCCESS when regressions exist"):
        verif.validate()
