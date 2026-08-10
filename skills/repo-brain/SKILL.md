---
name: repo-brain
description: Use Repo Brain to locate current repository code, consult evidence-backed memory, log reads, detect stale analyses, and refresh memory after changes.
---

# Repo Brain

Repo Brain is an offline SQLite map of the repository. Memory guides discovery; current source code determines truth.

## Non-trivial task workflow

1. Run `repo-brain status` and `repo-brain scan`.
2. Ask `repo-brain context "<task>" --json` (or MCP `brain_context`) and start with the ranked files.
3. Treat `stale` as a mandatory reread and `needs_review` as a warning before structural edits.
4. Read the current source with `repo-brain read path/to/file.py` or MCP `brain_read_file`; never edit from a summary alone.
5. Check `repo-brain impact path/to/file.py` before cross-module changes. Create a plan for features, refactors, migrations, security work, or multi-module bugs.
6. During work, record only concise technical facts, decisions, plans, and evidence — never private chain-of-thought or secrets.
7. After edits, run `repo-brain scan`, reread changed files, update an analysis with `repo-brain analyze FILE --json-file analysis.json`, run tests, and verify stale/needs-review output.

## Bootstrap mode

If the database is missing or coverage is low, run `repo-brain init`, then claim work with `repo-brain bootstrap claim --limit 10`. Read each claimed file, record analysis, and complete the claim. Claims have leases so multiple agents can cooperate.

## Session and safety

Start with `repo-brain session start --agent codex --task "..."`; the returned ID is reused through `REPO_BRAIN_SESSION`. Paths are constrained to the repository root. Secret files are not read or stored. Always validate the current file hash and line evidence before relying on memory.

## Progressive disclosure

Use context first, then the smallest relevant files, symbols/dependencies, current code, and only then broader exploration. Default responses are intentionally limited to protect agent context.

