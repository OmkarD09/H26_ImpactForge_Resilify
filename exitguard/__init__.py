"""
ExitGuard - Dependency Exit Capsule Schema and Verification Engine.
Member 3 component for H26_ImpactForge_Resilify.
"""

from .capsule_schema import (
    DependencyExitCapsule,
    EvidenceStatus,
    MigrationProposal,
    ProposedAction,
    RepositoryMetadata,
    RiskEvidence,
    RunRecord,
    RunStatus,
    TargetDependency,
    TestCounts,
    UsageLocation,
    VerificationSummary,
    VerificationVerdict,
    VersionVerification,
)
from .sandbox_manager import (
    SandboxCleanupError,
    SandboxCreationError,
    SandboxError,
    SandboxInfo,
    SandboxManager,
    SandboxVerificationError,
)

__all__ = [
    "DependencyExitCapsule",
    "EvidenceStatus",
    "MigrationProposal",
    "ProposedAction",
    "RepositoryMetadata",
    "RiskEvidence",
    "RunRecord",
    "RunStatus",
    "SandboxCleanupError",
    "SandboxCreationError",
    "SandboxError",
    "SandboxInfo",
    "SandboxManager",
    "SandboxVerificationError",
    "TargetDependency",
    "TestCounts",
    "UsageLocation",
    "VerificationSummary",
    "VerificationVerdict",
    "VersionVerification",
]
