"""
capsule_schema.py - Data contract and schema validation for Dependency Exit Capsule.

Member 3 (Migration Verification and Capsule Generation) for ExitGuard.
Preserves strict epistemological distinctions between:
  - OBSERVED: Directly inspected repository/metadata evidence.
  - EXECUTED: Produced by a command that actually ran.
  - AI_RECOMMENDATION: Gemma 4 / model suggestion (unproven hypothesis).
  - NOT_VERIFIED: Not tested or independently confirmed.
  - BLOCKED: Verification could not proceed (with explicit reason).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Dict, List, Optional


class EvidenceStatus(str, Enum):
    """Provenance and epistemological status of a claim or observation."""
    OBSERVED = "OBSERVED"
    EXECUTED = "EXECUTED"
    AI_RECOMMENDATION = "AI_RECOMMENDATION"
    HEURISTIC = "HEURISTIC"
    MANUAL_STAND_IN = "MANUAL_STAND_IN"
    MISSING_FROM_MEMBER_2 = "MISSING_FROM_MEMBER_2"
    NOT_VERIFIED = "NOT_VERIFIED"
    BLOCKED = "BLOCKED"


class RunStatus(str, Enum):
    """Outcome of an attempted test or command execution."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"


class VerificationVerdict(str, Enum):
    """
    Overall verdict of the migration verification suite.
    NOTE: VERIFIED_SUCCESS asserts only that explicitly executed checks passed within
    the tested scope, never claiming universal or unverified behavioral equivalence.
    """
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    REGRESSION_DETECTED = "REGRESSION_DETECTED"
    BLOCKED = "BLOCKED"
    NOT_VERIFIED = "NOT_VERIFIED"
    NO_MIGRATION_PROPOSED = "NO_MIGRATION_PROPOSED"


class ProposedAction(str, Enum):
    """Action recommended for the target dependency."""
    REPLACE = "REPLACE"
    REMOVE = "REMOVE"
    UPGRADE = "UPGRADE"
    NO_SAFE_REPLACEMENT = "NO_SAFE_REPLACEMENT"
    PROVISIONAL_EVALUATION = "PROVISIONAL_EVALUATION"


class SchemaValidationError(ValueError):
    """Raised when data violates capsule contract or validation constraints."""
    pass


@dataclass
class TestCounts:
    """Breakdown of executed test counts."""
    __test__ = False

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    total: int = 0

    def validate(self) -> None:
        if any(c < 0 for c in (self.passed, self.failed, self.skipped, self.total)):
            raise SchemaValidationError("Test counts cannot be negative.")
        if self.passed + self.failed + self.skipped > self.total:
            raise SchemaValidationError("Sum of passed, failed, and skipped exceeds total count.")


@dataclass
class TestCaseResult:
    """Individual test outcome and failure signature within a test suite."""
    __test__ = False

    node_id: str
    status: str
    duration_s: Optional[float] = None
    failure_message: Optional[str] = None
    failure_signature: Optional[str] = None

    def validate(self) -> None:
        if not self.node_id:
            raise SchemaValidationError("TestCaseResult requires node_id.")
        if not self.status:
            raise SchemaValidationError("TestCaseResult requires status.")


@dataclass
class RunRecord:
    """
    Auditable record of a single command or test execution attempt.
    Supports nullable fields for blocked or unexecuted runs.
    """
    command_args: List[str]
    python_version: str
    platform: str
    status: RunStatus
    working_dir: Optional[str] = None
    executed_at: Optional[str] = None
    exit_code: Optional[int] = None
    duration_ms: Optional[int] = None
    log_artifact_path: Optional[str] = None
    test_counts: Optional[TestCounts] = None
    test_results: Optional[List[TestCaseResult]] = None
    block_or_skip_reason: Optional[str] = None

    def validate(self) -> None:
        if not self.command_args and self.status not in (RunStatus.BLOCKED, RunStatus.NOT_RUN):
            raise SchemaValidationError("Executed RunRecord must specify command_args.")

        if self.status in (RunStatus.PASSED, RunStatus.FAILED):
            if self.exit_code is None:
                raise SchemaValidationError(f"RunRecord with status {self.status.value} must include exit_code.")
            if self.duration_ms is not None and self.duration_ms < 0:
                raise SchemaValidationError("duration_ms cannot be negative.")

        if self.status in (RunStatus.BLOCKED, RunStatus.NOT_RUN):
            if not self.block_or_skip_reason:
                raise SchemaValidationError(f"RunRecord with status {self.status.value} must supply block_or_skip_reason.")

        if self.test_counts:
            self.test_counts.validate()

        if self.test_results:
            for tr in self.test_results:
                tr.validate()


