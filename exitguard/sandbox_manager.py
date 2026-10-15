"""
sandbox_manager.py - Manages isolated, disposable working copies of target repositories.

Part of ExitGuard (Member 3: Migration Verification).

Key design principles:
  - Original repository is NEVER modified.
  - Creates disposable working copies pinned to exact commit SHAs (via Git worktree).
  - Explicitly verifies the checked-out commit identity.
  - Enforces strict ownership boundaries: will only delete sandboxes created and tagged by this manager.
  - Safe subprocess execution with structured argument lists and timeouts.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Generator, Optional, Set
import uuid

logger = logging.getLogger("exitguard.sandbox")

METADATA_FILENAME = ".exitguard_sandbox_meta.json"
OWNER_TAG = "ExitGuard-SandboxManager-v0.2.0"
DEFAULT_TIMEOUT_SECONDS = 30


class SandboxError(Exception):
    """Base exception for all sandbox-related failures."""
    pass


class SandboxCreationError(SandboxError):
    """Raised when sandbox creation fails."""
    pass


class SandboxVerificationError(SandboxError):
    """Raised when a sandbox fails commit or integrity verification."""
    pass


class SandboxCleanupError(SandboxError):
    """Raised when sandbox cleanup fails or violates ownership."""
    pass


@dataclass
class SandboxInfo:
    """Descriptor for an active sandbox instance."""
    sandbox_root: Path
    target_dir: Path
    commit_sha: str
    source_repo_root: Path
    created_at: str
    owner_id: str
    is_worktree: bool = True

    def to_dict(self) -> dict:
        return {
            "sandbox_root": str(self.sandbox_root),
            "target_dir": str(self.target_dir),
            "commit_sha": self.commit_sha,
            "source_repo_root": str(self.source_repo_root),
            "created_at": self.created_at,
            "owner_id": self.owner_id,
            "is_worktree": self.is_worktree,
        }


class SandboxManager:
    """
    Creates and cleans up disposable, isolated Git worktree copies of target repositories.
    Guarantees the original working tree remains completely untouched.
    """

    def __init__(self, base_temp_dir: Optional[Path | str] = None) -> None:
        self.base_temp_dir = Path(base_temp_dir) if base_temp_dir else Path(tempfile.gettempdir())
        self._owned_sandboxes: Set[Path] = set()

    def _run_git(
        self,
        args: list[str],
        cwd: Path,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> subprocess.CompletedProcess[str]:
        """Execute a structured Git command with strict timeout and no shell."""
        cmd = ["git", "-C", str(cwd)] + args
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise SandboxError(f"Git command timed out after {timeout}s: {' '.join(cmd)}") from exc
        except FileNotFoundError as exc:
            raise SandboxError("Git executable not found in PATH.") from exc

    def _find_git_root(self, path: Path) -> Path:
        """Find the enclosing Git repository root for a given directory."""
        if not path.exists():
            raise SandboxCreationError(f"Specified path does not exist: {path}")

        proc = self._run_git(["rev-parse", "--show-toplevel"], cwd=path if path.is_dir() else path.parent)
        if proc.returncode != 0:
            raise SandboxCreationError(f"Path is not part of a Git repository: {path}. Git stderr: {proc.stderr.strip()}")
        return Path(proc.stdout.strip())

    def _resolve_commit(self, git_root: Path, commit_sha: Optional[str]) -> str:
        """Resolve commit reference to an exact 40-character SHA."""
        target_ref = commit_sha if commit_sha else "HEAD"
        proc = self._run_git(["rev-parse", "--verify", f"{target_ref}^{{commit}}"], cwd=git_root)
        if proc.returncode != 0:
            raise SandboxCreationError(
                f"Commit '{target_ref}' could not be verified in repository {git_root}. Git stderr: {proc.stderr.strip()}"
            )
        resolved = proc.stdout.strip()
        if len(resolved) != 40:
            raise SandboxCreationError(f"Invalid resolved commit SHA '{resolved}'.")
        return resolved

    def create_sandbox(
        self,
        repo_path: Path | str,
        commit_sha: Optional[str] = None,
    ) -> SandboxInfo:
        """
        Create a disposable, isolated working copy at the specified commit.
        Leaves original repo completely untouched.
        """
        path = Path(repo_path).resolve()
        git_root = self._find_git_root(path)
        resolved_sha = self._resolve_commit(git_root, commit_sha)

        # Calculate relative offset if repo_path is a subdirectory inside git_root
        relative_subpath = Path()
        try:
            relative_subpath = path.relative_to(git_root)
        except ValueError:
            relative_subpath = Path()

        owner_id = f"{OWNER_TAG}-{uuid.uuid4().hex[:12]}"
        sb_dir_name = f"exitguard_sb_{uuid.uuid4().hex[:8]}"
        sandbox_root = self.base_temp_dir / sb_dir_name

        # Ensure base directory exists
        self.base_temp_dir.mkdir(parents=True, exist_ok=True)

        # Create detached git worktree
        proc = self._run_git(
            ["worktree", "add", "--detach", str(sandbox_root), resolved_sha],
            cwd=git_root,
        )
        if proc.returncode != 0:
            raise SandboxCreationError(
                f"Failed to create git worktree at {sandbox_root}: {proc.stderr.strip()}"
            )

        target_dir = sandbox_root / relative_subpath
        if not target_dir.exists():
            has_files_at_root = any(
                p.is_file() for p in sandbox_root.iterdir() if p.name != METADATA_FILENAME
            )
            if has_files_at_root:
                target_dir = sandbox_root
            else:
                # Rollback worktree on failure
                self._run_git(["worktree", "remove", "--force", str(sandbox_root)], cwd=git_root)
                raise SandboxCreationError(
                    f"Target subdirectory '{relative_subpath}' does not exist in checked-out commit {resolved_sha}"
                )

        # Write provenance marker
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        meta_payload = {
            "owner_tag": OWNER_TAG,
            "owner_id": owner_id,
            "created_at": created_at,
            "commit_sha": resolved_sha,
            "source_repo_root": str(git_root),
            "target_relative_path": str(relative_subpath),
        }
        meta_file = sandbox_root / METADATA_FILENAME
        meta_file.write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")

        info = SandboxInfo(
            sandbox_root=sandbox_root,
            target_dir=target_dir,
            commit_sha=resolved_sha,
            source_repo_root=git_root,
            created_at=created_at,
            owner_id=owner_id,
            is_worktree=True,
        )

        # Verify sandbox integrity immediately
        self.verify_sandbox(info)

        # Record ownership
        self._owned_sandboxes.add(sandbox_root.resolve())
        return info

    def verify_sandbox(self, sandbox: SandboxInfo) -> bool:
        """
        Verify that the sandbox exists, holds the ownership marker,
        and is checked out to the exact expected commit SHA.
        """
        if not sandbox.sandbox_root.exists():
            raise SandboxVerificationError(f"Sandbox root does not exist: {sandbox.sandbox_root}")

        meta_file = sandbox.sandbox_root / METADATA_FILENAME
        if not meta_file.exists():
            raise SandboxVerificationError(f"Sandbox missing ownership metadata file: {meta_file}")

        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SandboxVerificationError(f"Could not parse sandbox metadata: {exc}") from exc

        if meta.get("owner_id") != sandbox.owner_id:
            raise SandboxVerificationError(
                f"Sandbox owner_id mismatch. Expected {sandbox.owner_id}, found {meta.get('owner_id')}"
            )

        # Verify exact commit in sandbox git
        proc = self._run_git(["rev-parse", "HEAD"], cwd=sandbox.sandbox_root)
        if proc.returncode != 0:
            raise SandboxVerificationError(f"Failed to query commit in sandbox: {proc.stderr.strip()}")

        actual_sha = proc.stdout.strip()
        if actual_sha != sandbox.commit_sha:
            raise SandboxVerificationError(
                f"Sandbox commit mismatch. Expected {sandbox.commit_sha}, found {actual_sha}"
            )

        return True

    def cleanup_sandbox(self, sandbox: SandboxInfo) -> None:
        """
        Clean up only sandboxes created and owned by this SandboxManager instance.
        Refuses to clean up unverified or arbitrary directories.
        """
        sb_resolved = sandbox.sandbox_root.resolve()

        # Strict ownership verification
        meta_file = sandbox.sandbox_root / METADATA_FILENAME
        is_tracked_in_memory = sb_resolved in self._owned_sandboxes
        has_matching_marker = False

        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                if meta.get("owner_id") == sandbox.owner_id and meta.get("owner_tag") == OWNER_TAG:
                    has_matching_marker = True
            except Exception:
                has_matching_marker = False

        if not (is_tracked_in_memory or has_matching_marker):
            raise SandboxCleanupError(
                f"Refusing to delete directory not owned by SandboxManager: {sandbox.sandbox_root}"
            )

        # Remove git worktree via source repo if it is a worktree
        if sandbox.is_worktree and sandbox.source_repo_root.exists():
            self._run_git(
                ["worktree", "remove", "--force", str(sandbox.sandbox_root)],
                cwd=sandbox.source_repo_root,
            )

        # If directory remains on disk, clean it up safely
        if sandbox.sandbox_root.exists():
            shutil.rmtree(sandbox.sandbox_root, ignore_errors=True)

        self._owned_sandboxes.discard(sb_resolved)

    @contextmanager
    def isolated_sandbox(
        self,
        repo_path: Path | str,
        commit_sha: Optional[str] = None,
        preserve_on_error: bool = False,
    ) -> Generator[SandboxInfo, None, None]:
        """
        Context manager that automatically provisions and cleans up an isolated sandbox.
        """
        sandbox = self.create_sandbox(repo_path, commit_sha=commit_sha)
        failed = False
        try:
            yield sandbox
        except Exception:
            failed = True
            if preserve_on_error:
                logger.warning(
                    f"Preserving failed sandbox for inspection: {sandbox.sandbox_root}"
                )
                raise
            raise
        finally:
            if not (failed and preserve_on_error):
                self.cleanup_sandbox(sandbox)
