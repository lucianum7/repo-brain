from __future__ import annotations

import contextlib
import hashlib
import json
import re
import sqlite3
import time
from collections.abc import Iterator
from importlib.resources import files as resource_files
from pathlib import Path
from typing import Any

from .errors import MigrationError

SCHEMA_VERSION = 5
_MIGRATION_PATTERN = re.compile(r"^(?P<version>\d{3})_(?P<name>[a-z0-9_]+)\.sql$")


class Database:
    """SQLite storage with immutable, package-managed SQL migrations."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fts_available = False

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    @contextlib.contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        for attempt in range(5):
            try:
                conn.execute("BEGIN IMMEDIATE")
                break
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt == 4:
                    conn.close()
                    raise
                time.sleep(0.05 * (2**attempt))
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def _migration_files(self) -> list[dict[str, Any]]:
        """Load and validate numbered SQL resources shipped with the package."""
        directory = resource_files("repo_brain").joinpath("migrations")
        migrations: list[dict[str, Any]] = []
        for resource in directory.iterdir():
            match = _MIGRATION_PATTERN.match(resource.name)
            if not match:
                continue
            text = resource.read_text(encoding="utf-8")
            migrations.append(
                {
                    "version": int(match.group("version")),
                    "name": match.group("name"),
                    "filename": resource.name,
                    "source_path": f"repo_brain/migrations/{resource.name}",
                    "sql": text,
                    "checksum": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                }
            )
        migrations.sort(key=lambda item: item["version"])
        versions = [item["version"] for item in migrations]
        expected = list(range(1, len(versions) + 1))
        if not migrations or versions != expected:
            raise MigrationError(
                "migration files must start at 001 and contain one contiguous numbered file per version"
            )
        return migrations

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None

    @staticmethod
    def _current_version(conn: sqlite3.Connection) -> int:
        if not Database._table_exists(conn, "schema_migrations"):
            return 0
        return int(conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0])

    @staticmethod
    def _audit_rows(conn: sqlite3.Connection) -> dict[int, sqlite3.Row]:
        if not Database._table_exists(conn, "migration_audit"):
            return {}
        return {
            int(row["version"]): row
            for row in conn.execute("SELECT * FROM migration_audit").fetchall()
        }

    def _verify_applied(
        self,
        conn: sqlite3.Connection,
        migrations: list[dict[str, Any]],
        current: int,
        *,
        backfill: bool,
    ) -> list[dict[str, Any]]:
        """Verify applied source files; optionally trust and record legacy rows once."""
        by_version = {item["version"]: item for item in migrations}
        audit = self._audit_rows(conn)
        drift: list[dict[str, Any]] = []
        for version in range(1, current + 1):
            migration = by_version.get(version)
            if migration is None:
                drift.append({"version": version, "reason": "missing source file"})
                continue
            recorded = audit.get(version)
            if recorded is None:
                if backfill and self._table_exists(conn, "migration_audit"):
                    conn.execute(
                        "INSERT INTO migration_audit(version,name,checksum,source_path) VALUES (?,?,?,?)",
                        (version, migration["name"], migration["checksum"], migration["source_path"]),
                    )
                continue
            if recorded["checksum"] != migration["checksum"]:
                drift.append(
                    {
                        "version": version,
                        "name": migration["name"],
                        "expected": recorded["checksum"],
                        "actual": migration["checksum"],
                        "source_path": migration["source_path"],
                    }
                )
        return drift

    def migrate(self) -> None:
        migrations = self._migration_files()
        latest = migrations[-1]["version"]
        conn: sqlite3.Connection | None = None
        try:
            conn = self.connect()
            current = self._current_version(conn)
            if current > latest:
                raise MigrationError(
                    f"database schema version {current} is newer than this package ({latest})"
                )
            preflight_drift = self._verify_applied(conn, migrations, current, backfill=False)
            if preflight_drift:
                raise MigrationError(
                    "applied migration source differs from its recorded checksum: "
                    + ", ".join(str(item["version"]) for item in preflight_drift)
                )
            for migration in migrations:
                version = migration["version"]
                if version <= current:
                    continue
                if version != current + 1:
                    raise MigrationError(f"cannot apply migration {version} after {current}")
                conn.executescript(migration["sql"])
                conn.execute(
                    "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
                    (version, migration["name"]),
                )
                conn.commit()
                current = version
            if not self._table_exists(conn, "migration_audit"):
                raise MigrationError("migration 005 did not create migration_audit")
            drift = self._verify_applied(conn, migrations, current, backfill=True)
            conn.commit()
            if drift:
                raise MigrationError(
                    "migration checksum drift detected: "
                    + ", ".join(str(item["version"]) for item in drift)
                )
            try:
                conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(kind, ref_id UNINDEXED, text)"
                )
                conn.commit()
                self.fts_available = True
            except sqlite3.OperationalError:
                self.fts_available = False
        except MigrationError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise MigrationError(f"could not migrate database {self.path}: {exc}") from exc
        finally:
            if conn is not None:
                conn.close()

    def migration_status(self) -> dict[str, Any]:
        """Return schema version, pending migrations and recorded source drift."""
        migrations = self._migration_files()
        conn = self.connect()
        try:
            current = self._current_version(conn)
            has_schema = self._table_exists(conn, "schema_migrations")
            has_audit = self._table_exists(conn, "migration_audit")
            if has_schema and has_audit:
                applied_query = "SELECT s.version,s.name,s.applied_at,a.checksum,a.source_path,a.verified_at FROM schema_migrations s LEFT JOIN migration_audit a ON a.version=s.version ORDER BY s.version"
            elif has_schema:
                applied_query = "SELECT version,name,applied_at,NULL AS checksum,NULL AS source_path,NULL AS verified_at FROM schema_migrations ORDER BY version"
            else:
                applied_query = "SELECT NULL AS version,NULL AS name,NULL AS applied_at,NULL AS checksum,NULL AS source_path,NULL AS verified_at WHERE 0"
            applied_rows = {
                int(row["version"]): dict(row)
                for row in conn.execute(applied_query).fetchall()
            }
            drift = self._verify_applied(conn, migrations, current, backfill=False)
            source_rows = [
                {
                    "version": item["version"],
                    "name": item["name"],
                    "filename": item["filename"],
                    "source_path": item["source_path"],
                    "checksum": item["checksum"],
                    "applied": item["version"] <= current,
                }
                for item in migrations
            ]
            return {
                "current": current,
                "latest": migrations[-1]["version"],
                "up_to_date": current == migrations[-1]["version"] and not drift,
                "pending": [item["filename"] for item in migrations if item["version"] > current],
                "applied": list(applied_rows.values()),
                "sources": source_rows,
                "drift": drift,
            }
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        with self.transaction() as conn:
            return conn.execute(sql, params)

    def vacuum(self) -> None:
        conn = self.connect()
        try:
            conn.execute("VACUUM")
        finally:
            conn.close()

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        conn = self.connect()
        try:
            return conn.execute(sql, params).fetchone()
        finally:
            conn.close()

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        conn = self.connect()
        try:
            return list(conn.execute(sql, params).fetchall())
        finally:
            conn.close()


def json_text(value: Any) -> str:
    return json.dumps(value if value is not None else [], ensure_ascii=False, separators=(",", ":"))
