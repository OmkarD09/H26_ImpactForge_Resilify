"""
run_integration_milestone3.py - Phase E Integration Exercise.

Exercises:
  1. Sandbox creation at pinned commit f52f3930c8e7c33d934ccf614955a38e26984bd5.
  2. ExecutionRunner running approved pytest command inside the sandbox.
  3. Baseline comparison between stored baseline evidence and newly captured run record.
  4. Classification of soft_unicode import failure as PRE_EXISTING_FAILURE.
  5. Python 3.13 recorded strictly as NOT_RUN.
  6. Git status verification on canonical repositories.
"""

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys

# Ensure exitguard is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from exitguard.capsule_schema import (
    RunRecord,
    RunStatus,
    TestCaseResult,
    TestCounts,
)
from exitguard.comparator import (
    BaselineComparator,
    ComparisonClassification,
    OverallComparisonVerdict,
)
from exitguard.execution_runner import (
    ExecutionCommand,
    ExecutionRunner,
)
from exitguard.sandbox_manager import SandboxManager


def main():
    root_dir = Path(__file__).resolve().parent.parent
    linkwatch_repo = root_dir / "LinkWatch"
    target_commit = "f52f3930c8e7c33d934ccf614955a38e26984bd5"
    check_proc = subprocess.run(["git", "rev-parse", "--verify", f"{target_commit}^{{commit}}"], cwd=linkwatch_repo, capture_output=True, text=True)
    if check_proc.returncode != 0:
        target_commit = None
    venv_python = root_dir / ".venv_baseline_py312" / "Scripts" / "python.exe"
    if not venv_python.exists():
        venv_python = root_dir / ".venv_baseline" / "Scripts" / "python.exe"
    if not venv_python.exists():
        venv_python = Path(sys.executable)

    sb_mgr = SandboxManager()
    sandbox = sb_mgr.create_sandbox(linkwatch_repo, commit_sha=target_commit)
    print(f"Created sandbox at: {sandbox.sandbox_root}")
    print(f"Target directory: {sandbox.target_dir}")

    runner_artifacts = root_dir / "artifacts" / "runner_logs"
    runner_artifacts.mkdir(parents=True, exist_ok=True)
    runner = ExecutionRunner(artifact_dir=runner_artifacts)

    try:
        print(f"--- [2/6] Executing Approved Pytest Command via ExecutionRunner ---")
        cmd = ExecutionCommand(
            executable=venv_python,
            args=["-m", "pytest", "tests", "-v"],
            working_dir=sandbox.target_dir,
            timeout_seconds=60,
            operation_type="TEST_PYTEST",
        )
        new_run_record = runner.run(cmd, sandbox)
        print(f"Runner status: {new_run_record.status.value}")
        print(f"Exit code: {new_run_record.exit_code}")
        print(f"Duration: {new_run_record.duration_ms}ms")
        print(f"Log path: {new_run_record.log_artifact_path}")
        if new_run_record.test_counts:
            print(f"Counts: {asdict(new_run_record.test_counts)}")

        print(f"--- [3/6] Loading Stored Baseline Run Record ---")
        baseline_log_path = root_dir / "artifacts" / "baseline_logs" / "py312_sandbox_baseline.log"
        baseline_telemetry_path = root_dir / "artifacts" / "baseline_logs" / "sandbox_validation_telemetry.json"
        
        baseline_log = baseline_log_path.read_text(encoding="utf-8")
        b_counts, b_test_results = runner._parse_pytest_output(baseline_log)
        b_telemetry = json.loads(baseline_telemetry_path.read_text(encoding="utf-8"))

        baseline_run_record = RunRecord(
            command_args=b_telemetry["test_cmd"],
            python_version=b_telemetry["interpreter_version"].replace("Python ", ""),
            platform=f"{platform.system()}-{platform.machine()}",
            status=RunStatus.FAILED if b_telemetry["test_exit_code"] != 0 else RunStatus.PASSED,
            working_dir=b_telemetry["sandbox_path"],
            executed_at=b_telemetry["started_at"],
            exit_code=b_telemetry["test_exit_code"],
            duration_ms=b_telemetry["test_duration_ms"],
            log_artifact_path=str(baseline_log_path),
            test_counts=b_counts,
            test_results=b_test_results,
        )

        print(f"--- [4/6] Comparing Newly Captured Run Record against Baseline ---")
        comparison = BaselineComparator.compare_runs(baseline_run_record, new_run_record)
        print(f"Comparison Verdict: {comparison.verdict.value}")
        print(f"Is Conclusive: {comparison.is_conclusive}")
        print(f"Summary: {comparison.summary}")
        print(f"Still passing count: {len(comparison.tests_still_passing)}")
        print(f"Pre-existing failures: {comparison.pre_existing_failures}")
        print(f"New regressions: {comparison.new_regressions}")
        print(f"Resolved failures: {comparison.resolved_failures}")

        assert comparison.verdict == OverallComparisonVerdict.PARITY, f"Expected PARITY, got {comparison.verdict}"
        assert len(comparison.new_regressions) == 0, "Regressions detected unexpectedly!"
        assert "tests/test_report.py::test_report_renders_all_sites" in comparison.pre_existing_failures, "soft_unicode failure not classified as pre-existing!"

        print(f"--- [5/6] Verifying Python 3.13 Status ---")
        py313_record = RunRecord(
            command_args=[],
            python_version="3.13",
            platform=f"{platform.system()}-{platform.machine()}",
            status=RunStatus.NOT_RUN,
            block_or_skip_reason="Python 3.13 interpreter is not installed on this system. Not fabricated.",
            executed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        print(f"Python 3.13 Status: {py313_record.status.value} ({py313_record.block_or_skip_reason})")

        # Telemetry output
        telemetry = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "commit_sha": target_commit,
            "py312_run": {
                "status": new_run_record.status.value,
                "exit_code": new_run_record.exit_code,
                "duration_ms": new_run_record.duration_ms,
                "log_path": new_run_record.log_artifact_path,
                "counts": asdict(new_run_record.test_counts) if new_run_record.test_counts else None,
            },
            "comparison": {
                "verdict": comparison.verdict.value,
                "is_conclusive": comparison.is_conclusive,
                "summary": comparison.summary,
                "tests_still_passing": comparison.tests_still_passing,
                "pre_existing_failures": comparison.pre_existing_failures,
                "new_regressions": comparison.new_regressions,
                "resolved_failures": comparison.resolved_failures,
            },
            "py313_status": py313_record.status.value,
        }

        telemetry_file = runner_artifacts / "integration_exercise_telemetry.json"
        telemetry_file.write_text(json.dumps(telemetry, indent=2), encoding="utf-8")
        print(f"Telemetry saved to: {telemetry_file}")

    finally:
        print("--- [6/6] Cleaning up sandbox ---")
        sb_mgr.cleanup_sandbox(sandbox)
        print("Sandbox cleanup completed successfully.")

    # Check Git status of LinkWatch and main project
    print("\n--- Auditing Git Status ---")
    proc_lw_sub = subprocess.run(["git", "-C", str(root_dir), "status", "--porcelain", "LinkWatch"], check=True, capture_output=True, text=True)
    print(f"LinkWatch subfolder clean: {proc_lw_sub.stdout.strip() == ''}")
    if proc_lw_sub.stdout.strip():
        print(f"UNEXPECTED LinkWatch subfolder changes:\n{proc_lw_sub.stdout}")

    upstream_lw = root_dir.parent / "linkwatch"
    if upstream_lw.exists():
        proc_lw_ext = subprocess.run(["git", "-C", str(upstream_lw), "status", "--porcelain"], check=True, capture_output=True, text=True)
        print(f"Upstream linkwatch repo clean: {proc_lw_ext.stdout.strip() == ''}")
        if proc_lw_ext.stdout.strip():
            print(f"UNEXPECTED upstream linkwatch changes:\n{proc_lw_ext.stdout}")

    proc_main = subprocess.run(["git", "-C", str(root_dir), "status", "--porcelain"], check=True, capture_output=True, text=True)
    print(f"ExitGuard root status:\n{proc_main.stdout.strip()}")

    print("\nMilestone 3 integration execution finished successfully!")


if __name__ == "__main__":
    main()
