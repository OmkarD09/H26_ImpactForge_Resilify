"""
test_comparator.py - Unit tests for BaselineComparator.

NOTE: All tests in this file strictly operate on SYNTHETIC test records.
LinkWatch source code is NEVER modified or targeted by these tests.
"""

import pytest

from exitguard.capsule_schema import RunRecord, RunStatus, TestCaseResult, TestCounts
from exitguard.comparator import (
    BaselineComparator,
    ComparisonClassification,
    OverallComparisonVerdict,
)


def _make_run(
    status: RunStatus = RunStatus.FAILED,
    py_ver: str = "3.12.10",
    test_results: list[TestCaseResult] = None,
    block_reason: str = None,
) -> RunRecord:
    """Helper to create synthetic RunRecords for testing."""
    return RunRecord(
        command_args=["python", "-m", "pytest"],
        python_version=py_ver,
        platform="Windows-AMD64",
        status=status,
        block_or_skip_reason=block_reason,
        test_results=test_results or [],
        executed_at="2026-10-15T12:00:00Z",
    )


def test_baseline_failure_remains_pre_existing():
    """Confirms that a pre-existing baseline failure matching signature is classified as PRE_EXISTING_FAILURE."""
    baseline = _make_run(
        status=RunStatus.FAILED,
        test_results=[
            TestCaseResult(node_id="tests/test_ok.py::test_one", status="PASSED"),
            TestCaseResult(
                node_id="tests/test_report.py::test_report_renders_all_sites",
                status="FAILED",
                failure_signature="ImportError: cannot import name 'soft_unicode' from 'markupsafe'",
            ),
        ],
    )
    candidate = _make_run(
        status=RunStatus.FAILED,
        test_results=[
            TestCaseResult(node_id="tests/test_ok.py::test_one", status="PASSED"),
            TestCaseResult(
                node_id="tests/test_report.py::test_report_renders_all_sites",
                status="FAILED",
                failure_signature="ImportError: cannot import name 'soft_unicode' from 'markupsafe'",
            ),
        ],
    )

    comparison = BaselineComparator.compare_runs(baseline, candidate)

    assert comparison.is_conclusive is True
    assert comparison.verdict == OverallComparisonVerdict.PARITY
    assert "tests/test_report.py::test_report_renders_all_sites" in comparison.pre_existing_failures
    assert "tests/test_ok.py::test_one" in comparison.tests_still_passing
    assert len(comparison.new_regressions) == 0


def test_baseline_failure_becomes_resolved():
    """Confirms that a pre-existing baseline failure that now passes is classified as RESOLVED_FAILURE."""
    baseline = _make_run(
        status=RunStatus.FAILED,
        test_results=[
            TestCaseResult(node_id="tests/test_ok.py::test_one", status="PASSED"),
            TestCaseResult(
                node_id="tests/test_report.py::test_report_renders_all_sites",
                status="FAILED",
                failure_signature="ImportError: cannot import name 'soft_unicode' from 'markupsafe'",
            ),
        ],
    )
    candidate = _make_run(
        status=RunStatus.PASSED,
        test_results=[
            TestCaseResult(node_id="tests/test_ok.py::test_one", status="PASSED"),
            TestCaseResult(
                node_id="tests/test_report.py::test_report_renders_all_sites",
                status="PASSED",
            ),
        ],
    )

    comparison = BaselineComparator.compare_runs(baseline, candidate)

    assert comparison.is_conclusive is True
    assert comparison.verdict == OverallComparisonVerdict.IMPROVED
    assert "tests/test_report.py::test_report_renders_all_sites" in comparison.resolved_failures
    assert len(comparison.new_regressions) == 0


def test_previously_passing_test_becomes_regression():
    """Confirms that a previously passing test that now fails is classified as NEW_REGRESSION."""
    baseline = _make_run(
        status=RunStatus.PASSED,
        test_results=[
            TestCaseResult(node_id="tests/test_ok.py::test_one", status="PASSED"),
        ],
    )
    candidate = _make_run(
        status=RunStatus.FAILED,
        test_results=[
            TestCaseResult(
                node_id="tests/test_ok.py::test_one",
                status="FAILED",
                failure_signature="AssertionError: assert 1 == 2",
            ),
        ],
    )

    comparison = BaselineComparator.compare_runs(baseline, candidate)

    assert comparison.is_conclusive is True
    assert comparison.verdict == OverallComparisonVerdict.REGRESSION
    assert "tests/test_ok.py::test_one" in comparison.new_regressions


def test_passing_test_remains_passing():
    """Confirms that passing tests in both runs are classified as STILL_PASSING."""
    baseline = _make_run(
        status=RunStatus.PASSED,
        test_results=[
            TestCaseResult(node_id="tests/test_ok.py::test_one", status="PASSED"),
            TestCaseResult(node_id="tests/test_ok.py::test_two", status="PASSED"),
        ],
    )
    candidate = _make_run(
        status=RunStatus.PASSED,
        test_results=[
            TestCaseResult(node_id="tests/test_ok.py::test_one", status="PASSED"),
            TestCaseResult(node_id="tests/test_ok.py::test_two", status="PASSED"),
        ],
    )

    comparison = BaselineComparator.compare_runs(baseline, candidate)

    assert comparison.is_conclusive is True
    assert comparison.verdict == OverallComparisonVerdict.PARITY
    assert set(comparison.tests_still_passing) == {
        "tests/test_ok.py::test_one",
        "tests/test_ok.py::test_two",
    }