@dataclass
class VersionVerification:
    """
    Represents verification outcome independently for a specific Python version (e.g. 3.12 or 3.13).
    Prevents falsely claiming that an unavailable version was executed.
    """
    python_version: str
    tested: bool
    baseline_run: Optional[RunRecord] = None
    migrated_run: Optional[RunRecord] = None
    tests_passed_before: Optional[int] = None
    tests_passed_after: Optional[int] = None
    regressions: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    def validate(self) -> None:
        if not self.python_version:
            raise SchemaValidationError("VersionVerification must specify python_version.")

        if self.tested:
            if not self.baseline_run:
                raise SchemaValidationError(
                    f"VersionVerification marked tested=True for Python {self.python_version} must have baseline_run."
                )
            self.baseline_run.validate()
            if self.migrated_run:
                self.migrated_run.validate()
        else:
            if self.baseline_run and self.baseline_run.status in (RunStatus.PASSED, RunStatus.FAILED):
                raise SchemaValidationError(
                    f"VersionVerification marked tested=False cannot have executed baseline_run for Python {self.python_version}."
                )


@dataclass
class RepositoryMetadata:
    """Directly inspected repository baseline facts."""
    url: str
    commit_sha: str
    branch: str = "main"
    is_dirty: bool = False

    def validate(self) -> None:
        if not self.url:
            raise SchemaValidationError("RepositoryMetadata requires url.")
        if not self.commit_sha:
            raise SchemaValidationError("RepositoryMetadata requires commit_sha.")


@dataclass
class TargetDependency:
    """
    Target dependency under evaluation.
    Can be marked is_provisional=True before cross-member confirmation.
    """
    name: str
    specifier: str
    installed_version: Optional[str] = None
    is_provisional: bool = True

    def validate(self) -> None:
        if not self.name:
            raise SchemaValidationError("TargetDependency requires name.")
        if not self.specifier:
            raise SchemaValidationError("TargetDependency requires specifier.")


@dataclass
class RiskEvidence:
    """Individual item of risk evidence with explicit source and status."""
    category: str
    evidence: str
    source: str
    status: EvidenceStatus

    def validate(self) -> None:
        if not self.category or not self.evidence or not self.source:
            raise SchemaValidationError("RiskEvidence fields cannot be empty.")


@dataclass
class UsageLocation:
    """Directly inspected location in the repository where the dependency is used."""
    file_path: str
    line_numbers: List[int]
    ast_symbol: str
    status: EvidenceStatus = EvidenceStatus.OBSERVED

    def validate(self) -> None:
        if not self.file_path or not self.ast_symbol:
            raise SchemaValidationError("UsageLocation requires file_path and ast_symbol.")
        if any(line <= 0 for line in self.line_numbers):
            raise SchemaValidationError("Line numbers must be positive integers.")


@dataclass
class MigrationProposal:
    """
    AI-generated migration hypothesis from Member 2.
    Must always carry AI_RECOMMENDATION status.
    """
    proposed_action: ProposedAction
    replacement_package: Optional[str] = None
    rationale: str = ""
    patch_diff: Optional[str] = None
    uncertainty_notes: str = ""
    status: EvidenceStatus = EvidenceStatus.AI_RECOMMENDATION

    def validate(self) -> None:
        allowed_proposal_statuses = (
            EvidenceStatus.AI_RECOMMENDATION,
            EvidenceStatus.HEURISTIC,
            EvidenceStatus.MANUAL_STAND_IN,
            EvidenceStatus.MISSING_FROM_MEMBER_2,
        )
        if self.status not in allowed_proposal_statuses:
            raise SchemaValidationError(
                f"MigrationProposal status must be AI_RECOMMENDATION, HEURISTIC, MANUAL_STAND_IN, or MISSING_FROM_MEMBER_2, got {self.status.value}"
            )


