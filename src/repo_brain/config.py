from __future__ import annotations

import fnmatch
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_EXCLUDES = [
    ".git", ".repo-brain", "node_modules", "vendor", "dist", "build", "coverage",
    ".next", ".nuxt", ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache", "__pycache__",
    ".venv", "venv", "env", "target", "out", "tmp", "temp", "logs", "*.egg-info", "clean-test-*",
]
SECRET_PATTERNS = [".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa", "id_ed25519", "credentials*", "secrets*"]


@dataclass
class Config:
    include: list[str] = field(default_factory=lambda: ["**/*"])
    exclude: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDES))
    max_file_size: int = 2_000_000
    allowed_extensions: list[str] = field(default_factory=list)
    ignored_extensions: list[str] = field(default_factory=lambda: [".log", ".map", ".min.js"])
    secret_patterns: list[str] = field(default_factory=lambda: list(SECRET_PATTERNS))
    max_context: int = 12
    token_budget: int = 3000
    claim_lease_seconds: int = 900

    @classmethod
    def load(cls, root: Path) -> Config:
        path = root / ".repo-brain" / "config.toml"
        if not path.exists():
            return cls()
        try:
            with path.open("rb") as handle:
                raw = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError):
            return cls()
        scanner = raw.get("scanner", {})
        bootstrap = raw.get("bootstrap", {})
        ranking = raw.get("ranking", {})
        return cls(
            include=list(scanner.get("include", cls().include)),
            exclude=list(scanner.get("exclude", cls().exclude)),
            max_file_size=int(scanner.get("max_file_size", cls().max_file_size)),
            allowed_extensions=list(scanner.get("allowed_extensions", [])),
            ignored_extensions=list(scanner.get("ignored_extensions", cls().ignored_extensions)),
            secret_patterns=list(scanner.get("secret_patterns", cls().secret_patterns)),
            max_context=int(ranking.get("max_context", 12)),
            token_budget=int(ranking.get("token_budget", 3000)),
            claim_lease_seconds=int(bootstrap.get("claim_lease_seconds", 900)),
        )

    def write(self, root: Path) -> Path:
        directory = root / ".repo-brain"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "config.toml"
        if path.exists():
            return path
        content = (
            "# Repo Brain configuration (TOML)\n"
            "[scanner]\n"
            f"include = {self.include!r}\n"
            f"exclude = {self.exclude!r}\n"
            f"max_file_size = {self.max_file_size}\n"
            f"allowed_extensions = {self.allowed_extensions!r}\n"
            f"ignored_extensions = {self.ignored_extensions!r}\n"
            f"secret_patterns = {self.secret_patterns!r}\n\n"
            f"[ranking]\nmax_context = {self.max_context}\ntoken_budget = {self.token_budget}\n\n"
            f"[bootstrap]\nclaim_lease_seconds = {self.claim_lease_seconds}\n"
        )
        path.write_text(content, encoding="utf-8")
        return path

    def is_ignored(self, relative: str, is_dir: bool = False) -> bool:
        normalized = relative.replace("\\", "/")
        parts = normalized.split("/")
        if any(part in self.exclude for part in parts):
            return True
        if any(fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(parts[-1], pattern) for pattern in self.exclude):
            return True
        basename = parts[-1]
        return any(fnmatch.fnmatch(basename, pattern) for pattern in self.secret_patterns)