def test_missing_candidate_or_baseline_is_inconclusive():
    """Confirms that comparing against None returns INCONCLUSIVE."""
    baseline = _make_run(status=RunStatus.PASSED, test_results=[TestCaseResult(node_id="test", status="PASSED")])

    comp1 = BaselineComparator.compare_runs(baseline, None)
    assert comp1.is_conclusive is False
    assert comp1.verdict == OverallComparisonVerdict.INCONCLUSIVE

    comp2 = BaselineComparator.compare_runs(None, baseline)
    assert comp2.is_conclusive is False
    assert comp2.verdict == OverallComparisonVerdict.INCONCLUSIVE


def test_blocked_timed_out_and_not_run_records_are_inconclusive():
    """Confirms that runs with status BLOCKED, TIMED_OUT, or NOT_RUN return INCONCLUSIVE."""
    baseline = _make_run(status=RunStatus.PASSED, test_results=[TestCaseResult(node_id="test", status="PASSED")])

    for bad_status in [RunStatus.BLOCKED, RunStatus.TIMED_OUT, RunStatus.NOT_RUN]:
        candidate = _make_run(status=bad_status, block_reason=f"Status was {bad_status.value}")
        comparison = BaselineComparator.compare_runs(baseline, candidate)
        assert comparison.is_conclusive is False
        assert comparison.verdict == OverallComparisonVerdict.INCONCLUSIVE
        assert any(bad_status.value in r for r in comparison.inconclusive_reasons)


def test_python_version_mismatches_are_not_compared():
    """Confirms that attempting to compare Python 3.12 with Python 3.13 returns INCONCLUSIVE."""
    baseline = _make_run(py_ver="3.12.10", test_results=[TestCaseResult(node_id="test", status="PASSED")])
    candidate = _make_run(py_ver="3.13.0", test_results=[TestCaseResult(node_id="test", status="PASSED")])

    comparison = BaselineComparator.compare_runs(baseline, candidate)

    assert comparison.is_conclusive is False
    assert comparison.verdict == OverallComparisonVerdict.INCONCLUSIVE
    assert any("version mismatch" in r.lower() for r in comparison.inconclusive_reasons)


def test_changed_failure_signatures_are_flagged_for_review():
    """Confirms that different root causes on the same test node are flagged as CHANGED_FAILURE_SIGNATURE."""
    baseline = _make_run(
        status=RunStatus.FAILED,
        test_results=[
            TestCaseResult(
                node_id="tests/test_report.py::test_render",
                status="FAILED",
                failure_signature="ImportError: cannot import name 'soft_unicode' from 'markupsafe'",
            ),
        ],
    )
    candidate = _make_run(
        status=RunStatus.FAILED,
        test_results=[
            TestCaseResult(
                node_id="tests/test_report.py::test_render",
                status="FAILED",
                failure_signature="ZeroDivisionError: division by zero in report template",
            ),
        ],
    )

    comparison = BaselineComparator.compare_runs(baseline, candidate)

    assert comparison.is_conclusive is False
    assert comparison.verdict == OverallComparisonVerdict.INCONCLUSIVE
    assert "tests/test_report.py::test_render" in comparison.changed_failure_signatures


def test_collection_differences_are_reported():
    """Confirms that tests present in one run but missing in the other are reported as COLLECTION_DIFFERENCE."""
    baseline = _make_run(
        status=RunStatus.PASSED,
        test_results=[
            TestCaseResult(node_id="tests/test_a.py::test_a", status="PASSED"),
            TestCaseResult(node_id="tests/test_b.py::test_b", status="PASSED"),
        ],
    )
    candidate = _make_run(
        status=RunStatus.PASSED,
        test_results=[
            TestCaseResult(node_id="tests/test_a.py::test_a", status="PASSED"),
            TestCaseResult(node_id="tests/test_c.py::test_c", status="PASSED"),
        ],
    )

    comparison = BaselineComparator.compare_runs(baseline, candidate)

    assert comparison.is_conclusive is False
    assert comparison.verdict == OverallComparisonVerdict.INCONCLUSIVE
    assert set(comparison.collection_differences) == {
        "tests/test_b.py::test_b",
        "tests/test_c.py::test_c",
    }


def test_zero_new_regressions_does_not_imply_verified_success():
    """Confirms that having zero regressions with an existing failure yields PARITY, not an unverified success claim."""
    baseline = _make_run(
        status=RunStatus.FAILED,
        test_results=[
            TestCaseResult(node_id="tests/test_ok.py::test_1", status="PASSED"),
            TestCaseResult(
                node_id="tests/test_report.py::test_fail",
                status="FAILED",
                failure_signature="ImportError: cannot import name 'soft_unicode' from 'markupsafe'",
            ),
        ],
    )
    candidate = _make_run(
        status=RunStatus.FAILED,
        test_results=[
            TestCaseResult(node_id="tests/test_ok.py::test_1", status="PASSED"),
            TestCaseResult(
                node_id="tests/test_report.py::test_fail",
                status="FAILED",
                failure_signature="ImportError: cannot import name 'soft_unicode' from 'markupsafe'",
            ),
        ],
    )

    comparison = BaselineComparator.compare_runs(baseline, candidate)

    assert comparison.verdict == OverallComparisonVerdict.PARITY
    assert comparison.verdict != OverallComparisonVerdict.IMPROVED
    assert len(comparison.new_regressions) == 0
    assert len(comparison.pre_existing_failures) == 1
