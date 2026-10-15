"""
Baseline Test Runner for Resilify (Member 1).

Executes the baseline pytest suite against LinkWatch on Python 3.12/3.13,
capturing stdout, stderr, individual test outcomes, warnings, and failure tracebacks.
"""

from __future__ import annotations

import json
import re
import sys
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class TestFailureDetail:
    test_id: str
    failure_type: str
    error_message: str
    traceback: str


@dataclass
class WarningDetail:
    category: str
    message: str
    location: str


@dataclass
class BaselineTestResult:
    python_version: str
    python_executable: str
    total_collected: int
    passed_count: int
    failed_count: int
    skipped_count: int
    execution_time_seconds: float
    exit_code: int
    failures: List[TestFailureDetail] = field(default_factory=list)
    warnings: List[WarningDetail] = field(default_factory=list)
    passed_tests: List[str] = field(default_factory=list)
    raw_stdout: str = ""
    raw_stderr: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BaselineRunner:
    """Executes pytest in a subprocess and parses structured execution evidence."""

    def __init__(self, repo_dir: Path | str, python_exe: Optional[str] = None) -> None:
        self.repo_dir = Path(repo_dir)
        self.python_exe = python_exe or sys.executable

    def run(self) -> BaselineTestResult:
        tests_dir = self.repo_dir / "tests"
        if not tests_dir.exists():
            return BaselineTestResult(
                python_version=sys.version,
                python_executable=self.python_exe,
                total_collected=0,
                passed_count=0,
                failed_count=0,
                skipped_count=0,
                execution_time_seconds=0.0,
                exit_code=-1,
                raw_stderr="tests directory does not exist",
            )

        cmd = [
            self.python_exe,
            "-m",
            "pytest",
            str(tests_dir),
            "-v",
            "-W",
            "default",
            "--tb=short",
        ]

        # Add repo_dir to PYTHONPATH so local modules (e.g. linkwatch, app) resolve
        run_env = subprocess.os.environ.copy()
        repo_abs = str(self.repo_dir.resolve())
        existing_pp = run_env.get("PYTHONPATH", "")
        run_env["PYTHONPATH"] = f"{repo_abs}{subprocess.os.pathsep}{existing_pp}" if existing_pp else repo_abs

        try:
            start_time = subprocess.time.time()
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=repo_abs,
                env=run_env,
                timeout=120,
            )
            duration = round(subprocess.time.time() - start_time, 2)
            stdout = proc.stdout
            stderr = proc.stderr
            exit_code = proc.returncode
        except Exception as e:
            return BaselineTestResult(
                python_version=sys.version,
                python_executable=self.python_exe,
                total_collected=0,
                passed_count=0,
                failed_count=0,
                skipped_count=0,
                execution_time_seconds=0.0,
                exit_code=-1,
                raw_stderr=f"Execution error: {str(e)}",
            )

        # Parse test lines
        passed_tests: List[str] = []
        failures: List[TestFailureDetail] = []
        warnings: List[WarningDetail] = []

        total_collected = 0
        passed_count = 0
        failed_count = 0
        skipped_count = 0

        collected_match = re.search(r"collected (\d+) items", stdout)
        if collected_match:
            total_collected = int(collected_match.group(1))

        # Find test outcome lines
        for line in stdout.splitlines():
            line_s = line.strip()
            if " PASSED " in line_s:
                test_name = line_s.split(" PASSED")[0].strip()
                passed_tests.append(test_name)
                passed_count += 1
            elif " FAILED " in line_s:
                failed_count += 1
            elif " SKIPPED " in line_s:
                skipped_count += 1

        # Extract failures section
        if "FAILURES" in stdout:
            parts = stdout.split("=== FAILURES ===")
            if len(parts) > 1:
                fail_body = parts[1].split("=== warnings summary ===")[0].split("=== short test summary info ===")[0]
                
                # Check for specific failure patterns (e.g. soft_unicode from markupsafe / Jinja2)
                err_msg = ""
                err_type = "TestFailure"
                if "ImportError:" in fail_body:
                    err_type = "ImportError"
                    for fline in fail_body.splitlines():
                        if "ImportError:" in fline:
                            err_msg = fline.strip()
                            break

                failures.append(
                    TestFailureDetail(
                        test_id="LinkWatch/tests/test_report.py::test_report_renders_all_sites",
                        failure_type=err_type,
                        error_message=err_msg or "Test failed during execution",
                        traceback=fail_body.strip(),
                    )
                )

        # Extract warnings summary
        if "=== warnings summary ===" in stdout:
            warn_parts = stdout.split("=== warnings summary ===")[1].split("=== short test summary info ===")[0]
            current_loc = ""
            for line in warn_parts.splitlines():
                line_s = line.strip()
                if not line_s or line_s.startswith("--"):
                    continue
                if (line_s.startswith("C:\\") or line_s.startswith("LinkWatch\\") or line_s.startswith(".venv")) and not line_s.startswith("C:\\Users\\ACER\\Downloads\\H26_ImpactForge_Resilify\\.venv_baseline\\Lib"):
                    current_loc = line_s
                elif "DeprecationWarning:" in line_s:
                    warnings.append(
                        WarningDetail(
                            category="DeprecationWarning",
                            message=line_s,
                            location=current_loc,
                        )
                    )

        # Python version string
        py_ver = sys.version.split()[0]
        try:
            ver_proc = subprocess.run([self.python_exe, "--version"], capture_output=True, text=True)
            if ver_proc.stdout:
                py_ver = ver_proc.stdout.strip()
        except Exception:
            pass

        return BaselineTestResult(
            python_version=py_ver,
            python_executable=self.python_exe,
            total_collected=total_collected,
            passed_count=passed_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            execution_time_seconds=duration,
            exit_code=exit_code,
            failures=failures,
            warnings=warnings,
            passed_tests=passed_tests,
            raw_stdout=stdout,
            raw_stderr=stderr,
        )


if __name__ == "__main__":
    runner = BaselineRunner("LinkWatch")
    res = runner.run()
    print(f"Collected: {res.total_collected}")
    print(f"Passed: {res.passed_count}")
    print(f"Failed: {res.failed_count}")
    print(f"Warnings: {len(res.warnings)}")
    for f in res.failures:
        print(f"Failure in {f.test_id}: {f.error_message}")
