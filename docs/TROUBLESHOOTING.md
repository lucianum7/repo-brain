# Troubleshooting

- Run `repo-brain doctor` for Python, database, WAL, FTS and configuration checks.
- Run `repo-brain init` if the database was removed.
- Use `repo-brain db path` when worktrees appear to disagree.
- If a file is stale, read it and run `repo-brain analyze FILE --summary "..."`.
- If FTS5 is unavailable, the built-in fallback search remains functional.

