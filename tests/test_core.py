from __future__ import annotations

import json

import pytest

from repo_brain import Brain
from repo_brain.errors import InvalidPath


def make_project(tmp_path):
    (tmp_path / "src" / "auth").mkdir(parents=True)
    (tmp_path / "src" / "mail").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "auth" / "token.py").write_text("EXPIRATION = 3600\ndef create_token(user):\n    return str(user)\n", encoding="utf-8")
    (tmp_path / "src" / "auth" / "password_reset.py").write_text("from .token import create_token\ndef reset(email):\n    return create_token(email)\n", encoding="utf-8")
    (tmp_path / "src" / "mail" / "password_email.py").write_text("def send_reset(email):\n    return email\n", encoding="utf-8")
    (tmp_path / "tests" / "test_password_reset.py").write_text("from src.auth.password_reset import reset\ndef test_reset():\n    assert reset('a')\n", encoding="utf-8")
    return Brain(tmp_path)


def test_scan_context_read_and_stale(tmp_path):
    brain = make_project(tmp_path)
    brain.init()
    results = brain.context("change password reset token expiration")['results']
    paths = [item['path'] for item in results]
    assert "src/auth/token.py" in paths
    brain.upsert_analysis("src/auth/token.py", {"summary": "Creates expiring reset tokens", "tags": ["auth", "security"], "confidence": 0.9})
    assert brain.read_file("src/auth/token.py")["sha256"]
    (tmp_path / "src" / "auth" / "token.py").write_text("EXPIRATION = 7200\n", encoding="utf-8")
    brain.scan()
    stale = [row["relative_path"] for row in brain.db.fetchall("SELECT relative_path FROM files WHERE analysis_state='stale'")]
    assert "src/auth/token.py" in stale
    with pytest.raises(InvalidPath):
        brain.read_file("../../etc/passwd")


def test_bootstrap_claims_are_unique(tmp_path):
    brain = make_project(tmp_path)
    brain.init()
    first = brain.claim_bootstrap(2, "a")
    second = brain.claim_bootstrap(2, "b")
    assert {item['file_id'] for item in first}.isdisjoint({item['file_id'] for item in second})


def test_export_import_decision(tmp_path):
    brain = make_project(tmp_path)
    brain.init()
    brain.add_decision("Tokens expire", "Use bounded reset token expiry", "Limit replay")
    output = brain.export_snapshot()
    assert output.exists()
    assert any(json.loads(line)["kind"] == "decisions" for line in output.read_text(encoding="utf-8").splitlines())


def test_directory_partitions_and_compact_context(tmp_path):
    brain = make_project(tmp_path)
    brain.init()
    directories = {row["path"] for row in brain.directories()}
    assert {".", "src", "src/auth", "src/mail", "tests"}.issubset(directories)
    scoped = brain.context("password reset token", directory="src/auth", limit=5)
    assert scoped["directory"] == "src/auth"
    assert all(item["path"].startswith("src/auth/") for item in scoped["results"])
    assert all(key == "src/auth" for key in scoped["groups"])
    assert "token_budget" not in scoped
    assert scoped["estimated_tokens"] >= 1
    analysis = brain.upsert_directory_analysis("src/auth", {"summary": "Authentication and reset-token logic.", "responsibilities": ["identity and token flows"], "confidence": 0.9})
    assert analysis["directory"] == "src/auth"
    report = brain.efficiency(directory="src/auth")
    assert report["runs"] >= 1
    assert report["totals"]["estimated_tokens"] == scoped["estimated_tokens"]
    raw = brain.db.fetchone("SELECT task_hash,task_length FROM retrieval_runs WHERE repository_id=?", (brain.repository_id,))
    assert len(raw["task_hash"]) == 64
    assert raw["task_length"] == len("password reset token")


def test_database_migrations_are_source_driven_and_idempotent(tmp_path):
    brain = make_project(tmp_path)
    brain.init()
    first = brain.db.migration_status()
    assert first["current"] == first["latest"] == 5
    assert first["up_to_date"] is True
    assert [row["version"] for row in brain.db.fetchall("SELECT version FROM schema_migrations ORDER BY version")] == [1, 2, 3, 4, 5]
    columns = {row["name"] for row in brain.db.fetchall("PRAGMA table_info(retrieval_runs)")}
    assert {"compacted_tokens", "candidate_tokens", "estimated_tokens"}.issubset(columns)
    assert "token_budget" not in columns
    assert "saved_tokens" not in columns
    assert brain.db.fetchone("SELECT COUNT(*) AS count FROM migration_audit")["count"] == 5
    assert first["applied"][-1]["source_path"] == "repo_brain/migrations/005_migration_audit.sql"
    brain.db.migrate()
    assert brain.db.migration_status()["up_to_date"] is True

