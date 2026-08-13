# Changelog

## 0.4.0 - 2026-08-12

- Made packaged numbered SQL files the single migration source; removed duplicated inline schemas from the database runner.
- Added migration 004 to converge legacy retrieval telemetry on compact fields and migration 005 for immutable source checksums, paths and drift diagnostics.
- Added clean-install, legacy-upgrade and idempotence coverage for migrations, plus `repo-brain db check` and schema details in status/INDEX output.
- Removed the active manual token-budget control from configuration, CLI, MCP, UI and skills. Token estimates remain observational and compacting is automatic.
- Published the multilingual documentation and directory/SQL governance plan for v0.4.0.

## 0.3.0 — 2026-08-11

- Added privacy-preserving retrieval efficiency telemetry for approximate tokens, omitted candidates, result counts and local elapsed time.
- Added `repo-brain efficiency`, MCP `brain_efficiency`, UI `/api/efficiency`, migration 003 and exported/indexed efficiency summaries.
- Added the versioned token-efficiency plan with targets, formulas, implementation phases, privacy rules and decision logging.
- Added the directory/SQL governance plan clarifying automatic file-change records versus explicit immutable schema migrations.

## 0.2.0 — 2026-08-10

- Added directory-scoped memory, directory analyses, grouped UI/API results and compact context.
- Expanded multilingual README documentation.

## 0.1.0 — 2026-08-10

- Initial offline-first SQLite memory, scanner, graph, search, CLI, MCP stdio transport and local UI.
- Codex and Claude Code skills, hooks, documentation and packaging included.

