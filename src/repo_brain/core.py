from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import time
import uuid
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .analyzers import index_file, language_for
from .config import Config
from .db import Database, json_text
from .errors import BrainNotInitialized, InvalidAnalysis, InvalidPath
from .paths import database_path, ensure_inside, find_root, git_common_dir, relative_path

APP_VERSION = "0.4.0"


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Brain:
    """Application service shared by the CLI, UI, hooks and MCP transport."""

    def __init__(self, root: str | Path | None = None, require_initialized: bool = False):
        self.root = Path(root).expanduser().resolve() if root is not None else find_root()
        if self.root.is_file():
            self.root = self.root.parent
        self.config = Config.load(self.root)
        self.db_path = database_path(self.root)
        self.db = Database(self.db_path)
        if require_initialized and not self.db_path.exists():
            raise BrainNotInitialized(f"Repo Brain is not initialized. Run `repo-brain init` in {self.root}.")
        if self.db_path.exists():
            self.db.migrate()

    def init(self) -> dict[str, Any]:
        self.config.write(self.root)
        self.db.migrate()
        repo = self._ensure_repository()
        result = self.scan()
        result.update({"root": str(self.root), "database": str(self.db_path), "repository_id": repo})
        return result

    def _ensure_repository(self) -> int:
        remote = None
        branch = None
        try:
            remote = subprocess.check_output(["git", "-C", str(self.root), "remote", "get-url", "origin"], text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            pass
        try:
            branch = subprocess.check_output(["git", "-C", str(self.root), "branch", "--show-current"], text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            pass
        existing = self.db.fetchone("SELECT id FROM repositories WHERE root_path=?", (str(self.root),))
        if existing:
            self.db.execute("UPDATE repositories SET updated_at=CURRENT_TIMESTAMP, git_remote=?, default_branch=?, brain_version=? WHERE id=?", (remote, branch, APP_VERSION, existing["id"]))
            return int(existing["id"])
        with self.db.transaction() as conn:
            cur = conn.execute("INSERT INTO repositories(uuid,root_path,git_common_dir,git_remote,default_branch,brain_version) VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), str(self.root), str(git_common_dir(self.root) or ""), remote, branch, APP_VERSION))
            return int(cur.lastrowid)

    @property
    def repository_id(self) -> int:
        row = self.db.fetchone("SELECT id FROM repositories WHERE root_path=?", (str(self.root),))
        if not row:
            return self._ensure_repository()
        return int(row["id"])

    def _gitignore(self) -> list[str]:
        path = self.root / ".gitignore"
        if not path.exists():
            return []
        return [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip() and not line.startswith("#")]

    def _ignored(self, rel: str) -> bool:
        if self.config.is_ignored(rel):
            return True
        import fnmatch
        return any(fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(Path(rel).name, pattern) for pattern in self._gitignore())

    def scan(self) -> dict[str, Any]:
        self.db.migrate()
        repo_id = self.repository_id
        seen: set[str] = set()
        created = changed = deleted = ignored = 0
        for path in self.root.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(self.root).as_posix()
            if self._ignored(rel):
                ignored += 1
                continue
            seen.add(rel)
            stat = path.stat()
            category = "source"
            lower = path.name.lower()
            if any(re.fullmatch(pattern.replace("*", ".*"), lower) for pattern in self.config.secret_patterns):
                category = "secret"
            elif stat.st_size > self.config.max_file_size:
                category = "large"
            else:
                try:
                    sample = path.read_bytes()[:4096]
                    if b"\x00" in sample:
                        category = "binary"
                except OSError:
                    category = "error"
            digest = None if category in {"secret", "binary"} else hash_file(path)
            line_count = 0
            if category == "source":
                try:
                    line_count = path.read_text(encoding="utf-8", errors="replace").count("\n") + (1 if stat.st_size else 0)
                except OSError:
                    category = "error"
            previous = self.db.fetchone("SELECT * FROM files WHERE repository_id=? AND relative_path=?", (repo_id, rel))
            old_hash = previous["sha256"] if previous else None
            state = previous["analysis_state"] if previous else "pending"
            if previous and previous["status"] == "deleted" or not previous:
                created += 1
            elif old_hash != digest and digest is not None:
                changed += 1
                state = "stale"
            if category in {"secret", "binary", "large"}:
                state = "ignored"
            with self.db.transaction() as conn:
                conn.execute("""INSERT INTO files(repository_id,relative_path,normalized_path,basename,extension,language,category,size,line_count,sha256,mtime,status,analysis_state,last_seen_at,last_changed_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,'active',?,CURRENT_TIMESTAMP,CASE WHEN ? IS NOT NULL AND ? != ? THEN CURRENT_TIMESTAMP ELSE NULL END)
                    ON CONFLICT(repository_id,relative_path) DO UPDATE SET normalized_path=excluded.normalized_path,basename=excluded.basename,extension=excluded.extension,language=excluded.language,category=excluded.category,size=excluded.size,line_count=excluded.line_count,sha256=excluded.sha256,mtime=excluded.mtime,status='active',analysis_state=excluded.analysis_state,last_seen_at=CURRENT_TIMESTAMP,last_changed_at=CASE WHEN files.sha256 != excluded.sha256 THEN CURRENT_TIMESTAMP ELSE files.last_changed_at END""", (repo_id, rel, rel.lower(), path.name, path.suffix.lower(), language_for(path), category, stat.st_size, line_count, digest, stat.st_mtime, state, digest, old_hash, digest))
                row = conn.execute("SELECT id FROM files WHERE repository_id=? AND relative_path=?", (repo_id, rel)).fetchone()
                if not previous:
                    conn.execute("INSERT OR REPLACE INTO bootstrap_queue(file_id,priority,status) VALUES (?, ?, 'pending')", (row["id"], 10 if rel.startswith(("src/", "app/")) else 1))
                elif old_hash != digest and digest is not None:
                    conn.execute("INSERT INTO changes(session_id,file_id,old_sha256,new_sha256,change_type,agent,reason) VALUES (NULL,?,?,?,?,?,?)", (row["id"], old_hash, digest, "modify", os.getenv("REPO_BRAIN_AGENT", "unknown"), "scan"))
                    conn.execute("UPDATE bootstrap_queue SET status='pending', claimed_by=NULL, claimed_at=NULL WHERE file_id=?", (row["id"],))
                    conn.execute("UPDATE files SET analysis_state='needs_review' WHERE id IN (SELECT source_file_id FROM dependencies WHERE target_file_id=?) AND analysis_state='fresh'", (row["id"],))
        rows = self.db.fetchall("SELECT * FROM files WHERE repository_id=? AND status='active'", (repo_id,))
        with self.db.transaction() as conn:
            for row in conn.execute("SELECT id,relative_path,sha256 FROM files WHERE repository_id=? AND status='active'", (repo_id,)).fetchall():
                if row["relative_path"] not in seen:
                    deleted += 1
                    conn.execute("UPDATE files SET status='deleted',analysis_state='stale',last_changed_at=CURRENT_TIMESTAMP WHERE id=?", (row["id"],))
                    conn.execute("INSERT INTO changes(file_id,old_sha256,new_sha256,change_type,agent,reason) VALUES (?,?,?,?,?,?)", (row["id"], row["sha256"], None, "delete", os.getenv("REPO_BRAIN_AGENT", "unknown"), "scan"))
        # Rebuild static symbols/dependencies for active source files.
        for row in rows:
            if row["category"] == "source" and row["status"] == "active":
                index_file(self.db, repo_id, row, self.root)
        self._refresh_directories(repo_id)
        self._refresh_modules(repo_id)
        self.db.execute("UPDATE repositories SET last_scan_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?", (repo_id,))
        self.write_index()
        return {"created": created, "changed": changed, "deleted": deleted, "ignored": ignored, "files": len(seen), "database": str(self.db_path)}

    @staticmethod
    def _directory_chain(relative_path_value: str) -> list[str]:
        """Return root-to-parent directory paths for a relative file path."""
        parts = relative_path_value.split("/")[:-1]
        paths = ["."]
        for index in range(1, len(parts) + 1):
            paths.append("/".join(parts[:index]))
        return paths

    def _refresh_directories(self, repo_id: int) -> None:
        """Keep directory inventory and compact structural summaries current."""
        with self.db.transaction() as conn:
            files = conn.execute("SELECT id,relative_path FROM files WHERE repository_id=? AND status='active'", (repo_id,)).fetchall()
            directory_rows: dict[str, tuple[str, str | None, int]] = {}
            for file_row in files:
                for directory_path in self._directory_chain(file_row["relative_path"]):
                    if directory_path == ".":
                        directory_rows[directory_path] = (self.root.name, None, 0)
                    else:
                        parent = "/".join(directory_path.split("/")[:-1]) or "."
                        directory_rows[directory_path] = (directory_path.rsplit("/", 1)[-1], parent, directory_path.count("/") + 1)
            for path_value, (name, parent, depth) in directory_rows.items():
                conn.execute("""INSERT INTO directories(repository_id,path,name,parent_path,depth)
                    VALUES (?,?,?,?,?)
                    ON CONFLICT(repository_id,path) DO UPDATE SET name=excluded.name,parent_path=excluded.parent_path,depth=excluded.depth,updated_at=CURRENT_TIMESTAMP""", (repo_id, path_value, name, parent, depth))
            for file_row in files:
                parent_path = "/".join(file_row["relative_path"].split("/")[:-1]) or "."
                directory = conn.execute("SELECT id FROM directories WHERE repository_id=? AND path=?", (repo_id, parent_path)).fetchone()
                conn.execute("UPDATE files SET directory_id=? WHERE id=?", (directory["id"], file_row["id"]))
            directories = conn.execute("SELECT id,path FROM directories WHERE repository_id=?", (repo_id,)).fetchall()
            for directory in directories:
                scope = "1=1" if directory["path"] == "." else "relative_path LIKE ?"
                scope_params = () if directory["path"] == "." else (directory["path"] + "/%",)
                stats = conn.execute(f"""SELECT COUNT(*) AS total,
                    SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) AS active,
                    SUM(CASE WHEN analysis_state='fresh' AND status='active' THEN 1 ELSE 0 END) AS fresh,
                    SUM(CASE WHEN analysis_state='stale' AND status='active' THEN 1 ELSE 0 END) AS stale,
                    SUM(CASE WHEN analysis_state='needs_review' AND status='active' THEN 1 ELSE 0 END) AS review,
                    SUM(CASE WHEN analysis_state='pending' AND status='active' THEN 1 ELSE 0 END) AS pending
                    FROM files WHERE repository_id=? AND {scope}""", (repo_id, *scope_params)).fetchone()
                names = [row["relative_path"].rsplit("/", 1)[-1] for row in conn.execute(f"SELECT relative_path FROM files WHERE repository_id=? AND status='active' AND {scope} ORDER BY relative_path LIMIT 8", (repo_id, *scope_params)).fetchall()]
                summary = f"{stats['active'] or 0} active files; fresh={stats['fresh'] or 0}, stale={stats['stale'] or 0}, needs_review={stats['review'] or 0}, pending={stats['pending'] or 0}."
                conn.execute("""UPDATE directories SET file_count=?,active_file_count=?,fresh_count=?,stale_count=?,needs_review_count=?,pending_count=?,summary=?,responsibilities=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""", (stats["total"] or 0, stats["active"] or 0, stats["fresh"] or 0, stats["stale"] or 0, stats["review"] or 0, stats["pending"] or 0, summary, json_text([f"Contains {len(names)} indexed files" if names else "No active files"]), directory["id"]))

    def _refresh_modules(self, repo_id: int) -> None:
        """Infer stable, shallow modules from top-level path segments."""
        with self.db.transaction() as conn:
            rows = conn.execute("SELECT id,relative_path FROM files WHERE repository_id=? AND status='active'", (repo_id,)).fetchall()
            buckets: dict[str, list[int]] = {}
            for row in rows:
                parts = row["relative_path"].split("/")
                name = parts[0] if len(parts) > 1 else "root"
                buckets.setdefault(name, []).append(row["id"])
            for name, file_ids in buckets.items():
                conn.execute("INSERT INTO modules(repository_id,name,description,purpose) VALUES (?,?,?,?) ON CONFLICT(repository_id,name) DO UPDATE SET updated_at=CURRENT_TIMESTAMP", (repo_id, name, f"Top-level module {name}", "Repository component inferred from paths"))
                module_id = conn.execute("SELECT id FROM modules WHERE repository_id=? AND name=?", (repo_id, name)).fetchone()["id"]
                conn.execute("DELETE FROM module_files WHERE module_id=?", (module_id,))
                conn.executemany("INSERT OR IGNORE INTO module_files(module_id,file_id) VALUES (?,?)", [(module_id, fid) for fid in file_ids])

    def _file(self, value: str | Path) -> Any:
        path = ensure_inside(self.root, value)
        rel = relative_path(self.root, path)
        row = self.db.fetchone("SELECT * FROM files WHERE repository_id=? AND relative_path=?", (self.repository_id, rel))
        if not row:
            raise InvalidPath(f"file is not indexed: {rel}; run `repo-brain scan`")
        return row

    def _normalize_directory(self, value: str | Path | None) -> str:
        if value in (None, "", "."):
            return "."
        path = ensure_inside(self.root, value)
        if path == self.root:
            return "."
        return relative_path(self.root, path).rstrip("/") or "."

    def directory_details(self, value: str | Path = ".", include_files: bool = True) -> dict[str, Any]:
        directory_path = self._normalize_directory(value)
        row = self.db.fetchone("SELECT * FROM directories WHERE repository_id=? AND path=?", (self.repository_id, directory_path))
        if not row:
            raise InvalidPath(f"directory is not indexed: {directory_path}; run `repo-brain scan`")
        latest = self.db.fetchone("SELECT * FROM directory_analyses WHERE directory_id=? ORDER BY updated_at DESC LIMIT 1", (row["id"],))
        result = dict(row)
        for key in ("responsibilities", "entrypoints", "risks", "architecture_notes"):
            result[key] = json.loads(result[key] or "[]")
        result["analysis"] = dict(latest) if latest else None
        if result["analysis"]:
            for key in ("responsibilities", "entrypoints", "risks", "architecture_notes"):
                result["analysis"][key] = json.loads(result["analysis"][key] or "[]")
        if include_files:
            if directory_path == ".":
                files = self.db.fetchall("SELECT relative_path,basename,language,category,analysis_state,sha256 FROM files WHERE repository_id=? AND status='active' ORDER BY relative_path", (self.repository_id,))
            else:
                files = self.db.fetchall("SELECT relative_path,basename,language,category,analysis_state,sha256 FROM files WHERE repository_id=? AND status='active' AND relative_path LIKE ? ORDER BY relative_path", (self.repository_id, directory_path + "/%"))
            result["files"] = [dict(file_row) for file_row in files]
        return result

    def directories(self, parent: str | None = None) -> list[dict[str, Any]]:
        if parent is None:
            rows = self.db.fetchall("SELECT * FROM directories WHERE repository_id=? AND active_file_count>0 ORDER BY depth,path", (self.repository_id,))
        else:
            rows = self.db.fetchall("SELECT * FROM directories WHERE repository_id=? AND parent_path=? AND active_file_count>0 ORDER BY path", (self.repository_id, self._normalize_directory(parent)))
        result = []
        for row in rows:
            item = dict(row)
            for key in ("responsibilities", "entrypoints", "risks", "architecture_notes"):
                item[key] = json.loads(item[key] or "[]")
            result.append(item)
        return result

    def upsert_directory_analysis(self, directory: str, payload: dict[str, Any]) -> dict[str, Any]:
        details = self.directory_details(directory, include_files=True)
        summary = str(payload.get("summary", "")).strip()
        if not summary or len(summary) > 5000:
            raise InvalidAnalysis("directory summary is required and must be <= 5000 characters")
        confidence = float(payload.get("confidence", 0.5))
        if not 0 <= confidence <= 1:
            raise InvalidAnalysis("confidence must be between 0 and 1")
        fingerprint = hashlib.sha256("|".join(str(item.get("sha256") or "") for item in details["files"]).encode()).hexdigest()
        with self.db.transaction() as conn:
            conn.execute("""INSERT INTO directory_analyses(repository_id,directory_id,source_fingerprint,summary,responsibilities,entrypoints,risks,architecture_notes,confidence,analyzer)
                VALUES (?,?,?,?,?,?,?,?,?,?)""", (self.repository_id, details["id"], fingerprint, summary, json_text(payload.get("responsibilities", [])), json_text(payload.get("entrypoints", [])), json_text(payload.get("risks", [])), json_text(payload.get("architecture_notes", [])), confidence, payload.get("analyzer", "agent")))
            conn.execute("UPDATE directories SET purpose=?,confidence=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (payload.get("purpose"), confidence, details["id"]))
        return {"directory": details["path"], "state": "fresh", "source_fingerprint": fingerprint}

    def start_session(self, agent: str = "unknown", task: str | None = None, external_session_id: str | None = None) -> dict[str, Any]:
        with self.db.transaction() as conn:
            cur = conn.execute("INSERT INTO sessions(external_session_id,repository_id,agent,worktree,branch,task) VALUES (?,?,?,?,?,?)", (external_session_id, self.repository_id, agent, str(self.root), self._branch(), task))
            session_id = int(cur.lastrowid)
        os.environ["REPO_BRAIN_SESSION"] = str(session_id)
        return {"session_id": session_id, "agent": agent, "task": task}

    def end_session(self, session_id: int | None = None, status: str = "completed") -> dict[str, Any]:
        sid = session_id or int(os.getenv("REPO_BRAIN_SESSION", "0") or 0)
        self.db.execute("UPDATE sessions SET ended_at=CURRENT_TIMESTAMP,status=? WHERE id=?", (status, sid))
        return {"session_id": sid, "status": status}

    def _branch(self) -> str | None:
        try:
            return subprocess.check_output(["git", "-C", str(self.root), "branch", "--show-current"], text=True, stderr=subprocess.DEVNULL).strip() or None
        except (OSError, subprocess.CalledProcessError):
            return None

    def read_file(self, value: str, start: int | None = None, end: int | None = None, purpose: str = "context", agent: str | None = None, method: str = "cli") -> dict[str, Any]:
        row = self._file(value)
        path = ensure_inside(self.root, value)
        if row["category"] == "secret":
            raise InvalidPath("secret files cannot be read through Repo Brain")
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        lo = max(1, start or 1)
        hi = min(len(lines), end or len(lines))
        sid = int(os.getenv("REPO_BRAIN_SESSION", "0") or 0) or None
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO reads(session_id,file_id,source_sha256,agent,purpose,read_method,start_line,end_line) VALUES (?,?,?,?,?,?,?,?)", (sid, row["id"], hash_file(path), agent or os.getenv("REPO_BRAIN_AGENT", "unknown"), purpose, method, lo, hi))
        return {"path": row["relative_path"], "content": "\n".join(lines[lo - 1:hi]), "start_line": lo, "end_line": hi, "sha256": hash_file(path), "analysis_state": row["analysis_state"]}

    def _search_rows(self, query: str, limit: int = 12, directory: str | None = None) -> list[dict[str, Any]]:
        terms = [term.lower() for term in re.findall(r"[\w-]+", query) if len(term) > 1]
        rows = self.db.fetchall("""SELECT f.*, a.summary, a.responsibilities, d.path AS directory_path FROM files f LEFT JOIN file_analyses a ON a.file_id=f.id AND a.id=(SELECT id FROM file_analyses aa WHERE aa.file_id=f.id ORDER BY aa.updated_at DESC LIMIT 1) LEFT JOIN directories d ON d.id=f.directory_id WHERE f.repository_id=? AND f.status='active'""", (self.repository_id,))
        directory_prefix = self._normalize_directory(directory) if directory else None
        result = []
        for row in rows:
            if directory_prefix and directory_prefix != "." and row["relative_path"] != directory_prefix and not row["relative_path"].startswith(directory_prefix + "/"):
                continue
            body = " ".join(str(row[key] or "") for key in ("relative_path", "basename", "summary", "responsibilities", "language")).lower()
            symbol_text = " ".join(str(s["name"]) for s in self.db.fetchall("SELECT name FROM symbols WHERE file_id=?", (row["id"],))).lower()
            score = 0.0
            for term in terms:
                if term in row["basename"].lower(): score += 12
                if term in row["relative_path"].lower(): score += 10
                if term in symbol_text: score += 8
                if term in body: score += 4
            if terms and all(term in body or term in symbol_text for term in terms): score += 8
            if row["analysis_state"] == "fresh": score += 2
            elif row["analysis_state"] == "stale": score -= 2
            if score > 0 or not terms:
                result.append({"file_id": row["id"], "path": row["relative_path"], "directory": row["directory_path"] or ".", "state": row["analysis_state"], "category": row["category"], "language": row["language"], "score": round(score, 2), "summary": row["summary"], "responsibilities": json.loads(row["responsibilities"] or "[]"), "symbols": [dict(s) for s in self.db.fetchall("SELECT name,qualified_name,symbol_type,start_line,end_line FROM symbols WHERE file_id=? ORDER BY start_line LIMIT 8", (row["id"],))]})
        return sorted(result, key=lambda item: (-item["score"], item["path"]))[:limit]

    def search(self, query: str, limit: int = 12, directory: str | None = None) -> list[dict[str, Any]]:
        return self._search_rows(query, limit, directory)

    def context(self, task: str, limit: int | None = None, include_stale: bool = True, directory: str | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        limit = max(1, int(limit or self.config.max_context))
        scope = self._normalize_directory(directory) if directory else "."
        results = self._search_rows(task, limit, scope)
        if not include_stale:
            results = [item for item in results if item["state"] != "stale"]
        candidate_tokens = sum(max(1, len(json.dumps(item, ensure_ascii=False)) // 4) for item in results)
        compact = [{**item, "responsibilities": item["responsibilities"][:5], "symbols": item["symbols"][:8]} for item in results]
        estimated_tokens = sum(max(1, len(json.dumps(item, ensure_ascii=False)) // 4) for item in compact)
        compacted_tokens = max(0, candidate_tokens - estimated_tokens)
        groups: dict[str, list[dict[str, Any]]] = {}
        for item in compact:
            groups.setdefault(item["directory"], []).append(item)
        directory_summaries = []
        for directory_path in groups:
            try:
                detail = self.directory_details(directory_path, include_files=False)
                directory_summaries.append({"path": directory_path, "summary": detail.get("summary"), "state": {"fresh": detail.get("fresh_count", 0), "stale": detail.get("stale_count", 0), "needs_review": detail.get("needs_review_count", 0), "pending": detail.get("pending_count", 0)}})
            except InvalidPath:
                directory_summaries.append({"path": directory_path})
        self._record_retrieval_run(task, scope, limit, len(results), len(compact), candidate_tokens, estimated_tokens, compacted_tokens, (time.perf_counter() - started) * 1000)
        return {"task": task, "repository": str(self.root), "directory": scope, "estimated_tokens": estimated_tokens, "brain": self.status(), "directories": directory_summaries, "groups": groups, "results": compact, "read_order": [item["path"] for item in compact], "warnings": [f"{item['path']} is STALE — reread before editing." for item in compact if item["state"] in {"stale", "needs_review"}]}

    def _record_retrieval_run(self, task: str, directory: str, requested_limit: int, candidate_count: int, result_count: int, candidate_tokens: int, estimated_tokens: int, compacted_tokens: int, elapsed_ms: float) -> None:
        """Persist aggregate retrieval metadata without storing task or source content."""
        try:
            session_id = int(os.getenv("REPO_BRAIN_SESSION", "0") or 0) or None
            self.db.execute(
                "INSERT INTO retrieval_runs(repository_id,session_id,task_hash,task_length,directory,requested_limit,candidate_count,result_count,candidate_tokens,estimated_tokens,compacted_tokens,elapsed_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (self.repository_id, session_id, hashlib.sha256(task.strip().encode("utf-8")).hexdigest(), len(task), directory, requested_limit, candidate_count, result_count, candidate_tokens, estimated_tokens, compacted_tokens, round(elapsed_ms, 3)),
            )
        except (OSError, TypeError, ValueError, sqlite3.Error):
            # Telemetry is best effort and must never block discovery.
            return

    def efficiency(self, limit: int = 30, directory: str | None = None) -> dict[str, Any]:
        """Return local, aggregate retrieval efficiency metrics."""
        scope = self._normalize_directory(directory) if directory else None
        limit = max(1, min(int(limit), 500))
        where = "repository_id=?"
        params: list[Any] = [self.repository_id]
        if scope:
            where += " AND directory=?"
            params.append(scope)
        rows = self.db.fetchall(f"SELECT created_at,directory,requested_limit,candidate_count,result_count,candidate_tokens,estimated_tokens,compacted_tokens,elapsed_ms FROM retrieval_runs WHERE {where} ORDER BY id DESC LIMIT ?", tuple(params + [limit]))
        recent = [dict(row) for row in rows]
        if not recent:
            return {"repository": str(self.root), "directory": scope or ".", "runs": 0, "message": "No retrieval metrics recorded yet. Run repo-brain context first."}
        elapsed = sorted(float(row["elapsed_ms"]) for row in recent)
        median_elapsed = elapsed[len(elapsed) // 2]
        totals = {key: sum(int(row[key]) for row in recent) for key in ("candidate_tokens", "estimated_tokens", "compacted_tokens", "candidate_count", "result_count")}
        return {"repository": str(self.root), "directory": scope or ".", "runs": len(recent), "totals": totals, "averages": {"estimated_tokens": round(totals["estimated_tokens"] / len(recent), 1), "compacted_tokens": round(totals["compacted_tokens"] / len(recent), 1), "elapsed_ms": round(sum(float(row["elapsed_ms"]) for row in recent) / len(recent), 2), "median_elapsed_ms": round(median_elapsed, 2), "results": round(totals["result_count"] / len(recent), 1)}, "compaction_percent": round((totals["compacted_tokens"] / totals["candidate_tokens"]) * 100, 1) if totals["candidate_tokens"] else 0, "recent": recent, "definitions": {"candidate_tokens": "Approximate tokens for ranked candidates before compacting fields.", "estimated_tokens": "Approximate tokens in the returned compact context.", "compacted_tokens": "Approximate tokens removed by compacting responsibilities and symbols, not by a user budget.", "elapsed_ms": "Local retrieval time including ranking, compacting and metric recording."}}

    def upsert_analysis(self, file: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = self._file(file)
        summary = str(payload.get("summary", "")).strip()
        if not summary or len(summary) > 5000:
            raise InvalidAnalysis("summary is required and must be <= 5000 characters")
        confidence = float(payload.get("confidence", 0.5))
        if not 0 <= confidence <= 1:
            raise InvalidAnalysis("confidence must be between 0 and 1")
        path = ensure_inside(self.root, file)
        current_hash = hash_file(path)
        payload = {**payload, "summary": summary, "confidence": confidence}
        columns = ["responsibilities", "public_api", "inputs", "outputs", "side_effects", "data_flow", "security_notes", "test_notes", "risks", "architectural_notes"]
        values = {column: json_text(payload.get(column, [])) for column in columns}
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO file_analyses(repository_id,file_id,source_sha256,summary,responsibilities,public_api,inputs,outputs,side_effects,data_flow,security_notes,test_notes,risks,architectural_notes,confidence,analyzer) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (self.repository_id, row["id"], current_hash, summary, *(values[column] for column in columns), confidence, payload.get("analyzer", "agent")))
            conn.execute("INSERT INTO analysis_history(file_id,source_sha256,summary,payload) VALUES (?,?,?,?)", (row["id"], current_hash, summary, json.dumps(payload, ensure_ascii=False)))
            conn.execute("UPDATE files SET analysis_state='fresh',last_analyzed_at=CURRENT_TIMESTAMP WHERE id=? AND sha256=?", (row["id"], current_hash))
            for tag in payload.get("tags", []):
                conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (str(tag),))
                tag_row = conn.execute("SELECT id FROM tags WHERE name=?", (str(tag),)).fetchone()
                conn.execute("INSERT OR IGNORE INTO file_tags(file_id,tag_id) VALUES (?,?)", (row["id"], tag_row["id"]))
            conn.execute("UPDATE bootstrap_queue SET status='analyzed',claimed_by=NULL WHERE file_id=?", (row["id"],))
        self.write_index()
        return {"file": row["relative_path"], "state": "fresh", "sha256": current_hash}

    def status(self) -> dict[str, Any]:
        repo = self.db.fetchone("SELECT * FROM repositories WHERE id=?", (self.repository_id,))
        counts = {row["analysis_state"]: row["count"] for row in self.db.fetchall("SELECT analysis_state,COUNT(*) count FROM files WHERE repository_id=? AND status='active' GROUP BY analysis_state", (self.repository_id,))}
        total = self.db.fetchone("SELECT COUNT(*) count FROM files WHERE repository_id=? AND status='active'", (self.repository_id,))["count"]
        directory_count = self.db.fetchone("SELECT COUNT(*) count FROM directories WHERE repository_id=? AND active_file_count > 0", (self.repository_id,))["count"]
        retrieval_runs = self.db.fetchone("SELECT COUNT(*) count FROM retrieval_runs WHERE repository_id=?", (self.repository_id,))["count"]
        return {"version": APP_VERSION, "repository": str(self.root), "database": str(self.db_path), "files": total, "directories": directory_count, "inventory_coverage": 100 if total else 0, "semantic_coverage": round((counts.get("fresh", 0) / total) * 100, 1) if total else 0, "states": counts, "last_scan": repo["last_scan_at"] if repo else None, "fts": self.db.fts_available, "mcp": True, "database_schema": self.db.migration_status(), "retrieval": {"default_limit": self.config.max_context, "directory_scoped": True, "recorded_runs": retrieval_runs}}

    def coverage(self) -> dict[str, Any]:
        result = self.status()
        result["eligible"] = self.db.fetchone("SELECT COUNT(*) count FROM files WHERE repository_id=? AND status='active' AND category='source'", (self.repository_id,))["count"]
        return result

    def dependencies(self, file: str, reverse: bool = False) -> list[dict[str, Any]]:
        row = self._file(file)
        sql = "SELECT d.*, f.relative_path FROM dependencies d LEFT JOIN files f ON f.id=d.target_file_id WHERE d.source_file_id=?" if not reverse else "SELECT d.*, f.relative_path FROM dependencies d LEFT JOIN files f ON f.id=d.source_file_id WHERE d.target_file_id=?"
        return [dict(item) for item in self.db.fetchall(sql, (row["id"],))]

    def impact(self, file: str, depth: int = 3) -> dict[str, Any]:
        row = self._file(file)
        visited = {row["id"]}
        queue = deque([(row["id"], 0)])
        impacted = []
        while queue:
            node, level = queue.popleft()
            if level >= depth: continue
            for dep in self.db.fetchall("SELECT d.*, f.relative_path FROM dependencies d JOIN files f ON f.id=d.source_file_id WHERE d.target_file_id=?", (node,)):
                if dep["source_file_id"] not in visited:
                    visited.add(dep["source_file_id"]); queue.append((dep["source_file_id"], level + 1)); impacted.append({"path": dep["relative_path"], "depth": level + 1, "type": dep["dependency_type"]})
        return {"source": row["relative_path"], "direct_dependents": [item for item in impacted if item["depth"] == 1], "indirect_dependents": [item for item in impacted if item["depth"] > 1], "related_tests": [item["path"] for item in impacted if "test" in item["path"].lower()], "warnings": [item["path"] + " may need review" for item in impacted]}

    def claim_bootstrap(self, limit: int = 10, worker: str | None = None) -> list[dict[str, Any]]:
        worker = worker or f"worker-{os.getpid()}"
        expiry = (datetime.now(UTC) + timedelta(seconds=self.config.claim_lease_seconds)).isoformat(timespec="seconds")
        claimed = []
        with self.db.transaction() as conn:
            rows = conn.execute("SELECT q.file_id, f.relative_path, f.sha256 FROM bootstrap_queue q JOIN files f ON f.id=q.file_id WHERE f.status='active' AND (q.status='pending' OR q.claim_expires_at < CURRENT_TIMESTAMP) ORDER BY q.priority DESC,q.file_id LIMIT ?", (limit,)).fetchall()
            for row in rows:
                conn.execute("UPDATE bootstrap_queue SET status='claimed',claimed_by=?,claimed_at=CURRENT_TIMESTAMP,claim_expires_at=?,attempts=attempts+1 WHERE file_id=?", (worker, expiry, row["file_id"]))
                claimed.append(dict(row) | {"worker": worker, "claim_expires_at": expiry})
        return claimed

    def complete_bootstrap(self, file: str, worker: str | None = None) -> dict[str, Any]:
        row = self._file(file)
        self.db.execute("UPDATE bootstrap_queue SET status='analyzed',claimed_by=NULL WHERE file_id=? AND (claimed_by=? OR claimed_by IS NULL)", (row["id"], worker or f"worker-{os.getpid()}"))
        return {"file": row["relative_path"], "status": "analyzed"}

    def fail_bootstrap(self, file: str, error: str, worker: str | None = None) -> dict[str, Any]:
        row = self._file(file)
        self.db.execute("UPDATE bootstrap_queue SET status='error',last_error=?,claimed_by=NULL WHERE file_id=?", (error[:1000], row["id"]))
        return {"file": row["relative_path"], "status": "error", "error": error[:1000]}

    def changes(self, limit: int = 50, file: str | None = None) -> list[dict[str, Any]]:
        params: list[Any] = [self.repository_id]
        where = "f.repository_id=?"
        if file:
            row = self._file(file); where += " AND c.file_id=?"; params.append(row["id"])
        params.append(limit)
        return [dict(row) for row in self.db.fetchall(f"SELECT c.*,f.relative_path FROM changes c JOIN files f ON f.id=c.file_id WHERE {where} ORDER BY c.detected_at DESC LIMIT ?", tuple(params))]

    def reads(self, limit: int = 50) -> list[dict[str, Any]]:
        return [dict(row) for row in self.db.fetchall("SELECT r.*,f.relative_path FROM reads r JOIN files f ON f.id=r.file_id WHERE f.repository_id=? ORDER BY r.read_at DESC LIMIT ?", (self.repository_id, limit))]

    def create_plan(self, title: str, task: str, steps: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        with self.db.transaction() as conn:
            cur = conn.execute("INSERT INTO plans(repository_id,session_id,title,task) VALUES (?,?,?,?)", (self.repository_id, int(os.getenv("REPO_BRAIN_SESSION", "0") or 0) or None, title, task))
            pid = int(cur.lastrowid)
            for ordinal, step in enumerate(steps or [], 1):
                conn.execute("INSERT INTO plan_steps(plan_id,ordinal,title,details,target_files) VALUES (?,?,?,?,?)", (pid, ordinal, step.get("title", f"Step {ordinal}"), step.get("details"), json_text(step.get("target_files", []))))
        return self.get_plan(pid)

    def get_plan(self, plan_id: int) -> dict[str, Any]:
        row = self.db.fetchone("SELECT * FROM plans WHERE id=? AND repository_id=?", (plan_id, self.repository_id))
        if not row: return {}
        return dict(row) | {"steps": [dict(step) for step in self.db.fetchall("SELECT * FROM plan_steps WHERE plan_id=? ORDER BY ordinal", (plan_id,))]}

    def update_plan(self, plan_id: int, status: str | None = None, step_id: int | None = None, step_status: str | None = None) -> dict[str, Any]:
        if status: self.db.execute("UPDATE plans SET status=?,updated_at=CURRENT_TIMESTAMP,completed_at=CASE WHEN ?='completed' THEN CURRENT_TIMESTAMP ELSE completed_at END WHERE id=?", (status, status, plan_id))
        if step_id and step_status: self.db.execute("UPDATE plan_steps SET status=? WHERE id=?", (step_status, step_id))
        return self.get_plan(plan_id)

    def add_decision(self, title: str, decision: str, rationale: str = "", alternatives: str = "", consequences: str = "") -> dict[str, Any]:
        with self.db.transaction() as conn:
            cur = conn.execute("INSERT INTO decisions(repository_id,session_id,title,decision,rationale,alternatives,consequences) VALUES (?,?,?,?,?,?,?)", (self.repository_id, int(os.getenv("REPO_BRAIN_SESSION", "0") or 0) or None, title, decision, rationale, alternatives, consequences))
            return dict(conn.execute("SELECT * FROM decisions WHERE id=?", (cur.lastrowid,)).fetchone())

    def decisions(self, limit: int = 50) -> list[dict[str, Any]]:
        return [dict(row) for row in self.db.fetchall("SELECT * FROM decisions WHERE repository_id=? ORDER BY created_at DESC LIMIT ?", (self.repository_id, limit))]

    def export_snapshot(self, output: str | Path | None = None) -> Path:
        target = Path(output) if output else self.root / ".repo-brain" / "export" / "snapshot.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"repository": self.status(), "directories": [dict(row) for row in self.db.fetchall("SELECT path,name,parent_path,depth,summary,purpose,responsibilities,entrypoints,risks,architecture_notes,confidence FROM directories WHERE repository_id=? ORDER BY depth,path", (self.repository_id,))], "directory_analyses": [dict(row) for row in self.db.fetchall("SELECT directory_id,source_fingerprint,summary,responsibilities,entrypoints,risks,architecture_notes,confidence,analyzer FROM directory_analyses WHERE repository_id=?", (self.repository_id,))], "files": [dict(row) for row in self.db.fetchall("SELECT relative_path,sha256,language,category,analysis_state FROM files WHERE repository_id=?", (self.repository_id,))], "analyses": [dict(row) for row in self.db.fetchall("SELECT file_id,source_sha256,summary,responsibilities,risks,confidence,analyzer FROM file_analyses WHERE repository_id=?", (self.repository_id,))], "decisions": self.decisions(), "efficiency": self.efficiency(500), "exported_at": now_iso()}
        target.write_text("\n".join(json.dumps({"kind": kind, "data": data}, ensure_ascii=False) for kind, data in payload.items()) + "\n", encoding="utf-8")
        return target

    def import_snapshot(self, source: str | Path) -> dict[str, Any]:
        imported = 0
        for line in Path(source).read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            record = json.loads(line)
            if record.get("kind") == "decisions":
                for decision in record.get("data", []): self.add_decision(decision["title"], decision["decision"], decision.get("rationale", "")); imported += 1
        return {"imported": imported, "note": "Imported facts remain tied to source hashes; stale files must be reread."}

    def doctor(self) -> dict[str, Any]:
        checks = []
        checks.append({"name": "python", "status": "PASS", "detail": os.sys.version.split()[0]})
        checks.append({"name": "repository", "status": "PASS", "detail": str(self.root)})
        checks.append({"name": "database", "status": "PASS" if self.db_path.exists() else "FAIL", "detail": str(self.db_path)})
        checks.append({"name": "wal", "status": "PASS" if self.db_path.exists() else "WARN"})
        checks.append({"name": "fts5", "status": "PASS" if self.db.fts_available else "WARN", "detail": "fallback LIKE/ranking enabled" if not self.db.fts_available else "available"})
        checks.append({"name": "config", "status": "PASS" if (self.root / ".repo-brain" / "config.toml").exists() else "WARN"})
        schema = self.db.migration_status()
        checks.append({"name": "schema", "status": "PASS" if schema["up_to_date"] else ("FAIL" if schema["drift"] else "WARN"), "detail": f"{schema['current']}/{schema['latest']}"})
        return {"checks": checks, "ok": all(item["status"] != "FAIL" for item in checks)}

    def database_check(self) -> dict[str, Any]:
        """Validate SQLite integrity and migration source consistency."""
        integrity = self.db.fetchone("PRAGMA integrity_check")[0]
        migrations = self.db.migration_status()
        return {"ok": integrity == "ok" and migrations["up_to_date"], "integrity": integrity, "migrations": migrations}

    def write_index(self) -> Path:
        directory = self.root / ".repo-brain"
        directory.mkdir(parents=True, exist_ok=True)
        status = self.status()
        stale = self.db.fetchall("SELECT relative_path,analysis_state FROM files WHERE repository_id=? AND analysis_state IN ('stale','needs_review') AND status='active' ORDER BY relative_path LIMIT 30", (self.repository_id,))
        decisions = self.decisions(10)
        content = ["# Repo Brain", "", "<!-- GENERATED FILE — DO NOT EDIT MANUALLY -->", "", "## Repository", f"- Root: `{self.root}`", f"- Database: `{self.db_path}`", "", "## Health", f"- Files: {status['files']}", f"- Semantic coverage: {status['semantic_coverage']}%", f"- Last scan: {status['last_scan'] or 'never'}", "", "## Stale / needs review"]
        content.extend([f"- `{row['relative_path']}` — {row['analysis_state']}" for row in stale] or ["- None"])
        content += ["", "## Important decisions"]
        schema = status["database_schema"]
        content += ["", "## Database schema", f"- Migrations: {schema['current']}/{schema['latest']}", f"- Source drift: {'detected' if schema['drift'] else 'none'}"]
        content.extend([f"- **{row['title']}** — {row['decision']}" for row in decisions] or ["- None recorded"])
        content += ["", "## How to query", "- `repo-brain scan` before a task", "- `repo-brain context \"your task\"` to locate files", "- `repo-brain read path/to/file.py` to log an auditable read", "", "Memory guides discovery. Current source code determines truth."]
        efficiency = self.efficiency(30)
        content += ["", "## Retrieval efficiency"]
        if efficiency.get("runs"):
            content.extend([f"- Recorded runs: {efficiency['runs']}", f"- Average estimated context: {efficiency['averages']['estimated_tokens']} tokens", f"- Approximate compacted tokens: {efficiency['totals']['compacted_tokens']} ({efficiency['compaction_percent']}%)", f"- Average retrieval time: {efficiency['averages']['elapsed_ms']} ms"])
        else:
            content.append("- No retrieval metrics recorded yet")
        path = directory / "INDEX.md"
        path.write_text("\n".join(content) + "\n", encoding="utf-8")
        stale_index = content.index("## Stale / needs review")
        partitions = self.directories()[:40]
        directory_lines = ["", "## Directory partitions"]
        directory_lines.extend([f"- `{row['path']}` — {row['active_file_count']} files; fresh {row['fresh_count']}, stale {row['stale_count']}; {row['summary'] or 'No directory summary yet'}" for row in partitions] or ["- None"])
        content[stale_index:stale_index] = directory_lines
        path.write_text("\n".join(content) + "\n", encoding="utf-8")
        return path
