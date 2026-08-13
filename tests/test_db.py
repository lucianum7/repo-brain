from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from repo_brain.db import Database
from repo_brain.errors import MigrationError


def test_legacy_v3_database_upgrades_without_manual_budget_columns(tmp_path):
    database_path = tmp_path / "legacy.db"
    migrations = Path(__file__).parents[1] / "src" / "repo_brain" / "migrations"
    conn = sqlite3.connect(database_path)
    conn.executescript((migrations / "001_initial.sql").read_text(encoding="utf-8"))
    conn.execute("INSERT INTO schema_migrations(version,name) VALUES (1,'initial')")
    directory_sql = (migrations / "002_directory_memory.sql").read_text(encoding="utf-8")
    conn.executescript(directory_sql)
    conn.execute("INSERT INTO schema_migrations(version,name) VALUES (2,'directory_memory')")
    conn.executescript((migrations / "003_retrieval_efficiency.sql").read_text(encoding="utf-8"))
    conn.execute("INSERT INTO schema_migrations(version,name) VALUES (3,'retrieval_efficiency')")
    conn.commit()
    conn.close()

    database = Database(database_path)
    database.migrate()
    columns = {row["name"] for row in database.fetchall("PRAGMA table_info(retrieval_runs)")}
    assert "token_budget" not in columns
    assert "saved_tokens" not in columns
    assert "compacted_tokens" in columns
    assert database.migration_status()["up_to_date"] is True


def test_applied_migration_drift_is_reported_and_blocks_upgrade(tmp_path, monkeypatch):
    database = Database(tmp_path / "drift.db")
    database.migrate()
    original_loader = database._migration_files

    def tampered_loader():
        files = original_loader()
        files[0] = {**files[0], "checksum": "0" * 64}
        return files

    monkeypatch.setattr(database, "_migration_files", tampered_loader)
    status = database.migration_status()
    assert status["up_to_date"] is False
    assert status["drift"][0]["version"] == 1
    with pytest.raises(MigrationError):
        database.migrate()
