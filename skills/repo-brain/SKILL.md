---
name: repo-brain
description: Use Repo Brain to locate current repository code, consult evidence-backed memory, log reads, detect stale analyses, and refresh memory after changes.
---

# Repo Brain

Repo Brain is an offline SQLite map of the repository. Memory guides discovery; current source code determines truth. Every result is partitioned by directory so unrelated areas do not leak into the same context.

## Non-trivial task workflow

1. Run `repo-brain status` and `repo-brain scan`.
2. Identify the smallest relevant directory with `repo-brain directories` or `repo-brain context "<task>" --directory src/auth --json`.
3. Ask for compact context with a result limit and directory scope: `repo-brain context "<task>" --directory src/auth --limit 8 --json` (or MCP `brain_context`). No manual token cap is exposed; compacting is automatic and metrics are observational.
4. Use the returned `directories`, `groups`, `read_order`, summaries, states and warnings as the complete discovery handoff. Do not request the whole database or repeat the same search across unrelated directories.
5. Treat `stale` as a mandatory reread and `needs_review` as a warning before structural edits.
6. Read the current source with `repo-brain read path/to/file.py` or MCP `brain_read_file`; never edit from a summary alone.
7. Check `repo-brain impact path/to/file.py` before cross-module changes. Create a plan for features, refactors, migrations, security work, or multi-module bugs.
8. During work, record only concise technical facts, directory purpose, decisions, plans, and evidence — never private chain-of-thought or secrets.
9. After edits, run `repo-brain scan`, reread changed files, update file/directory analyses, run tests, verify stale/needs-review output, and inspect `repo-brain efficiency --json` when tuning retrieval.

## Bootstrap mode

If the database is missing or coverage is low, run `repo-brain init`, list the directory partitions, then claim work with `repo-brain bootstrap claim --limit 10`. Work one directory at a time: read each claimed file, record analysis, summarize the directory when its children are understood, and complete each claim. Claims have leases so multiple agents can cooperate.

## Session and safety

Start with `repo-brain session start --agent codex --task "..."`; the returned ID is reused through `REPO_BRAIN_SESSION`. Paths are constrained to the repository root. Secret files are not read or stored. Always validate the current file hash and line evidence before relying on memory.

## Progressive disclosure

Use directory context first, then the smallest relevant files, symbols/dependencies, current code, and only then broader exploration. Keep the result limit appropriate to the task, preserve the returned read order, and inspect efficiency metrics for observation rather than imposing a token budget. Default responses are intentionally compact to protect agent context.