@dataclass
class VerificationSummary:
    """
    Composite verification results across all evaluated Python versions.
    """
    verdict: VerificationVerdict
    verdict_scope_explanation: str
    supported_python_versions: List[str] = field(default_factory=lambda: ["3.12", "3.13"])
    tested_python_versions: List[str] = field(default_factory=list)
    python_version_results: Dict[str, VersionVerification] = field(default_factory=dict)
    compatibility_gaps: List[str] = field(default_factory=list)
    unresolved_concerns: List[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.verdict_scope_explanation:
            raise SchemaValidationError(
                "VerificationSummary requires verdict_scope_explanation explaining the limited scope of the verdict."
            )

        # Ensure tested_python_versions accurately reflects tested flags
        for py_ver in self.tested_python_versions:
            if py_ver not in self.python_version_results:
                raise SchemaValidationError(
                    f"Python version '{py_ver}' in tested_python_versions has no entry in python_version_results."
                )
            if not self.python_version_results[py_ver].tested:
                raise SchemaValidationError(
                    f"Python version '{py_ver}' marked in tested_python_versions but tested=False in results."
                )

        # Validate each version verification entry
        for v in self.python_version_results.values():
            v.validate()

        # If VERIFIED_SUCCESS, require at least one tested version and no regressions
        if self.verdict == VerificationVerdict.VERIFIED_SUCCESS:
            if not self.tested_python_versions:
                raise SchemaValidationError(
                    "Cannot issue VERIFIED_SUCCESS when zero Python versions were tested."
                )
            for py_ver in self.tested_python_versions:
                res = self.python_version_results[py_ver]
                if res.regressions:
                    raise SchemaValidationError(
                        f"Cannot issue VERIFIED_SUCCESS when regressions exist for Python {py_ver}: {res.regressions}"
                    )


@dataclass
class DependencyExitCapsule:
    """
    The canonical Dependency Exit Capsule document.
    Can represent:
      - A complete verified migration
      - A draft capsule (no selected dependency / proposal yet)
      - A blocked migration with documented obstacles
      - A synthetic fixture for testing (explicitly flagged)
    """
    capsule_id: str
    repository: RepositoryMetadata
    verification: VerificationSummary
    schema_version: str = "1.0.0"
    is_synthetic_fixture: bool = False
    is_draft: bool = False
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    generated_by: str = "ExitGuard v0.1.0 (Member 3: Migration Verification)"
    target_dependency: Optional[TargetDependency] = None
    risk_evidence: List[RiskEvidence] = field(default_factory=list)
    usage_locations: List[UsageLocation] = field(default_factory=list)
    migration_proposal: Optional[MigrationProposal] = None

    def validate(self) -> None:
        """Validates all inner components and contract invariants."""
        if not self.capsule_id:
            raise SchemaValidationError("DependencyExitCapsule requires capsule_id.")

        if self.is_synthetic_fixture and not self.capsule_id.startswith("SYNTHETIC_FIXTURE"):
            raise SchemaValidationError(
                "Synthetic fixture capsules must have capsule_id prefixed with 'SYNTHETIC_FIXTURE'."
            )

        self.repository.validate()

        if self.target_dependency is None or self.migration_proposal is None:
            if not self.is_draft:
                raise SchemaValidationError(
                    "Capsule without target_dependency or migration_proposal must have is_draft=True."
                )

        if self.target_dependency:
            self.target_dependency.validate()

        for risk in self.risk_evidence:
            risk.validate()

        for usage in self.usage_locations:
            usage.validate()

        if self.migration_proposal:
            self.migration_proposal.validate()

        self.verification.validate()

    def to_dict(self) -> Dict[str, Any]:
        """Convert capsule to serializable dictionary representation."""
        self.validate()

        def _convert(val: Any) -> Any:
            if isinstance(val, Enum):
                return val.value
            if isinstance(val, dict):
                return {k: _convert(v) for k, v in val.items()}
            if isinstance(val, list):
                return [_convert(item) for item in val]
            return val

        raw = asdict(self)
        return _convert(raw)

    def to_json(self, indent: int = 2) -> str:
        """Serialize validated capsule to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DependencyExitCapsule:
        """Reconstruct and validate a DependencyExitCapsule from a dictionary."""
        repo_data = data.get("repository", {})
        repo = RepositoryMetadata(
            url=repo_data["url"],
            commit_sha=repo_data["commit_sha"],
            branch=repo_data.get("branch", "main"),
            is_dirty=repo_data.get("is_dirty", False),
        )

        dep_data = data.get("target_dependency")
        target_dep = None
        if dep_data:
            target_dep = TargetDependency(
                name=dep_data["name"],
                specifier=dep_data["specifier"],
                installed_version=dep_data.get("installed_version"),
                is_provisional=dep_data.get("is_provisional", True),
            )

        risks = [
            RiskEvidence(
                category=r["category"],
                evidence=r["evidence"],
                source=r["source"],
                status=EvidenceStatus(r["status"]),
            )
            for r in data.get("risk_evidence", [])
        ]

        usages = [
            UsageLocation(
                file_path=u["file_path"],
                line_numbers=u["line_numbers"],
                ast_symbol=u["ast_symbol"],
                status=EvidenceStatus(u.get("status", EvidenceStatus.OBSERVED.value)),
            )
            for u in data.get("usage_locations", [])
        ]

        prop_data = data.get("migration_proposal")
        prop = None
        if prop_data:
            prop = MigrationProposal(
                proposed_action=ProposedAction(prop_data["proposed_action"]),
                replacement_package=prop_data.get("replacement_package"),
                rationale=prop_data.get("rationale", ""),
                patch_diff=prop_data.get("patch_diff"),
                uncertainty_notes=prop_data.get("uncertainty_notes", ""),
                status=EvidenceStatus(prop_data.get("status", EvidenceStatus.AI_RECOMMENDATION.value)),
            )

        verif_data = data.get("verification", {})
        py_results: Dict[str, VersionVerification] = {}
        for py_ver, vr_data in verif_data.get("python_version_results", {}).items():
            base_run_data = vr_data.get("baseline_run")
            mig_run_data = vr_data.get("migrated_run")

            base_run = None
            if base_run_data:
                tc_data = base_run_data.get("test_counts")
                tc = TestCounts(**tc_data) if tc_data else None
                tr_data = base_run_data.get("test_results")
                tr_list = [TestCaseResult(**item) for item in tr_data] if tr_data else None
                base_run = RunRecord(
                    command_args=base_run_data.get("command_args", []),
                    python_version=base_run_data["python_version"],
                    platform=base_run_data["platform"],
                    status=RunStatus(base_run_data["status"]),
                    working_dir=base_run_data.get("working_dir"),
                    executed_at=base_run_data.get("executed_at"),
                    exit_code=base_run_data.get("exit_code"),
                    duration_ms=base_run_data.get("duration_ms"),
                    log_artifact_path=base_run_data.get("log_artifact_path"),
                    test_counts=tc,
                    test_results=tr_list,
                    block_or_skip_reason=base_run_data.get("block_or_skip_reason"),
                )

            mig_run = None
            if mig_run_data:
                tc_data = mig_run_data.get("test_counts")
                tc = TestCounts(**tc_data) if tc_data else None
                tr_data = mig_run_data.get("test_results")
                tr_list = [TestCaseResult(**item) for item in tr_data] if tr_data else None
                mig_run = RunRecord(
                    command_args=mig_run_data.get("command_args", []),
                    python_version=mig_run_data["python_version"],
                    platform=mig_run_data["platform"],
                    status=RunStatus(mig_run_data["status"]),
                    working_dir=mig_run_data.get("working_dir"),
                    executed_at=mig_run_data.get("executed_at"),
                    exit_code=mig_run_data.get("exit_code"),
                    duration_ms=mig_run_data.get("duration_ms"),
                    log_artifact_path=mig_run_data.get("log_artifact_path"),
                    test_counts=tc,
                    test_results=tr_list,
                    block_or_skip_reason=mig_run_data.get("block_or_skip_reason"),
                )

            py_results[py_ver] = VersionVerification(
                python_version=py_ver,
                tested=vr_data.get("tested", False),
                baseline_run=base_run,
                migrated_run=mig_run,
                tests_passed_before=vr_data.get("tests_passed_before"),
                tests_passed_after=vr_data.get("tests_passed_after"),
                regressions=vr_data.get("regressions", []),
                notes=vr_data.get("notes"),
            )

        verification = VerificationSummary(
            verdict=VerificationVerdict(verif_data["verdict"]),
            verdict_scope_explanation=verif_data.get("verdict_scope_explanation", ""),
            supported_python_versions=verif_data.get("supported_python_versions", ["3.12", "3.13"]),
            tested_python_versions=verif_data.get("tested_python_versions", []),
            python_version_results=py_results,
            compatibility_gaps=verif_data.get("compatibility_gaps", []),
            unresolved_concerns=verif_data.get("unresolved_concerns", []),
        )

        capsule = cls(
            capsule_id=data["capsule_id"],
            schema_version=data.get("schema_version", "1.0.0"),
            is_synthetic_fixture=data.get("is_synthetic_fixture", False),
            is_draft=data.get("is_draft", False),
            generated_at=data.get("generated_at", ""),
            generated_by=data.get("generated_by", "ExitGuard"),
            repository=repo,
            target_dependency=target_dep,
            risk_evidence=risks,
            usage_locations=usages,
            migration_proposal=prop,
            verification=verification,
        )
        capsule.validate()
        return capsule

    @classmethod
    def from_json(cls, json_str: str) -> DependencyExitCapsule:
        """Deserialize and validate from JSON string."""
        return cls.from_dict(json.loads(json_str))
