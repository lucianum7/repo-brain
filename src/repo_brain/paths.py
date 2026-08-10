from __future__ import annotations

import subprocess
from pathlib import Path

from .errors import InvalidPath


def find_root(start: str | Path | None = None) -> Path:
    """Find the nearest project root, preferring the Git worktree root."""
    current = Path(start or Path.cwd()).expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    # A project can be used without Git; the caller's directory is the root.
    return current


def git_common_dir(root: Path) -> Path | None:
    try:
        value = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--git-common-dir"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    path = Path(value)
    if not path.is_absolute():
        path = (root / path).resolve()
    return path


def database_path(root: Path) -> Path:
    """Return the shared database path for a Git repository or local project."""
    common = git_common_dir(root)
    if common:
        return common / "repo-brain" / "brain.db"
    return root / ".repo-brain" / "brain.db"


def ensure_inside(root: Path, path: str | Path) -> Path:
    """Resolve a user path and reject traversal or symlink escapes."""
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise InvalidPath(f"path is outside repository root: {path}") from exc
    return resolved


def relative_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise InvalidPath(f"path is outside repository root: {path}") from exc

