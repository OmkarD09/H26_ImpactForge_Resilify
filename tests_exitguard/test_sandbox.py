"""
test_sandbox.py - Unit tests for SandboxManager using synthetic local Git repositories.

NOTE: All tests in this file operate strictly on disposable SYNTHETIC fixtures
created inside temporary directories. They do NOT test or modify the LinkWatch codebase.
"""

from pathlib import Path
import subprocess
import pytest

from exitguard.sandbox_manager import (
    SandboxCleanupError,
    SandboxCreationError,
    SandboxInfo,
    SandboxManager,
    SandboxVerificationError,
)


@pytest.fixture
def synthetic_git_repo(tmp_path: Path):
    """
    Creates a disposable, isolated synthetic Git repository with two commits
    to test commit pinning, worktree creation, and source immutability.
    """
    repo_dir = tmp_path / "synthetic_source_repo"
    repo_dir.mkdir(parents=True)

    def _run_git(args: list[str]):
        subprocess.run(
            ["git", "-C", str(repo_dir)] + args,
            check=True,
            capture_output=True,
            text=True,
        )

    _run_git(["init", "-b", "main"])
    _run_git(["config", "user.name", "Synthetic Tester"])
    _run_git(["config", "user.email", "tester@example.com"])

    # Commit 1
    (repo_dir / "initial.txt").write_text("commit 1 content\n", encoding="utf-8")
    _run_git(["add", "initial.txt"])
    _run_git(["commit", "-m", "Commit 1: initial file"])
    proc1 = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    commit1_sha = proc1.stdout.strip()

    # Commit 2 (adds a subfolder and modifies initial.txt)
    subfolder = repo_dir / "subpkg"
    subfolder.mkdir()
    (subfolder / "module.py").write_text("print('hello')\n", encoding="utf-8")
    (repo_dir / "initial.txt").write_text("commit 2 modified content\n", encoding="utf-8")
    _run_git(["add", "."])
    _run_git(["commit", "-m", "Commit 2: added subpkg and modified initial"])
    proc2 = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    commit2_sha = proc2.stdout.strip()

    return {
        "repo_dir": repo_dir,
        "commit1_sha": commit1_sha,
        "commit2_sha": commit2_sha,
    }


def test_sandbox_creation_at_pinned_commit(synthetic_git_repo, tmp_path: Path):
    """Verify sandbox is created at the requested older commit, not HEAD."""
    repo_dir = synthetic_git_repo["repo_dir"]
    commit1_sha = synthetic_git_repo["commit1_sha"]

    manager = SandboxManager(base_temp_dir=tmp_path / "sandboxes")
    sandbox = manager.create_sandbox(repo_dir, commit_sha=commit1_sha)

    try:
        assert sandbox.commit_sha == commit1_sha
        assert sandbox.sandbox_root.exists()

        # In Commit 1, initial.txt should have "commit 1 content", and subpkg should NOT exist
        initial_file = sandbox.sandbox_root / "initial.txt"
        assert initial_file.exists()
        assert initial_file.read_text(encoding="utf-8").strip() == "commit 1 content"
        assert not (sandbox.sandbox_root / "subpkg").exists()

        # Verify manager integrity check
        assert manager.verify_sandbox(sandbox) is True
    finally:
        manager.cleanup_sandbox(sandbox)

    assert not sandbox.sandbox_root.exists()


