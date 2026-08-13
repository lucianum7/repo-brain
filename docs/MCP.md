# MCP

Run `repo-brain mcp serve` as a stdio server. Configure a host with command `repo-brain` and arguments `mcp serve`. The server implements `initialize`, `tools/list`, and `tools/call`, exposing status, scan, context, search, read, graph, sessions, analysis, plans, decisions, bootstrap and index tools.

The optional `mcp` dependency follows the current official Python SDK v2 line; the built-in transport is intentionally dependency-free for offline use. Never print logs to stdout while the MCP process is running.

