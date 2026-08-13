from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .core import Brain
from .errors import RepoBrainError


def _json_or_print(value: Any, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
        return
    if isinstance(value, str):
        print(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                print(f"{key}: {json.dumps(item, ensure_ascii=False, default=str)}")
            else:
                print(f"{key}: {item}")
    elif isinstance(value, list):
        for item in value:
            print(item.get("path", item) if isinstance(item, dict) else item)
    else:
        print(value)


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repo-brain", description="Persistent repository memory for coding agents.")
    parser.add_argument("--root", help="repository root (defaults to current directory)")
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in {
        "init": "initialize database and scan", "scan": "scan repository", "status": "show health",
        "coverage": "show coverage", "index": "refresh INDEX.md", "doctor": "diagnose setup",
        "migrate": "apply database migrations", "reads": "show auditable reads", "changes": "show changes",
        "history": "show change and read history", "modules": "show modules", "directories": "list directory memory partitions", "stale": "list stale files",
    }.items():
        p = sub.add_parser(name, help=help_text); _common(p)
    p = sub.add_parser("context", help="rank files for a task"); p.add_argument("task"); p.add_argument("--limit", type=int, default=12); p.add_argument("--directory", help="scope to a directory and its descendants"); p.add_argument("--no-stale", action="store_false", dest="include_stale", default=True); _common(p)
    p = sub.add_parser("search", help="search indexed files"); p.add_argument("query"); p.add_argument("--limit", type=int, default=12); p.add_argument("--directory", help="scope to a directory and its descendants"); _common(p)
    p = sub.add_parser("directory", help="show one directory partition"); p.add_argument("path", nargs="?", default="."); p.add_argument("--no-files", action="store_false", dest="include_files", default=True); _common(p)
    p = sub.add_parser("efficiency", help="show recorded token and retrieval-time metrics"); p.add_argument("--limit", type=int, default=30); p.add_argument("--directory", help="filter metrics to a directory"); _common(p)
    p = sub.add_parser("analyze-directory", help="persist analysis for a directory"); p.add_argument("path"); p.add_argument("--json-file", type=Path); p.add_argument("--summary"); _common(p)
    p = sub.add_parser("read", help="read and log a file"); p.add_argument("file"); p.add_argument("--start", type=int); p.add_argument("--end", type=int); p.add_argument("--purpose", default="context"); _common(p)
    p = sub.add_parser("file", help="show a file record"); p.add_argument("file"); _common(p)
    p = sub.add_parser("symbols", help="show symbols"); p.add_argument("file", nargs="?"); _common(p)
    for command in ("deps", "dependents"):
        p = sub.add_parser(command); p.add_argument("file"); _common(p)
    p = sub.add_parser("impact"); p.add_argument("file"); p.add_argument("--depth", type=int, default=3); _common(p)
    p = sub.add_parser("analyze"); p.add_argument("file"); p.add_argument("--json-file", type=Path); p.add_argument("--summary"); _common(p)
    p = sub.add_parser("session"); ss = p.add_subparsers(dest="session_command", required=True); p1 = ss.add_parser("start"); p1.add_argument("--agent", default="unknown"); p1.add_argument("--task"); p1.add_argument("--external-id"); _common(p1); p2 = ss.add_parser("end"); p2.add_argument("--session", type=int); p2.add_argument("--status", default="completed"); _common(p2)
    p = sub.add_parser("plan"); ps = p.add_subparsers(dest="plan_command", required=True); p1 = ps.add_parser("create"); p1.add_argument("title"); p1.add_argument("task"); p1.add_argument("--json-file", type=Path); _common(p1); p2 = ps.add_parser("show"); p2.add_argument("id", type=int); _common(p2); p3 = ps.add_parser("update"); p3.add_argument("id", type=int); p3.add_argument("--status"); p3.add_argument("--step", type=int); p3.add_argument("--step-status"); _common(p3)
    p = sub.add_parser("plans"); _common(p)
    p = sub.add_parser("decision"); ds = p.add_subparsers(dest="decision_command", required=True); p1 = ds.add_parser("add"); p1.add_argument("title"); p1.add_argument("decision"); p1.add_argument("--rationale", default=""); p1.add_argument("--alternatives", default=""); p1.add_argument("--consequences", default=""); _common(p1); p2 = ds.add_parser("show"); p2.add_argument("id", type=int); _common(p2)
    p = sub.add_parser("decisions"); _common(p)
    p = sub.add_parser("bootstrap"); bs = p.add_subparsers(dest="bootstrap_command", required=True); p1 = bs.add_parser("status"); _common(p1); p2 = bs.add_parser("claim"); p2.add_argument("--limit", type=int, default=10); p2.add_argument("--worker"); _common(p2); p3 = bs.add_parser("complete"); p3.add_argument("file"); p3.add_argument("--worker"); _common(p3); p4 = bs.add_parser("fail"); p4.add_argument("file"); p4.add_argument("error"); p4.add_argument("--worker"); _common(p4)
    p = sub.add_parser("export"); p.add_argument("--output", type=Path); _common(p)
    p = sub.add_parser("import"); p.add_argument("source", type=Path); _common(p)
    p = sub.add_parser("db"); dbs = p.add_subparsers(dest="db_command", required=True); p1 = dbs.add_parser("path"); _common(p1); p2 = dbs.add_parser("check"); _common(p2); p3 = dbs.add_parser("vacuum"); _common(p3)
    p = sub.add_parser("mcp"); ms = p.add_subparsers(dest="mcp_command", required=True); p1 = ms.add_parser("serve"); _common(p1)
    p = sub.add_parser("ui", help="start local browser interface"); p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8765); _common(p)
    p = sub.add_parser("install"); p.add_argument("--codex", action="store_true"); p.add_argument("--claude", action="store_true"); p.add_argument("--all", action="store_true"); p.add_argument("--dry-run", action="store_true"); _common(p)
    p = sub.add_parser("uninstall"); p.add_argument("--purge-data", action="store_true"); p.add_argument("--dry-run", action="store_true"); _common(p)
    p = sub.add_parser("integrate"); p.add_argument("target", choices=["codex", "claude"]); p.add_argument("--dry-run", action="store_true"); _common(p)
    return parser


def _install(brain: Brain, args: argparse.Namespace) -> dict[str, Any]:
    root = brain.root
    source = Path(__file__).resolve().parents[2] / "skills" / "repo-brain" / "SKILL.md"
    if not source.exists():
        source = Path(__file__).resolve().parent / "templates" / "SKILL.md"
    targets = []
    if args.all or (not args.codex and not args.claude): args.codex = args.claude = True
    if args.codex: targets.append(root / ".agents" / "skills" / "repo-brain" / "SKILL.md")
    if args.claude: targets.append(root / ".claude" / "skills" / "repo-brain" / "SKILL.md")
    actions = []
    for target in targets:
        actions.append(str(target))
        if not args.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.exists(): shutil.copyfile(source, target)
    marker = "<!-- repo-brain:start -->\nUse Repo Brain before non-trivial changes: run `repo-brain scan`, choose a scope with `repo-brain directories`, query compact context with `repo-brain context --directory PATH`, read current files with `repo-brain read`, and refresh file/directory memory after edits.\n<!-- repo-brain:end -->"
    for name in (["AGENTS.md"] if args.codex else []) + (["CLAUDE.md"] if args.claude else []):
        target = root / name; actions.append(str(target))
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        if "<!-- repo-brain:start -->" not in existing and not args.dry_run:
            target.write_text(existing.rstrip() + ("\n\n" if existing.strip() else "") + marker + "\n", encoding="utf-8")
    if not args.dry_run: brain.init()
    return {"installed": actions, "dry_run": args.dry_run}


def _uninstall(brain: Brain, args: argparse.Namespace) -> dict[str, Any]:
    removed = []
    for target in [brain.root / ".agents" / "skills" / "repo-brain", brain.root / ".claude" / "skills" / "repo-brain"]:
        if target.exists():
            removed.append(str(target))
            if not args.dry_run: shutil.rmtree(target)
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = brain.root / name
        if path.exists():
            text = path.read_text(encoding="utf-8")
            old_markers = [
                "<!-- repo-brain:start -->\nUse Repo Brain before non-trivial changes: run `repo-brain scan`, choose a scope with `repo-brain directories`, query compact context with `repo-brain context --directory PATH`, read current files with `repo-brain read`, and refresh file/directory memory after edits.\n<!-- repo-brain:end -->",
                "<!-- repo-brain:start -->\nUse Repo Brain before non-trivial changes: run `repo-brain scan`, query `repo-brain context`, read current files with `repo-brain read`, and refresh memory after edits.\n<!-- repo-brain:end -->",
            ]
            cleaned = text
            for marker in old_markers:
                cleaned = cleaned.replace(marker, "")
            cleaned = cleaned.strip() + "\n"
            if cleaned != text and not args.dry_run: path.write_text(cleaned, encoding="utf-8")
    if args.purge_data and brain.db_path.exists() and not args.dry_run: brain.db_path.unlink()
    return {"removed": removed, "purged_data": args.purge_data, "dry_run": args.dry_run}


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        brain = Brain(args.root, require_initialized=args.command not in {"init", "install", "ui", "mcp"})
        if args.command == "init": value = brain.init()
        elif args.command == "scan": value = brain.scan()
        elif args.command == "status": value = brain.status()
        elif args.command == "coverage": value = brain.coverage()
        elif args.command == "context": value = brain.context(args.task, args.limit, args.include_stale, args.directory)
        elif args.command == "search": value = brain.search(args.query, args.limit, args.directory)
        elif args.command == "directories": value = brain.directories()
        elif args.command == "efficiency": value = brain.efficiency(args.limit, args.directory)
        elif args.command == "directory": value = brain.directory_details(args.path, args.include_files)
        elif args.command == "analyze-directory":
            payload = json.loads(args.json_file.read_text(encoding="utf-8")) if args.json_file else {"summary": args.summary or "Directory analysis", "analyzer": "agent"}
            value = brain.upsert_directory_analysis(args.path, payload)
        elif args.command == "read": value = brain.read_file(args.file, args.start, args.end, args.purpose)
        elif args.command == "file": value = dict(brain._file(args.file))
        elif args.command == "symbols": value = [dict(row) for row in brain.db.fetchall("SELECT s.*,f.relative_path FROM symbols s JOIN files f ON f.id=s.file_id WHERE f.repository_id=?" + (" AND f.relative_path=?" if args.file else "") + " ORDER BY f.relative_path,s.start_line", (brain.repository_id, args.file) if args.file else (brain.repository_id,))]
        elif args.command == "deps": value = brain.dependencies(args.file)
        elif args.command == "dependents": value = brain.dependencies(args.file, reverse=True)
        elif args.command == "impact": value = brain.impact(args.file, args.depth)
        elif args.command == "stale": value = [dict(row) for row in brain.db.fetchall("SELECT relative_path,analysis_state,sha256,last_changed_at FROM files WHERE repository_id=? AND analysis_state IN ('stale','needs_review') ORDER BY relative_path", (brain.repository_id,))]
        elif args.command == "analyze":
            payload = json.loads(args.json_file.read_text(encoding="utf-8")) if args.json_file else {"summary": args.summary or "Agent analysis", "analyzer": "agent"}
            value = brain.upsert_analysis(args.file, payload)
        elif args.command == "session": value = brain.start_session(args.agent, args.task, args.external_id) if args.session_command == "start" else brain.end_session(args.session, args.status)
        elif args.command == "plan":
            if args.plan_command == "create":
                payload = json.loads(args.json_file.read_text(encoding="utf-8")) if args.json_file else {}
                value = brain.create_plan(args.title, args.task, payload.get("steps", []))
            elif args.plan_command == "show": value = brain.get_plan(args.id)
            else: value = brain.update_plan(args.id, args.status, args.step, args.step_status)
        elif args.command == "plans": value = [dict(row) for row in brain.db.fetchall("SELECT * FROM plans WHERE repository_id=? ORDER BY updated_at DESC", (brain.repository_id,))]
        elif args.command == "decision": value = brain.add_decision(args.title, args.decision, args.rationale, args.alternatives, args.consequences) if args.decision_command == "add" else next((d for d in brain.decisions() if d["id"] == args.id), {})
        elif args.command == "decisions": value = brain.decisions()
        elif args.command == "bootstrap":
            if args.bootstrap_command == "status": value = [dict(row) for row in brain.db.fetchall("SELECT q.*,f.relative_path FROM bootstrap_queue q JOIN files f ON f.id=q.file_id WHERE f.repository_id=? ORDER BY q.priority DESC", (brain.repository_id,))]
            elif args.bootstrap_command == "claim": value = brain.claim_bootstrap(args.limit, args.worker)
            elif args.bootstrap_command == "complete": value = brain.complete_bootstrap(args.file, args.worker)
            else: value = brain.fail_bootstrap(args.file, args.error, args.worker)
        elif args.command == "reads": value = brain.reads()
        elif args.command in {"changes", "history"}: value = brain.changes()
        elif args.command == "index": value = {"path": str(brain.write_index())}
        elif args.command == "export": value = {"path": str(brain.export_snapshot(args.output))}
        elif args.command == "import": value = brain.import_snapshot(args.source)
        elif args.command == "migrate":
            brain.db.migrate(); value = {"database": str(brain.db_path), "migrations": brain.db.migration_status()}
        elif args.command == "doctor": value = brain.doctor()
        elif args.command == "db":
            if args.db_command == "path": value = {"path": str(brain.db_path)}
            elif args.db_command == "check": value = brain.database_check()
            else: brain.db.vacuum(); value = {"vacuumed": True}
        elif args.command == "install": value = _install(brain, args)
        elif args.command == "uninstall": value = _uninstall(brain, args)
        elif args.command == "integrate": value = {"target": args.target, "dry_run": args.dry_run, "message": "Use integrations/ templates; no global configuration changed."}
        elif args.command == "mcp":
            from .mcp import serve_stdio
            serve_stdio(brain); return
        elif args.command == "ui":
            from .ui import serve
            serve(brain, args.host, args.port); return
        else: value = {}
        _json_or_print(value, getattr(args, "json", False))
    except RepoBrainError as exc:
        print(f"repo-brain: {exc}", file=sys.stderr)
        raise SystemExit(2)
