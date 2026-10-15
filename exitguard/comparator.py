"""
comparator.py - Deterministic Baseline Comparator for Migration Verification.

Part of ExitGuard (Member 3: Migration Verification).

Deterministic Comparison Rules:
  1. Compares test outcomes strictly on equivalent execution environments (same Python version).
  2. Categorizes each test case into:
     - STILL_PASSING: passed in baseline, passed in candidate.
     - PRE_EXISTING_FAILURE: failed in baseline and fails with matching signature in candidate.
     - RESOLVED_FAILURE: failed in baseline, now passes in candidate.
     - NEW_REGRESSION: passed in baseline, now fails in candidate.
     - CHANGED_FAILURE_SIGNATURE: failed in baseline and candidate, but with a different root cause.
     - COLLECTION_DIFFERENCE: test exists in only one of the runs.
  3. Strict Epistemological Integrity:
     - Blocked, timed out, or unexecuted runs are never treated as passing.
     - Missing candidate or baseline evidence returns INCONCLUSIVE.
     - Python 3.12 cannot be compared against Python 3.13 as equivalent.
     - Zero new regressions does NOT automatically imply full behavioral equivalence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .capsule_schema import (
    RunRecord,
    RunStatus,
    TestCaseResult,
    VerificationVerdict,
)


class ComparisonClassification(str, Enum):
    """Classification for an individual test case across baseline and candidate."""
    STILL_PASSING = "STILL_PASSING"
    PRE_EXISTING_FAILURE = "PRE_EXISTING_FAILURE"
    RESOLVED_FAILURE = "RESOLVED_FAILURE"
    NEW_REGRESSION = "NEW_REGRESSION"
    CHANGED_FAILURE_SIGNATURE = "CHANGED_FAILURE_SIGNATURE"
    COLLECTION_DIFFERENCE = "COLLECTION_DIFFERENCE"
    INCONCLUSIVE = "INCONCLUSIVE"


class OverallComparisonVerdict(str, Enum):
    """Deterministic verdict comparing candidate run against baseline."""
    PARITY = "PARITY"
    IMPROVED = "IMPROVED"
    REGRESSION = "REGRESSION"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class TestCaseComparison:
    """Detailed comparative record for a single test node ID."""
    node_id: str
    classification: ComparisonClassification
    baseline_status: Optional[str]
    candidate_status: Optional[str]
    baseline_signature: Optional[str] = None
    candidate_signature: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class RunComparison:
    """
    Complete deterministic comparison report between baseline and candidate runs.
    """
    verdict: OverallComparisonVerdict
    python_version: str
    is_conclusive: bool
    summary: str
    tests_still_passing: List[str] = field(default_factory=list)
    pre_existing_failures: List[str] = field(default_factory=list)
    resolved_failures: List[str] = field(default_factory=list)
    new_regressions: List[str] = field(default_factory=list)
    changed_failure_signatures: List[str] = field(default_factory=list)
    collection_differences: List[str] = field(default_factory=list)
    inconclusive_reasons: List[str] = field(default_factory=list)
    detailed_comparisons: Dict[str, TestCaseComparison] = field(default_factory=dict)


class BaselineComparator:
    """
    Performs deterministic evaluation between baseline and candidate RunRecords.
    """

    @staticmethod
    def _normalize_signature(sig: Optional[str]) -> str:
        """Normalize failure signature for resilient deterministic matching."""
        if not sig:
            return ""
        # Lowercase and strip whitespace and common noisy prefixes
        norm = sig.strip().lower()
        norm = norm.replace("import... ", "import ")
        return norm

    @classmethod
    def _signatures_match(cls, sig1: Optional[str], sig2: Optional[str]) -> bool:
        """Check if two failure signatures represent the same root cause."""
        s1 = cls._normalize_signature(sig1)
        s2 = cls._normalize_signature(sig2)
        if not s1 or not s2:
            return False

        # Direct equality check
        if s1 == s2:
            return True

        # Check key diagnostic tokens (e.g. 'soft_unicode' and 'markupsafe')
        tokens = ["soft_unicode", "markupsafe"]
        if all(t in s1 for t in tokens) and all(t in s2 for t in tokens):
            return True

        return False

    @classmethod
    def compare_runs(
        cls,
        baseline: Optional[RunRecord],
        candidate: Optional[RunRecord],
        expected_python_version: Optional[str] = None,
    ) -> RunComparison:
        """
        Compare baseline and candidate run records deterministically.
        """
        py_ver = expected_python_version or (baseline.python_version if baseline else "unknown")

        # 1. Check for missing run records
        inconclusive_reasons: List[str] = []
        if baseline is None:
            inconclusive_reasons.append("Missing baseline RunRecord.")
        if candidate is None:
            inconclusive_reasons.append("Missing candidate RunRecord.")

        if inconclusive_reasons:
            return RunComparison(
                verdict=OverallComparisonVerdict.INCONCLUSIVE,
                python_version=py_ver,
                is_conclusive=False,
                summary="Comparison inconclusive: missing run data.",
                inconclusive_reasons=inconclusive_reasons,
            )

        assert baseline is not None
        assert candidate is not None

        # 2. Check for Python version mismatch
        b_major_minor = ".".join(baseline.python_version.split(".")[:2])
        c_major_minor = ".".join(candidate.python_version.split(".")[:2])
        if b_major_minor != c_major_minor:
            inconclusive_reasons.append(
                f"Python version mismatch: baseline is {baseline.python_version}, candidate is {candidate.python_version}."
            )

        # 3. Check for non-executable or interrupted statuses
        for label, run in (("Baseline", baseline), ("Candidate", candidate)):
            if run.status == RunStatus.BLOCKED:
                inconclusive_reasons.append(f"{label} run was BLOCKED: {run.block_or_skip_reason or 'No reason provided.'}")
            elif run.status == RunStatus.NOT_RUN:
                inconclusive_reasons.append(f"{label} run was NOT_RUN: {run.block_or_skip_reason or 'No reason provided.'}")
            elif run.status == RunStatus.TIMED_OUT:
                inconclusive_reasons.append(f"{label} run TIMED_OUT: {run.block_or_skip_reason or 'Exceeded timeout limit.'}")

        # If any execution is not a completed PASSED/FAILED test execution, report inconclusive
        if inconclusive_reasons:
            return RunComparison(
                verdict=OverallComparisonVerdict.INCONCLUSIVE,
                python_version=c_major_minor,
                is_conclusive=False,
                summary="Comparison inconclusive due to environment or execution constraints.",
                inconclusive_reasons=inconclusive_reasons,
            )

        # 4. Extract test results maps
        b_tests: Dict[str, TestCaseResult] = {tr.node_id: tr for tr in (baseline.test_results or [])}
        c_tests: Dict[str, TestCaseResult] = {tr.node_id: tr for tr in (candidate.test_results or [])}

        if not b_tests or not c_tests:
            return RunComparison(
                verdict=OverallComparisonVerdict.INCONCLUSIVE,
                python_version=c_major_minor,
                is_conclusive=False,
                summary="Comparison inconclusive: no detailed test results captured in RunRecord.",
                inconclusive_reasons=["Detailed test results (node IDs) missing from one or both runs."],
            )

        all_nodes = sorted(set(b_tests.keys()) | set(c_tests.keys()))

        tests_still_passing: List[str] = []
        pre_existing_failures: List[str] = []
        resolved_failures: List[str] = []
        new_regressions: List[str] = []
        changed_failure_signatures: List[str] = []
        collection_differences: List[str] = []
        detailed_comparisons: Dict[str, TestCaseComparison] = {}

        # 5. Evaluate each test case
        for node in all_nodes:
            b_res = b_tests.get(node)
            c_res = c_tests.get(node)

            if b_res is None or c_res is None:
                collection_differences.append(node)
                detailed_comparisons[node] = TestCaseComparison(
                    node_id=node,
                    classification=ComparisonClassification.COLLECTION_DIFFERENCE,
                    baseline_status=b_res.status if b_res else None,
                    candidate_status=c_res.status if c_res else None,
                    notes="Test present in only one of the runs.",
                )
                continue

            b_stat = b_res.status
            c_stat = c_res.status

            if b_stat == "PASSED" and c_stat == "PASSED":
                tests_still_passing.append(node)
                detailed_comparisons[node] = TestCaseComparison(
                    node_id=node,
                    classification=ComparisonClassification.STILL_PASSING,
                    baseline_status=b_stat,
                    candidate_status=c_stat,
                )

            elif b_stat in ("FAILED", "ERROR") and c_stat == "PASSED":
                resolved_failures.append(node)
                detailed_comparisons[node] = TestCaseComparison(
                    node_id=node,
                    classification=ComparisonClassification.RESOLVED_FAILURE,
                    baseline_status=b_stat,
                    candidate_status=c_stat,
                    baseline_signature=b_res.failure_signature,
                    notes="Pre-existing baseline failure was resolved in candidate.",
                )

            elif b_stat == "PASSED" and c_stat in ("FAILED", "ERROR"):
                new_regressions.append(node)
                detailed_comparisons[node] = TestCaseComparison(
                    node_id=node,
                    classification=ComparisonClassification.NEW_REGRESSION,
                    baseline_status=b_stat,
                    candidate_status=c_stat,
                    candidate_signature=c_res.failure_signature,
                    notes="Previously passing test failed in candidate run (regression).",
                )

            elif b_stat in ("FAILED", "ERROR") and c_stat in ("FAILED", "ERROR"):
                if cls._signatures_match(b_res.failure_signature, c_res.failure_signature):
                    pre_existing_failures.append(node)
                    detailed_comparisons[node] = TestCaseComparison(
                        node_id=node,
                        classification=ComparisonClassification.PRE_EXISTING_FAILURE,
                        baseline_status=b_stat,
                        candidate_status=c_stat,
                        baseline_signature=b_res.failure_signature,
                        candidate_signature=c_res.failure_signature,
                        notes="Failure matches pre-existing baseline failure signature.",
                    )
                else:
                    changed_failure_signatures.append(node)
                    detailed_comparisons[node] = TestCaseComparison(
                        node_id=node,
                        classification=ComparisonClassification.CHANGED_FAILURE_SIGNATURE,
                        baseline_status=b_stat,
                        candidate_status=c_stat,
                        baseline_signature=b_res.failure_signature,
                        candidate_signature=c_res.failure_signature,
                        notes="Failure signature differs from baseline; flagged for review.",
                    )
            else:
                detailed_comparisons[node] = TestCaseComparison(
                    node_id=node,
                    classification=ComparisonClassification.INCONCLUSIVE,
                    baseline_status=b_stat,
                    candidate_status=c_stat,
                )

        # 6. Determine overall verdict
        if new_regressions:
            verdict = OverallComparisonVerdict.REGRESSION
            summary = f"Detected {len(new_regressions)} new regression(s)."
        elif collection_differences:
            verdict = OverallComparisonVerdict.INCONCLUSIVE
            summary = f"Inconclusive: {len(collection_differences)} collection difference(s) detected."
        elif changed_failure_signatures:
            verdict = OverallComparisonVerdict.INCONCLUSIVE
            summary = f"Inconclusive: {len(changed_failure_signatures)} changed failure signature(s) require review."
        elif resolved_failures:
            verdict = OverallComparisonVerdict.IMPROVED
            summary = f"Improved: {len(resolved_failures)} baseline failure(s) resolved with zero new regressions."
        else:
            verdict = OverallComparisonVerdict.PARITY
            summary = f"Parity confirmed: {len(tests_still_passing)} passing tests maintained with zero new regressions."

        return RunComparison(
            verdict=verdict,
            python_version=c_major_minor,
            is_conclusive=verdict != OverallComparisonVerdict.INCONCLUSIVE,
            summary=summary,
            tests_still_passing=tests_still_passing,
            pre_existing_failures=pre_existing_failures,
            resolved_failures=resolved_failures,
            new_regressions=new_regressions,
            changed_failure_signatures=changed_failure_signatures,
            collection_differences=collection_differences,
            inconclusive_reasons=[],
            detailed_comparisons=detailed_comparisons,
        )
