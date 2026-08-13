# Repo Brain

Persistent repository memory for coding agents.

[English](README.md) · [Português do Brasil](README.pt-BR.md) · [简体中文](README.zh-CN.md)

Repo Brain is an offline-first skill, CLI, SQLite memory and MCP server that helps a coding agent find the right place to work without rereading an entire repository at the start of every task.

> Memory guides discovery. Current source code determines truth.

## What the skill does

The `repo-brain` skill teaches an agent a repeatable, evidence-first workflow:

1. Check the repository health and run an incremental scan.
2. Search the memory for the task and rank likely files, symbols, tests and dependencies.
3. Read the current source through an auditable `read` operation before editing.
4. Check stale analyses, direct dependents and architectural decisions.
5. Create a persistent plan for a feature, refactor, migration, security change or multi-module bug.
6. Make the change, run project tests and scan again.
7. Refresh the analysis using the new source hash and finish the session.

The skill never grants permission to edit from an old summary. When a file hash changes, its analysis becomes `stale`; direct dependents can become `needs_review`. An agent must reread the current file before a critical change.

## Directory-scoped memory and token economy

Memory is partitioned by normalized repository directory. Every indexed file belongs to its immediate directory, while each directory also carries subtree counts, a compact summary, responsibilities, entry points, risks and freshness state. A directory analysis never replaces source reading: it is a short routing layer that tells the agent where to look first.

Start with the directory map, then keep retrieval scoped:

```bash
repo-brain directories --json
repo-brain directory src/auth --json
repo-brain context "rotate password reset tokens" --directory src/auth --limit 8 --json
repo-brain analyze-directory src/auth --json-file auth-directory.json
```

`context` returns `groups` separated by directory, directory summaries and states, an intentional `read_order`, stale warnings and `estimated_tokens`. No manual token cap is exposed. Prefer one directory per retrieval and a result limit appropriate to the task; automatic compacting removes repeated symbols and responsibilities while preserving the handoff. Use the returned paths with `repo-brain read`, then verify the current hashes before editing.

The local UI keeps the same boundary: its sidebar and scope selector show one directory at a time (including descendants), while an all-directories search remains visibly grouped instead of mixing files into one list.

## Measuring token and time efficiency

Every `context` call records privacy-preserving local metadata in `retrieval_runs`: a task hash and length, directory, result limit, candidate/result counts, approximate candidate/selected/compacted tokens and elapsed milliseconds. Task text, source content and private model reasoning are never stored. The estimates compare retrievals; they are not a provider invoice.

Inspect the trend:

```bash
repo-brain efficiency --limit 100 --json
repo-brain efficiency --directory src/auth --json
```

The report is also available as MCP `brain_efficiency`, `/api/efficiency` in the local UI, `status.retrieval.recorded_runs`, `.repo-brain/INDEX.md` and exported snapshots. See the versioned [token-efficiency plan](docs/TOKEN_EFFICIENCY_PLAN.md) for targets, formulas, phases, privacy rules and a decision log template.

## Directory updates and SQL changes

`repo-brain scan` automatically records changed files in `changes`, including old/new hashes, reason and timestamp. It does not rewrite SQL files. A database schema change must be a new numbered migration under `src/repo_brain/migrations/`; applied migrations are immutable. `repo-brain db check --json` reports integrity, pending versions and migration-source drift. Follow the [directory and SQL improvement plan](docs/DIRECTORY_IMPROVEMENT_PLAN.md) for the upgrade checklist and organization rules.

## Requirements

- Python 3.11 or newer.
- SQLite 3 with WAL support (included with Python).
- Git is optional. Git repositories share a database between worktrees; non-Git projects store data under `.repo-brain/`.
- No API key, cloud account, external database, model or internet connection is required during normal use.
- FTS5 is used when available. A deterministic SQL/ranking fallback keeps search working when FTS5 is unavailable.

## Install

From a published package:

```bash
python -m pip install repo-brain
```

From this repository while developing:

```bash
python -m pip install -e ".[dev]"
```

Then install the agent integrations in the project you want to remember:

```bash
cd /path/to/your-project
repo-brain install --all
repo-brain init
```

`install --codex` creates `.agents/skills/repo-brain/SKILL.md` and a managed block in `AGENTS.md`. `install --claude` creates the Claude skill and a managed block in `CLAUDE.md`. Existing user content is preserved. Use `--dry-run` to preview changes.

## First run and database location

`repo-brain init` creates configuration, applies migrations, inventories files, calculates hashes, extracts static symbols and dependencies, fills the bootstrap queue and generates `.repo-brain/INDEX.md`.

To see the exact database path:

```bash
repo-brain db path
```

For a Git repository, the default is `<git-common-dir>/repo-brain/brain.db`, so worktrees use the same memory. For a non-Git project, it is `.repo-brain/brain.db`. The database and WAL sidecars should not be committed; `.repo-brain/INDEX.md` is a compact human dashboard and can be generated whenever needed.

## Daily agent workflow

```text
status → scan → context → read current code → plan (if needed)
      → edit → tests → scan → analysis refresh → index/session finish
```

Typical commands:

