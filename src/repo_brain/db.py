from __future__ import annotations

import contextlib
import json
import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .errors import MigrationError

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS repositories (
  id INTEGER PRIMARY KEY,
  uuid TEXT NOT NULL UNIQUE,
  root_path TEXT NOT NULL UNIQUE,
  git_common_dir TEXT,
  git_remote TEXT,
  default_branch TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_scan_at TEXT,
  brain_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY,
  repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  relative_path TEXT NOT NULL,
  normalized_path TEXT NOT NULL,
  basename TEXT NOT NULL,
  extension TEXT NOT NULL,
  language TEXT NOT NULL,
  category TEXT NOT NULL,
  size INTEGER NOT NULL DEFAULT 0,
  line_count INTEGER NOT NULL DEFAULT 0,
  sha256 TEXT,
  git_blob_hash TEXT,
  mtime REAL,
  status TEXT NOT NULL DEFAULT 'active',
  analysis_state TEXT NOT NULL DEFAULT 'pending',
  first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_analyzed_at TEXT,
  last_changed_at TEXT,
  UNIQUE(repository_id, relative_path)
);
CREATE INDEX IF NOT EXISTS idx_files_state ON files(repository_id, analysis_state);
CREATE INDEX IF NOT EXISTS idx_files_sha ON files(repository_id, sha256);
CREATE TABLE IF NOT EXISTS file_analyses (
  id INTEGER PRIMARY KEY,
  repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  source_sha256 TEXT NOT NULL,
  summary TEXT NOT NULL,
  responsibilities TEXT NOT NULL DEFAULT '[]',
  public_api TEXT NOT NULL DEFAULT '[]',
  inputs TEXT NOT NULL DEFAULT '[]',
  outputs TEXT NOT NULL DEFAULT '[]',
  side_effects TEXT NOT NULL DEFAULT '[]',
  data_flow TEXT NOT NULL DEFAULT '[]',
  security_notes TEXT NOT NULL DEFAULT '[]',
  test_notes TEXT NOT NULL DEFAULT '[]',
  risks TEXT NOT NULL DEFAULT '[]',
  architectural_notes TEXT NOT NULL DEFAULT '[]',
  confidence REAL NOT NULL DEFAULT 0.5,
  analyzer TEXT NOT NULL DEFAULT 'agent',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_analysis_file ON file_analyses(file_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS analysis_history (
  id INTEGER PRIMARY KEY,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  source_sha256 TEXT NOT NULL,
  summary TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS symbols (
  id INTEGER PRIMARY KEY,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  qualified_name TEXT NOT NULL,
  symbol_type TEXT NOT NULL,
  start_line INTEGER,
  end_line INTEGER,
  signature TEXT,
  summary TEXT,
  source_sha256 TEXT,
  visibility TEXT DEFAULT 'unknown'
);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE TABLE IF NOT EXISTS dependencies (
  id INTEGER PRIMARY KEY,
  source_file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  target_file_id INTEGER REFERENCES files(id) ON DELETE SET NULL,
  source_symbol_id INTEGER REFERENCES symbols(id) ON DELETE SET NULL,
  target_symbol_id INTEGER REFERENCES symbols(id) ON DELETE SET NULL,
  dependency_type TEXT NOT NULL,
  label TEXT,
  confidence REAL NOT NULL DEFAULT 0.5,
  source_sha256 TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_file_id, target_file_id, dependency_type, label)
);
CREATE INDEX IF NOT EXISTS idx_deps_target ON dependencies(target_file_id);
CREATE TABLE IF NOT EXISTS modules (
  id INTEGER PRIMARY KEY,
  repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  purpose TEXT,
  entrypoints TEXT NOT NULL DEFAULT '[]',
  risks TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(repository_id, name)
);
CREATE TABLE IF NOT EXISTS module_files (
  module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  PRIMARY KEY(module_id, file_id)
);
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY,
  external_session_id TEXT,
  repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  agent TEXT NOT NULL DEFAULT 'unknown',
  agent_version TEXT,
  worktree TEXT,
  branch TEXT,
  task TEXT,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ended_at TEXT,
  status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS reads (
  id INTEGER PRIMARY KEY,
  session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  source_sha256 TEXT,
  agent TEXT NOT NULL DEFAULT 'unknown',
  purpose TEXT,
  read_method TEXT NOT NULL DEFAULT 'cli',
  start_line INTEGER,
  end_line INTEGER,
  read_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS changes (
  id INTEGER PRIMARY KEY,
  session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  old_sha256 TEXT,
  new_sha256 TEXT,
  change_type TEXT NOT NULL,
  agent TEXT NOT NULL DEFAULT 'unknown',
  reason TEXT,
  git_commit TEXT,
  detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY,
  repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT,
  alternatives TEXT,
  consequences TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  superseded_by INTEGER REFERENCES decisions(id)
);
CREATE TABLE IF NOT EXISTS decision_files (
  decision_id INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  PRIMARY KEY(decision_id, file_id)
);
CREATE TABLE IF NOT EXISTS plans (
  id INTEGER PRIMARY KEY,
  repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  task TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  risks TEXT NOT NULL DEFAULT '[]',
  assumptions TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT
);
CREATE TABLE IF NOT EXISTS plan_steps (
  id INTEGER PRIMARY KEY,
  plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL,
  title TEXT NOT NULL,
  details TEXT,
  target_files TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'pending',
  notes TEXT,
  UNIQUE(plan_id, ordinal)
);
CREATE TABLE IF NOT EXISTS observations (
  id INTEGER PRIMARY KEY,
  file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  statement TEXT NOT NULL,
  source_sha256 TEXT,
  evidence_start_line INTEGER,
  evidence_end_line INTEGER,
  confidence REAL NOT NULL DEFAULT 0.5,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  superseded_at TEXT
);
CREATE TABLE IF NOT EXISTS tags (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS file_tags (
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY(file_id, tag_id)
);
CREATE TABLE IF NOT EXISTS bootstrap_queue (
  file_id INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
  priority INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending',
  claimed_by TEXT,
  claimed_at TEXT,
  claim_expires_at TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT
);
"""


class Database:
    """Small SQLite wrapper configured for safe concurrent local agents."""

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

    def migrate(self) -> None:
        try:
            conn = self.connect()
            try:
                # executescript manages its own implicit transaction; keep it
                # outside the short-write transaction helper.
                conn.executescript(SCHEMA)
                conn.execute(
                    "INSERT OR IGNORE INTO schema_migrations(version, name) VALUES (?, ?)",
                    (SCHEMA_VERSION, "initial"),
                )
                conn.commit()
                try:
                    conn.execute(
                        "CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(kind, ref_id UNINDEXED, text)"
                    )
                    conn.commit()
                    self.fts_available = True
                except sqlite3.OperationalError:
                    self.fts_available = False
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise MigrationError(f"could not migrate database {self.path}: {exc}") from exc

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
