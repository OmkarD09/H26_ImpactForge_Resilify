"""
test_runner.py - Unit tests for ExecutionRunner with Strict Command Policy and Sandbox Isolation.

NOTE: All tests strictly use disposable SYNTHETIC fixtures in temporary directories.
LinkWatch source code is NEVER modified or targeted by these tests.
"""

from pathlib import Path
import subprocess
import sys
import pytest

from exitguard.capsule_schema import RunStatus
from exitguard.execution_runner import (
    DEFAULT_TIMEOUT_SECONDS,
    ExecutionCommand,
    ExecutionRunner,
    RunnerPolicyViolation,
)
from exitguard.sandbox_manager import SandboxInfo, SandboxManager


@pytest.fixture
def synthetic_runner_sandbox(tmp_path: Path):
    """
    Creates a disposable Git repo and a verified sandbox with a simple pytest file.
    """
    source_repo = tmp_path / "synth_repo"
    source_repo.mkdir()

    def _git(args: list[str]):
        subprocess.run(["git", "-C", str(source_repo)] + args, check=True, capture_output=True, text=True)

    _git(["init", "-b", "main"])
    _git(["config", "user.name", "Runner Tester"])
    _git(["config", "user.email", "runner@example.com"])

    # Create dummy tests inside synthetic repo
    test_dir = source_repo / "tests"
    test_dir.mkdir()
    (test_dir / "test_ok.py").write_text(
        "def test_one():\n"
        "    assert 1 == 1\n\n"
        "def test_two():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    (test_dir / "test_fail.py").write_text(
        "def test_broken():\n"
        "    raise ImportError(\"cannot import name 'mock_dep' from 'mock_lib'\")\n",
        encoding="utf-8",
    )
    (test_dir / "test_slow.py").write_text(
        "import time\n"
        "def test_sleep():\n"
        "    time.sleep(10)\n",
        encoding="utf-8",
    )
    (test_dir / "test_secret.py").write_text(
        "def test_leak():\n"
        "    print(\"OLLAMA_API_KEY=sk-super-secret-12345\")\n"
        "    assert True\n",
        encoding="utf-8",
    )

    _git(["add", "."])
    _git(["commit", "-m", "Initial test commit"])
    head_proc = subprocess.run(["git", "-C", str(source_repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
    head_sha = head_proc.stdout.strip()

    # Create sandbox
    sandbox_base = tmp_path / "sandboxes"
    manager = SandboxManager(base_temp_dir=sandbox_base)
    sandbox = manager.create_sandbox(source_repo, commit_sha=head_sha)

    yield {
        "manager": manager,
        "sandbox": sandbox,
        "source_repo": source_repo,
        "commit_sha": head_sha,
        "tmp_path": tmp_path,
    }

    # Teardown
    manager.cleanup_sandbox(sandbox)


def test_approved_command_executes_and_captures_output(synthetic_runner_sandbox, tmp_path: Path):
    """Verifies that an approved pytest command executes successfully and captures structured results."""
    sandbox: SandboxInfo = synthetic_runner_sandbox["sandbox"]
    artifact_dir = tmp_path / "artifacts"
    runner = ExecutionRunner(artifact_dir=artifact_dir)

    cmd = ExecutionCommand(
        executable=sys.executable,
        args=["-m", "pytest", "tests/test_ok.py", "-v"],
        working_dir=sandbox.sandbox_root,
        timeout_seconds=30,
        operation_type="TEST_PYTEST",
    )

    record = runner.run(cmd, sandbox)

    assert record.status == RunStatus.PASSED
    assert record.exit_code == 0
    assert record.test_counts is not None
    assert record.test_counts.passed == 2
    assert record.test_counts.failed == 0
    assert record.test_counts.total == 2
    assert len(record.test_results) == 2
    assert record.duration_ms > 0
    assert record.log_artifact_path is not None
    assert Path(record.log_artifact_path).exists()
    assert "test_ok.py::test_one PASSED" in Path(record.log_artifact_path).read_text(encoding="utf-8")


def test_nonzero_exit_code_is_recorded_as_failed(synthetic_runner_sandbox, tmp_path: Path):
    """Verifies that test failures record exit_code != 0 and status FAILED."""
    sandbox: SandboxInfo = synthetic_runner_sandbox["sandbox"]
    runner = ExecutionRunner(artifact_dir=tmp_path / "artifacts")

    cmd = ExecutionCommand(
        executable=sys.executable,
        args=["-m", "pytest", "tests/test_fail.py", "-v"],
        working_dir=sandbox.sandbox_root,
        timeout_seconds=30,
        operation_type="TEST_PYTEST",
    )

    record = runner.run(cmd, sandbox)

    assert record.status == RunStatus.FAILED
    assert record.exit_code == 1
    assert record.test_counts is not None
    assert record.test_counts.failed == 1
    assert record.test_counts.passed == 0
    assert record.test_results is not None
    assert len(record.test_results) == 1
    assert "ImportError" in (record.test_results[0].failure_signature or "")


def test_timeout_is_recorded_correctly(synthetic_runner_sandbox, tmp_path: Path):
    """Verifies that commands exceeding timeout are aborted and recorded as TIMED_OUT."""
    sandbox: SandboxInfo = synthetic_runner_sandbox["sandbox"]
    runner = ExecutionRunner(artifact_dir=tmp_path / "artifacts")

    cmd = ExecutionCommand(
        executable=sys.executable,
        args=["-m", "pytest", "tests/test_slow.py", "-v"],
        working_dir=sandbox.sandbox_root,
        timeout_seconds=2,
        operation_type="TEST_PYTEST",
    )

    record = runner.run(cmd, sandbox)

    assert record.status == RunStatus.TIMED_OUT
    assert record.block_or_skip_reason is not None
    assert "timed out" in record.block_or_skip_reason.lower()
    assert record.log_artifact_path is not None
    assert Path(record.log_artifact_path).exists()


def test_unsupported_operation_is_blocked(synthetic_runner_sandbox, tmp_path: Path):
    """Verifies that commands with unapproved operation types are blocked."""
    sandbox: SandboxInfo = synthetic_runner_sandbox["sandbox"]
    runner = ExecutionRunner(artifact_dir=tmp_path / "artifacts")

    cmd = ExecutionCommand(
        executable=sys.executable,
        args=["-c", "print('arbitrary code')"],
        working_dir=sandbox.sandbox_root,
        operation_type="ARBITRARY_COMMAND",
    )

    record = runner.run(cmd, sandbox)

    assert record.status == RunStatus.BLOCKED
    assert "unsupported operation_type" in (record.block_or_skip_reason or "").lower()


def test_disallowed_pytest_flag_is_blocked(synthetic_runner_sandbox, tmp_path: Path):
    """Verifies that dangerous pytest flags (e.g. --override-ini) are blocked by policy."""
    sandbox: SandboxInfo = synthetic_runner_sandbox["sandbox"]
    runner = ExecutionRunner(artifact_dir=tmp_path / "artifacts")

    cmd = ExecutionCommand(
        executable=sys.executable,
        args=["-m", "pytest", "--override-ini=addopts=-s", "tests/test_ok.py"],
        working_dir=sandbox.sandbox_root,
        operation_type="TEST_PYTEST",
    )

    record = runner.run(cmd, sandbox)

    assert record.status == RunStatus.BLOCKED
    assert "disallowed pytest flag" in (record.block_or_skip_reason or "").lower()


def test_working_directory_outside_sandbox_is_rejected(synthetic_runner_sandbox, tmp_path: Path):
    """Verifies that an execution targeting a working directory outside the sandbox is rejected."""
    sandbox: SandboxInfo = synthetic_runner_sandbox["sandbox"]
    runner = ExecutionRunner(artifact_dir=tmp_path / "artifacts")

    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()

    cmd = ExecutionCommand(
        executable=sys.executable,
        args=["-m", "pytest", "tests/test_ok.py"],
        working_dir=outside_dir,
        operation_type="TEST_PYTEST",
    )

    record = runner.run(cmd, sandbox)

    assert record.status == RunStatus.BLOCKED
    assert "outside sandbox boundary" in (record.block_or_skip_reason or "").lower()


def test_path_traversal_is_rejected(synthetic_runner_sandbox, tmp_path: Path):
    """Verifies that path traversal attempts (e.g. ../../) are rejected."""
    sandbox: SandboxInfo = synthetic_runner_sandbox["sandbox"]
    runner = ExecutionRunner(artifact_dir=tmp_path / "artifacts")

    traversal_cwd = sandbox.sandbox_root / ".." / ".."

    cmd = ExecutionCommand(
        executable=sys.executable,
        args=["-m", "pytest", "tests/test_ok.py"],
        working_dir=traversal_cwd,
        operation_type="TEST_PYTEST",
    )

    record = runner.run(cmd, sandbox)

    assert record.status == RunStatus.BLOCKED
    assert "outside sandbox boundary" in (record.block_or_skip_reason or "").lower()


def test_invalid_or_missing_executable_is_handled_safely(synthetic_runner_sandbox, tmp_path: Path):
    """Verifies that nonexistent or invalid executables return BLOCKED instead of crashing."""
    sandbox: SandboxInfo = synthetic_runner_sandbox["sandbox"]
    runner = ExecutionRunner(artifact_dir=tmp_path / "artifacts")

    cmd = ExecutionCommand(
        executable=sandbox.sandbox_root / "nonexistent_python_binary",
        args=["-m", "pytest"],
        working_dir=sandbox.sandbox_root,
        operation_type="TEST_PYTEST",
    )

    record = runner.run(cmd, sandbox)

    assert record.status == RunStatus.BLOCKED
    assert "executable does not exist" in (record.block_or_skip_reason or "").lower()


def test_secrets_are_redacted_in_logs(synthetic_runner_sandbox, tmp_path: Path):
    """Verifies that sensitive credentials are scrubbed from runner logs."""
    sandbox: SandboxInfo = synthetic_runner_sandbox["sandbox"]
    runner = ExecutionRunner(artifact_dir=tmp_path / "artifacts")

    cmd = ExecutionCommand(
        executable=sys.executable,
        args=["-m", "pytest", "tests/test_secret.py", "-s"],
        working_dir=sandbox.sandbox_root,
        operation_type="TEST_PYTEST",
    )

    record = runner.run(cmd, sandbox)

    assert record.status == RunStatus.PASSED
    assert record.log_artifact_path is not None
    log_content = Path(record.log_artifact_path).read_text(encoding="utf-8")
    assert "sk-super-secret-12345" not in log_content
    assert "[REDACTED_SECRET]" in log_content


def test_source_repo_immutability_during_run(synthetic_runner_sandbox, tmp_path: Path):
    """Verifies that executing tests inside the sandbox does not alter the source repository."""
    source_repo: Path = synthetic_runner_sandbox["source_repo"]
    sandbox: SandboxInfo = synthetic_runner_sandbox["sandbox"]
    runner = ExecutionRunner(artifact_dir=tmp_path / "artifacts")

    cmd = ExecutionCommand(
        executable=sys.executable,
        args=["-m", "pytest", "tests/test_ok.py"],
        working_dir=sandbox.sandbox_root,
        operation_type="TEST_PYTEST",
    )

    runner.run(cmd, sandbox)

    # Check git status of source repository
    status_proc = subprocess.run(
        ["git", "-C", str(source_repo), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert status_proc.stdout.strip() == "", "Source repository was modified during sandbox execution!"