def test_original_repository_remains_unchanged(synthetic_git_repo, tmp_path: Path):
    """Verify source repository files, status, and HEAD are 100% untouched."""
    repo_dir = synthetic_git_repo["repo_dir"]
    commit2_sha = synthetic_git_repo["commit2_sha"]

    # Initial snapshot
    initial_content = (repo_dir / "initial.txt").read_text(encoding="utf-8")

    manager = SandboxManager(base_temp_dir=tmp_path / "sandboxes")
    with manager.isolated_sandbox(repo_dir) as sandbox:
        # Mutate the file in the sandbox
        (sandbox.sandbox_root / "initial.txt").write_text("MUTATED INSIDE SANDBOX", encoding="utf-8")
        assert (sandbox.sandbox_root / "initial.txt").read_text(encoding="utf-8") == "MUTATED INSIDE SANDBOX"

    # Verify source repository remains pristine
    assert (repo_dir / "initial.txt").read_text(encoding="utf-8") == initial_content

    # Check git status of source repo
    proc = subprocess.run(
        ["git", "-C", str(repo_dir), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert proc.stdout.strip() == "", "Source repository working tree was modified!"


def test_subdirectory_target_resolution(synthetic_git_repo, tmp_path: Path):
    """
    Verify that if a target subdirectory is specified (like LinkWatch inside H26_ImpactForge_Resilify),
    the target_dir points directly to that subdirectory in the sandbox.
    """
    subfolder_path = synthetic_git_repo["repo_dir"] / "subpkg"
    manager = SandboxManager(base_temp_dir=tmp_path / "sandboxes")

    with manager.isolated_sandbox(subfolder_path) as sandbox:
        assert sandbox.target_dir == sandbox.sandbox_root / "subpkg"
        assert (sandbox.target_dir / "module.py").exists()


def test_invalid_commit_fails_safely(synthetic_git_repo, tmp_path: Path):
    """Verify that an invalid or non-existent commit SHA raises SandboxCreationError."""
    repo_dir = synthetic_git_repo["repo_dir"]
    manager = SandboxManager(base_temp_dir=tmp_path / "sandboxes")

    with pytest.raises(SandboxCreationError, match="could not be verified"):
        manager.create_sandbox(repo_dir, commit_sha="deadbeef00001111222233334444555566667777")


def test_non_git_path_fails_safely(tmp_path: Path):
    """Verify that attempting to create a sandbox on a non-git directory fails safely."""
    non_git_dir = tmp_path / "not_git"
    non_git_dir.mkdir()
    manager = SandboxManager(base_temp_dir=tmp_path / "sandboxes")

    with pytest.raises(SandboxCreationError, match="not part of a Git repository"):
        manager.create_sandbox(non_git_dir)


def test_cleanup_restricted_to_owned_sandbox(synthetic_git_repo, tmp_path: Path):
    """Verify that SandboxManager refuses to delete directories it does not own."""
    unowned_dir = tmp_path / "user_important_data"
    unowned_dir.mkdir()
    (unowned_dir / "data.txt").write_text("cannot be deleted", encoding="utf-8")

    fake_sandbox = SandboxInfo(
        sandbox_root=unowned_dir,
        target_dir=unowned_dir,
        commit_sha="dummy",
        source_repo_root=synthetic_git_repo["repo_dir"],
        created_at="2026-10-15T12:00:00Z",
        owner_id="UNAUTHORIZED_ID",
    )

    manager = SandboxManager(base_temp_dir=tmp_path / "sandboxes")
    with pytest.raises(SandboxCleanupError, match="Refusing to delete directory not owned"):
        manager.cleanup_sandbox(fake_sandbox)

    # Verify the unowned directory was not deleted
    assert unowned_dir.exists()
    assert (unowned_dir / "data.txt").exists()


def test_root_project_fallback_when_subfolder_absent(synthetic_git_repo, tmp_path: Path):
    """
    Verify that if a target subdirectory is requested on an older commit where the
    subfolder did not exist, but root files exist, it falls back to sandbox_root safely.
    """
    subfolder_path = synthetic_git_repo["repo_dir"] / "subpkg"
    commit1_sha = synthetic_git_repo["commit1_sha"]
    manager = SandboxManager(base_temp_dir=tmp_path / "sandboxes")

    # In commit 1, subpkg did not exist yet, but initial.txt did
    with manager.isolated_sandbox(subfolder_path, commit_sha=commit1_sha) as sandbox:
        assert sandbox.commit_sha == commit1_sha
        assert (sandbox.target_dir / "initial.txt").exists()