```bash
repo-brain status
repo-brain scan
repo-brain context "change password reset token expiration and email flow"
repo-brain read src/auth/password_reset.py
repo-brain impact src/auth/token.py --depth 3
repo-brain analyze src/auth/password_reset.py --json-file analysis.json
repo-brain scan
```

Use `--json` on status, context, search, coverage, reads, changes, graph, bootstrap and other commands when an agent or script consumes the result.

## What is stored

SQLite stores repository identity, relative paths, normalized paths, file hashes, language/category, line counts, analysis states, directory partitions, directory analyses, symbols, dependency edges, modules, sessions, reads, changes, plans, decisions, observations and tags. Agent analyses are versioned in `analysis_history`; directory analyses are versioned in `directory_analyses` with a source fingerprint.

Repo Brain does not store full source files by default. Secret-looking files (`.env`, keys, certificates, credentials and similar patterns) are excluded from semantic analysis. Read and write hooks record paths, hashes, tools, sessions and timestamps—not raw write content.

## Core commands

| Area | Commands |
| --- | --- |
| Setup | `init`, `install`, `uninstall`, `migrate`, `doctor` |
| Health | `status`, `coverage`, `stale`, `index`, `db path`, `db check`, `db vacuum` |
| Discovery | `search`, `context`, `directories`, `directory`, `efficiency`, `file`, `symbols`, `modules` |
| Graph | `deps FILE`, `dependents FILE`, `impact FILE --depth N` |
| Audit | `read FILE`, `reads`, `changes`, `history` |
| Agent memory | `session`, `analyze`, `analyze-directory`, `plan`, `decision` |
| Bootstrap | `bootstrap status`, `claim`, `complete`, `fail` |
| Portability | `export`, `import` |
| Integrations | `mcp serve`, `ui`, `integrate codex`, `integrate claude` |

Run `repo-brain COMMAND --help` for the exact arguments.

## Bootstrap mode

Large projects can be analyzed cooperatively:

```bash
repo-brain bootstrap claim --limit 10
repo-brain read path/to/file.py --purpose bootstrap
repo-brain analyze path/to/file.py --json-file analysis.json
repo-brain bootstrap complete path/to/file.py
```

Claims have leases, so two agents do not receive the same active item. A failed worker can leave an item to be reclaimed after the lease expires.

## Analyses and evidence

An agent can persist a concise factual analysis such as:

```json
{
  "summary": "Creates and rotates password-reset tokens.",
  "responsibilities": ["validate expiry", "prevent replay"],
  "security_notes": ["invalidate the previous token after rotation"],
  "risks": ["replay if rotation is not atomic"],
  "tags": ["auth", "security"],
  "confidence": 0.9
}
```

Important observations should include the file, source hash, line range and confidence. Do not store private model reasoning or secrets.

## MCP server

Start the local stdio server:

```bash
repo-brain mcp serve
```

It exposes tools for status, scan, context, search, file reads, symbols, dependencies, impact, sessions, analysis, plans, decisions, bootstrap and index refresh. `brain_read_file` validates the path, reads a line range, records the read and returns the current hash and analysis state.

Configure an MCP host to run `repo-brain` with arguments `mcp serve`. The repository also includes a Claude plugin manifest and `.mcp.json` template.

## Local interface

The dependency-free local dashboard is served by the same application layer:

```bash
repo-brain ui --host 127.0.0.1 --port 8765
```

Open <http://127.0.0.1:8765>. It shows file counts, semantic coverage, fresh/stale state and contextual search results. The server is local-only unless you deliberately bind it to another interface.

## Codex and Claude Code

The canonical skill is `skills/repo-brain/SKILL.md`. The Claude distributable plugin is under `integrations/claude-plugin/`; it contains a skill, hook configuration, safe hook script and MCP configuration. Hooks are best-effort: a Repo Brain failure must never block the user's edit.

## Configuration

`repo-brain init` creates `.repo-brain/config.toml`. Configure include/exclude patterns, maximum file size, allowed/ignored extensions, secret patterns, ranking limits and bootstrap lease duration. Keep the database, WAL sidecars and local logs out of version control.

## Export and import

```bash
repo-brain export
repo-brain import .repo-brain/export/snapshot.jsonl
```

Snapshots contain sanitized metadata, hashes, analyses, relationships and decisions—not full source. Imported facts are tied to their original hashes and must be treated as stale when the current source differs.

## Security and privacy

- Offline-first with no external telemetry; efficiency metrics stay in the local SQLite database.
- Canonical path validation prevents traversal and repository-root escapes.
- Parameterized SQL prevents query injection.
- Secret, binary and oversized files are not loaded for semantic analysis.
- WAL, foreign keys, busy timeouts and short transactions support concurrent agents.
- Current source always outranks memory.

Read [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) for the threat model.

## Demo and development

The acceptance example is in `examples/demo-project/`. Try:

```bash
repo-brain --root examples/demo-project init
repo-brain --root examples/demo-project context "change password reset token expiration and update its email flow"
```

Run the test and build checks:

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests
python -m build
```

More detail is available in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DATABASE.md](docs/DATABASE.md), [docs/MCP.md](docs/MCP.md), [docs/CODEX.md](docs/CODEX.md), [docs/CLAUDE.md](docs/CLAUDE.md) and [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).
