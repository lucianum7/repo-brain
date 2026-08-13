# Development

The project uses Python standard library modules for portability. `Brain` is the shared application service; keep CLI, MCP and UI as thin adapters. Add schema changes as numbered migrations and preserve source-hash semantics. The SQL files under `src/repo_brain/migrations/` are the only schema source; the database loader validates contiguous numbering and records immutable checksums in `migration_audit`. Efficiency changes must record a hypothesis and use `retrieval_runs` without persisting prompts or source content. Run `pytest`, `ruff check src tests`, and `python -m build`.

The optimization plan and metric definitions live in [TOKEN_EFFICIENCY_PLAN.md](TOKEN_EFFICIENCY_PLAN.md). After changing retrieval, run representative contexts and compare `repo-brain efficiency --json` before and after.

For directory organization and SQL/schema updates, follow [DIRECTORY_IMPROVEMENT_PLAN.md](DIRECTORY_IMPROVEMENT_PLAN.md). File edits are recorded by `scan` in `changes`; schema edits require a new numbered migration and must never rewrite an applied migration. Before publishing, run `repo-brain db check --json`, the clean/upgrade/idempotence migration tests, `pytest`, Ruff and the package build.

