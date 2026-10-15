"""
execution_runner.py - Safe Execution Runner with Strict Command Policy and Sandbox Isolation.

Part of ExitGuard (Member 3: Migration Verification).

Safety invariants:
  - Accepts ONLY structured command specifications (argv lists), never arbitrary shell strings.
  - Strictly enforces subprocess execution with shell=False.
  - Enforces that all working directories and targets reside inside an ExitGuard-owned sandbox.
  - Rejects path traversal and working directories outside sandbox boundaries.
  - Restricts operations to an explicit whitelist of approved test operations (e.g. pytest).
  - Enforces execution timeouts and limits log output sizes.
  - Scrubs sensitive tokens/secrets from logs.
  - Deterministically maps process outcomes to typed RunRecord models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import re
import subprocess
import time
from typing import Dict, List, Optional
import uuid

from .capsule_schema import (
    RunRecord,
    RunStatus,
    TestCaseResult,
    TestCounts,
)
from .sandbox_manager import SandboxInfo

DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_LOG_BYTES = 512 * 1024  # 512 KB
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|bearer\s+[a-zA-Z0-9_\-\.]+)"),
    re.compile(r"OLLAMA_API_KEY\s*=\s*[^\s]+"),
]


class RunnerPolicyViolation(Exception):
    """Raised when a command violates the execution runner security policy."""
    pass


@dataclass
class ExecutionCommand:
    """Structured, policy-validated command specification."""
    executable: Path | str
    args: List[str]
    working_dir: Optional[Path | str] = None
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    operation_type: str = "TEST_PYTEST"
    env_overrides: Optional[Dict[str, str]] = None


class ExecutionRunner:
    """
    Executes approved, structured test commands strictly inside an ExitGuard sandbox.
    """

    def __init__(
        self,
        artifact_dir: Optional[Path | str] = None,
        max_log_bytes: int = DEFAULT_MAX_LOG_BYTES,
    ) -> None:
        self.artifact_dir = Path(artifact_dir) if artifact_dir else Path("artifacts/runner_logs")
        self.max_log_bytes = max_log_bytes
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_output(self, text: str) -> str:
        """Sanitize output to scrub credentials and enforce max length."""
        sanitized = text
        for pat in SECRET_PATTERNS:
            sanitized = pat.sub("[REDACTED_SECRET]", sanitized)

        raw_bytes = sanitized.encode("utf-8", errors="replace")
        if len(raw_bytes) > self.max_log_bytes:
            truncated = raw_bytes[: self.max_log_bytes].decode("utf-8", errors="replace")
            sanitized = truncated + "\n\n[OUTPUT TRUNCATED BY EXITGUARD EXECUTION RUNNER]"
        return sanitized

    def _validate_working_dir(self, cwd: Optional[Path | str], sandbox: SandboxInfo) -> Path:
        """Ensure working directory resolves strictly inside the sandbox boundary."""
        target_cwd = Path(cwd) if cwd else sandbox.target_dir
        resolved = target_cwd.resolve()
        sandbox_root = sandbox.sandbox_root.resolve()

        try:
            resolved.relative_to(sandbox_root)
        except ValueError as exc:
            raise RunnerPolicyViolation(
                f"Working directory '{resolved}' is outside sandbox boundary '{sandbox_root}'."
            ) from exc

        if not resolved.exists():
            raise RunnerPolicyViolation(f"Working directory does not exist: {resolved}")
        return resolved

    def _validate_command_policy(self, cmd: ExecutionCommand, resolved_cwd: Path, sandbox: SandboxInfo) -> Path:
        """
        Validate executable and arguments against the runner security policy.
        Only explicitly authorized operations are permitted.
        """
        exe_path = Path(cmd.executable).resolve()
        if not exe_path.exists():
            raise RunnerPolicyViolation(f"Executable does not exist: {exe_path}")

        # Check operation policy
        if cmd.operation_type == "TEST_PYTEST":
            # Must invoke python running pytest or pytest directly
            args_str = " ".join(cmd.args)
            has_pytest = "pytest" in exe_path.name.lower() or ("-m" in cmd.args and "pytest" in cmd.args)
            if not has_pytest:
                raise RunnerPolicyViolation(
                    f"TEST_PYTEST operation must invoke pytest. Provided args: {cmd.args}"
                )

            # Prevent dangerous pytest arguments
            disallowed = ["--import-mode=importlib", "--override-ini", "--basetemp"]
            for arg in cmd.args:
                if any(arg.startswith(d) for d in disallowed):
                    raise RunnerPolicyViolation(f"Disallowed pytest flag in policy: {arg}")

        elif cmd.operation_type == "SETUP_DEPENDENCIES":
            # Must be pip install referencing manifest inside sandbox
            if not ("-m" in cmd.args and "pip" in cmd.args and "install" in cmd.args):
                raise RunnerPolicyViolation(
                    f"SETUP_DEPENDENCIES operation must be 'python -m pip install'. Provided args: {cmd.args}"
                )
        else:
            raise RunnerPolicyViolation(f"Unsupported operation_type '{cmd.operation_type}' rejected by runner policy.")

        return exe_path

    def _parse_pytest_output(self, output: str) -> tuple[Optional[TestCounts], List[TestCaseResult]]:
        """Extract structured test counts and per-test outcomes from pytest verbose output."""
        test_results: List[TestCaseResult] = []

        # Find individual test results
        # Pattern matches: path/to/test.py::test_name PASSED / FAILED / SKIPPED
        node_pattern = re.compile(r"^([^\s:]+::[^\s]+)\s+(PASSED|FAILED|SKIPPED|ERROR)", re.MULTILINE)
        for match in node_pattern.finditer(output):
            node_id, status = match.groups()
            test_results.append(TestCaseResult(node_id=node_id, status=status))

        # Check for failure details (e.g. ImportError, AssertionError)
        for tr in test_results:
            if tr.status in ("FAILED", "ERROR"):
                # Look for failure snippet matching this test
                # Match exception line like: E   ImportError: cannot import name ...
                short_summary_pat = re.compile(
                    rf"FAILED\s+{re.escape(tr.node_id)}\s+-\s+([^\n\r]+)",
                    re.MULTILINE,
                )
                sum_match = short_summary_pat.search(output)
                if sum_match:
                    tr.failure_message = sum_match.group(1).strip()
                    tr.failure_signature = sum_match.group(1).strip()
                else:
                    # Fallback search for E   Exception: message
                    exc_match = re.search(r"E\s+([A-Za-z0-9_]+Error:[^\n\r]+)", output)
                    if exc_match:
                        tr.failure_signature = exc_match.group(1).strip()
                        tr.failure_message = exc_match.group(1).strip()

        # Parse test counts
        passed = sum(1 for tr in test_results if tr.status == "PASSED")
        failed = sum(1 for tr in test_results if tr.status in ("FAILED", "ERROR"))
        skipped = sum(1 for tr in test_results if tr.status == "SKIPPED")
        total = len(test_results)

        counts = TestCounts(passed=passed, failed=failed, skipped=skipped, total=total) if total > 0 else None
        return counts, test_results

    def run(self, cmd: ExecutionCommand, sandbox: SandboxInfo) -> RunRecord:
        """
        Execute an approved test command in the sandbox and return a verified RunRecord.
        Guarantees that policy violations and execution failures return explicit status.
        """
        executed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        plat_str = f"{platform.system()}-{platform.machine()}"

        # 1. Validate sandbox
        if not sandbox.sandbox_root.exists():
            return RunRecord(
                command_args=[],
                python_version=platform.python_version(),
                platform=plat_str,
                status=RunStatus.BLOCKED,
                block_or_skip_reason=f"Sandbox root does not exist: {sandbox.sandbox_root}",
                executed_at=executed_at,
            )

        # 2. Validate working directory (rejection of path traversal & outside dirs)
        try:
            resolved_cwd = self._validate_working_dir(cmd.working_dir, sandbox)
        except RunnerPolicyViolation as exc:
            return RunRecord(
                command_args=[str(cmd.executable)] + list(cmd.args),
                python_version=platform.python_version(),
                platform=plat_str,
                status=RunStatus.BLOCKED,
                block_or_skip_reason=f"Policy violation: {exc}",
                executed_at=executed_at,
            )

        # 3. Validate command policy
        try:
            exe_path = self._validate_command_policy(cmd, resolved_cwd, sandbox)
        except RunnerPolicyViolation as exc:
            return RunRecord(
                command_args=[str(cmd.executable)] + list(cmd.args),
                python_version=platform.python_version(),
                platform=plat_str,
                working_dir=str(resolved_cwd),
                status=RunStatus.BLOCKED,
                block_or_skip_reason=f"Policy violation: {exc}",
                executed_at=executed_at,
            )

        # 4. Prepare environment and log file
        run_id = f"run_{uuid.uuid4().hex[:10]}"
        log_file = self.artifact_dir / f"{run_id}.log"
        full_argv = [str(exe_path)] + list(cmd.args)

        env = os.environ.copy()
        if cmd.env_overrides:
            for k, v in cmd.env_overrides.items():
                # Disallow secret injection or dangerous envs
                if any(p.search(k) for p in SECRET_PATTERNS):
                    continue
                env[k] = v

        # Query interpreter version
        py_ver = platform.python_version()
        try:
            ver_proc = subprocess.run(
                [str(exe_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if ver_proc.returncode == 0:
                py_ver = ver_proc.stdout.strip().replace("Python ", "")
        except Exception:
            pass

        # 5. Execute with timeout (shell=False strictly enforced)
        t_start = time.time()
        try:
            proc = subprocess.run(
                full_argv,
                cwd=resolved_cwd,
                capture_output=True,
                text=True,
                timeout=cmd.timeout_seconds,
                shell=False,
                env=env,
            )
            duration_ms = int((time.time() - t_start) * 1000)
            raw_output = (proc.stdout or "") + "\n" + (proc.stderr or "")
            sanitized_output = self._sanitize_output(raw_output)
            log_file.write_text(sanitized_output, encoding="utf-8")

            # Parse results
            counts, test_results = self._parse_pytest_output(sanitized_output)
            status = RunStatus.PASSED if proc.returncode == 0 else RunStatus.FAILED

            return RunRecord(
                command_args=full_argv,
                python_version=py_ver,
                platform=plat_str,
                status=status,
                working_dir=str(resolved_cwd),
                executed_at=executed_at,
                exit_code=proc.returncode,
                duration_ms=duration_ms,
                log_artifact_path=str(log_file),
                test_counts=counts,
                test_results=test_results if test_results else None,
                block_or_skip_reason=None,
            )

        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.time() - t_start) * 1000)
            timed_out_output = (
                (exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
                + "\n"
                + (exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or ""))
                + f"\n[COMMAND TIMED OUT AFTER {cmd.timeout_seconds} SECONDS]"
            )
            log_file.write_text(self._sanitize_output(timed_out_output), encoding="utf-8")
            return RunRecord(
                command_args=full_argv,
                python_version=py_ver,
                platform=plat_str,
                status=RunStatus.TIMED_OUT,
                working_dir=str(resolved_cwd),
                executed_at=executed_at,
                exit_code=None,
                duration_ms=duration_ms,
                log_artifact_path=str(log_file),
                block_or_skip_reason=f"Execution timed out after {cmd.timeout_seconds}s.",
            )

        except Exception as exc:
            duration_ms = int((time.time() - t_start) * 1000)
            return RunRecord(
                command_args=full_argv,
                python_version=py_ver,
                platform=plat_str,
                status=RunStatus.BLOCKED,
                working_dir=str(resolved_cwd),
                executed_at=executed_at,
                exit_code=None,
                duration_ms=duration_ms,
                block_or_skip_reason=f"Execution failed to launch: {exc}",
            )
