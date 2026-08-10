"""Minimal MCP JSON-RPC stdio transport with no mandatory runtime dependency.

When the official ``mcp`` package is installed, the same service methods can be
wrapped by a host-specific adapter. The fallback here keeps offline installs
usable and speaks the core initialize/tools/list/tools/call methods.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from .core import Brain

TOOLS = {
    "brain_status": "Show repository memory health and coverage.",
    "brain_scan": "Scan the repository and mark changed files stale.",
    "brain_context": "Rank the smallest useful set of files for a task.",
    "brain_search": "Search indexed paths, symbols and analyses.",
    "brain_file": "Return an indexed file record.",
    "brain_read_file": "Read current source with line range and audit log.",
    "brain_symbols": "List symbols extracted from a file.",
    "brain_dependencies": "List dependencies of a file.",
    "brain_dependents": "List files that depend on a file.",
    "brain_impact": "Traverse direct and indirect impact.",
    "brain_modules": "List architectural modules.",
    "brain_stale": "List stale and needs_review files.",
    "brain_coverage": "Show inventory and semantic coverage.",
    "brain_session_start": "Start an auditable agent session.",
    "brain_session_end": "End an agent session.",
    "brain_record_read": "Record a read without returning source.",
    "brain_analysis_upsert": "Persist evidence-first semantic analysis.",
    "brain_plan_create": "Create a persistent change plan.",
    "brain_plan_update": "Update a persistent plan.",
    "brain_plan_get": "Retrieve a plan.",
    "brain_decision_record": "Record a reusable technical decision.",
    "brain_decisions": "List decisions.",
    "brain_changes": "List observed changes.",
    "brain_bootstrap_status": "Show cooperative bootstrap queue.",
    "brain_bootstrap_claim": "Claim a bootstrap batch with a lease.",
    "brain_bootstrap_complete": "Complete a bootstrap item.",
    "brain_bootstrap_fail": "Mark a bootstrap item as failed.",
    "brain_refresh_index": "Regenerate .repo-brain/INDEX.md.",
}


def tool_schemas() -> list[dict[str, Any]]:
    return [{"name": name, "description": desc, "inputSchema": {"type": "object"}} for name, desc in TOOLS.items()]


def call_tool(brain: Brain, name: str, args: dict[str, Any]) -> Any:
    if name == "brain_status": return brain.status()
    if name == "brain_scan": return brain.scan()
    if name == "brain_context": return brain.context(args.get("task", ""), int(args.get("limit", 12)), bool(args.get("include_stale", True)))
    if name == "brain_search": return brain.search(args.get("query", ""), int(args.get("limit", 12)))
    if name == "brain_file": return dict(brain._file(args["file"]))
    if name == "brain_read_file": return brain.read_file(args["file"], args.get("start_line"), args.get("end_line"), args.get("purpose", "context"), args.get("agent"), "mcp")
    if name == "brain_symbols": return [dict(row) for row in brain.db.fetchall("SELECT s.*,f.relative_path FROM symbols s JOIN files f ON f.id=s.file_id WHERE f.relative_path=?", (args["file"],))]
    if name == "brain_dependencies": return brain.dependencies(args["file"])
    if name == "brain_dependents": return brain.dependencies(args["file"], True)
    if name == "brain_impact": return brain.impact(args["file"], int(args.get("max_depth", 3)))
    if name == "brain_modules": return [dict(row) for row in brain.db.fetchall("SELECT * FROM modules WHERE repository_id=?", (brain.repository_id,))]
    if name == "brain_stale": return [dict(row) for row in brain.db.fetchall("SELECT relative_path,analysis_state,sha256,last_changed_at FROM files WHERE repository_id=? AND analysis_state IN ('stale','needs_review')", (brain.repository_id,))]
    if name == "brain_coverage": return brain.coverage()
    if name == "brain_session_start": return brain.start_session(args.get("agent", "unknown"), args.get("task"), args.get("external_session_id"))
    if name == "brain_session_end": return brain.end_session(args.get("session_id"), args.get("status", "completed"))
    if name == "brain_record_read": return brain.read_file(args["file"], args.get("start_line"), args.get("end_line"), args.get("purpose", "mcp"), args.get("agent"), "mcp")
    if name == "brain_analysis_upsert": return brain.upsert_analysis(args["file"], args.get("analysis", args))
    if name == "brain_plan_create": return brain.create_plan(args["title"], args["task"], args.get("steps", []))
    if name == "brain_plan_update": return brain.update_plan(int(args["plan_id"]), args.get("status"), args.get("step_id"), args.get("step_status"))
    if name == "brain_plan_get": return brain.get_plan(int(args["plan_id"]))
    if name == "brain_decision_record": return brain.add_decision(args["title"], args["decision"], args.get("rationale", ""), args.get("alternatives", ""), args.get("consequences", ""))
    if name == "brain_decisions": return brain.decisions(int(args.get("limit", 50)))
    if name == "brain_changes": return brain.changes(int(args.get("limit", 50)), args.get("file"))
    if name == "brain_bootstrap_status": return [dict(row) for row in brain.db.fetchall("SELECT q.*,f.relative_path FROM bootstrap_queue q JOIN files f ON f.id=q.file_id WHERE f.repository_id=?", (brain.repository_id,))]
    if name == "brain_bootstrap_claim": return brain.claim_bootstrap(int(args.get("limit", 10)), args.get("worker"))
    if name == "brain_bootstrap_complete": return brain.complete_bootstrap(args["file"], args.get("worker"))
    if name == "brain_bootstrap_fail": return brain.fail_bootstrap(args["file"], args.get("error", "unknown"), args.get("worker"))
    if name == "brain_refresh_index": return {"path": str(brain.write_index())}
    raise ValueError(f"unknown tool: {name}")


def serve_stdio(brain: Brain) -> None:
    """Run the MCP core loop; stdout is reserved for JSON-RPC frames."""
    for raw in sys.stdin:
        if not raw.strip():
            continue
        try:
            request = json.loads(raw)
            method = request.get("method")
            if method == "initialize":
                result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "repo-brain", "version": "0.1.0"}}
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                result = {"tools": tool_schemas()}
            elif method == "tools/call":
                params = request.get("params", {})
                value = call_tool(brain, params["name"], params.get("arguments", {}))
                result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, default=str)}], "structuredContent": value}
            else:
                result = {"error": {"code": -32601, "message": f"method not found: {method}"}}
            if "id" in request:
                print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}, ensure_ascii=False), flush=True)
        except (ValueError, KeyError, OSError, TypeError) as exc:
            if "id" in locals().get("request", {}):
                print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32000, "message": str(exc)}}, ensure_ascii=False), flush=True)
