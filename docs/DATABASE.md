# Database

The SQLite database is the structured source of memory. Core tables include `repositories`, `files`, `file_analyses`, `analysis_history`, `directories`, `directory_analyses`, `retrieval_runs`, `symbols`, `dependencies`, `modules`, `sessions`, `reads`, `changes`, `decisions`, `plans`, `observations`, `tags`, `bootstrap_queue`, and `migration_audit`. Numbered SQL files under `src/repo_brain/migrations/` are the single schema source. `schema_migrations` records applied versions and `migration_audit` records the checksum and package path of each source file. The current schema is version 5. FTS5 is optional; search falls back to deterministic local ranking.

File hashes connect every analysis and observation to the source that supported it. Historical analyses are append-only; current state is fresh only when its hash equals the file hash.

`retrieval_runs` stores privacy-preserving efficiency metadata for each `context` call: task hash and length, directory, result limit, candidate/result counts, approximate candidate/selected/compacted tokens and local elapsed milliseconds. It deliberately does not store task text, source text or model reasoning. Use `repo-brain efficiency` to aggregate this table. The active schema has no manual token-cap field; result quantity and directory scope control retrieval size, while compacting is automatic.

Run `repo-brain db check --json` to verify SQLite integrity, pending migrations and source drift. `repo-brain migrate --json` applies missing migrations in order and is safe to repeat. Applied SQL files are immutable: create a new numbered migration for every schema change. Migration 004 rebuilds the legacy retrieval table so existing databases converge on the current compact telemetry columns; migration 005 adds source checksums and audit paths.

