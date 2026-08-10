# Database

The SQLite database is the structured source of memory. Core tables include `repositories`, `files`, `file_analyses`, `analysis_history`, `symbols`, `dependencies`, `modules`, `sessions`, `reads`, `changes`, `decisions`, `plans`, `observations`, `tags`, and `bootstrap_queue`. A `schema_migrations` table tracks migration version 1. FTS5 is optional; search falls back to deterministic local ranking.

File hashes connect every analysis and observation to the source that supported it. Historical analyses are append-only; current state is fresh only when its hash equals the file hash.

