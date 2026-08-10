# Architecture

Repo Brain has one service layer shared by CLI, MCP, hooks and the local UI. The scanner inventories files, hashes content, detects secrets/binaries/large files, extracts conservative symbols and creates static dependency edges. Agent analyses are stored separately and retain history.

The retrieval path is progressive: status → scan → context ranking → symbols/dependencies → current source read. A changed source hash marks an analysis stale; dependents are warnings rather than a project-wide invalidation.

Git worktrees resolve `git rev-parse --git-common-dir`, so all worktrees share one memory database. SQLite uses WAL, foreign keys and busy timeouts.

