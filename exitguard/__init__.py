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
    TestCaseResult,
    TestCounts,
    UsageLocation,
    VerificationSummary,
    VerificationVerdict,
    VersionVerification,
)
from .candidate_evaluator import (
    CandidateEvaluation,
    CandidateEvaluator,
)
from .comparator import (
    BaselineComparator,
    ComparisonClassification,
    OverallComparisonVerdict,
    RunComparison,
    TestCaseComparison,
)
from .execution_runner import (
    DEFAULT_MAX_LOG_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    ExecutionCommand,
    ExecutionRunner,
    RunnerPolicyViolation,
)
from .gemma_advisor import (
    HOSTED_GEMMA_MODEL_ID,
    GemmaAdviceRecord,
    GemmaAdvisor,
    GemmaRecommendation,
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
    "BaselineComparator",
    "CandidateEvaluation",
    "CandidateEvaluator",
    "ComparisonClassification",
    "DEFAULT_MAX_LOG_BYTES",
    "DEFAULT_TIMEOUT_SECONDS",
    "DependencyExitCapsule",
    "EvidenceStatus",
    "ExecutionCommand",
    "ExecutionRunner",
    "GemmaAdviceRecord",
    "GemmaAdvisor",
    "GemmaRecommendation",
    "HOSTED_GEMMA_MODEL_ID",
    "MigrationProposal",
    "OverallComparisonVerdict",
    "ProposedAction",
    "RepositoryMetadata",
    "RiskEvidence",
    "RunComparison",
    "RunRecord",
    "RunStatus",
    "RunnerPolicyViolation",
    "SandboxCleanupError",
    "SandboxCreationError",
    "SandboxError",
    "SandboxInfo",
    "SandboxManager",
    "SandboxVerificationError",
    "TargetDependency",
    "TestCaseComparison",
    "TestCaseResult",
    "TestCounts",
    "UsageLocation",
    "VerificationSummary",
    "VerificationVerdict",
    "VersionVerification",
]
