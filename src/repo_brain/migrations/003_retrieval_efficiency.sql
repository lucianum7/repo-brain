-- Repo Brain schema migration 003: local retrieval efficiency telemetry.
-- Only aggregate metadata is stored; task text and source content are not stored.
CREATE TABLE IF NOT EXISTS retrieval_runs (
  id INTEGER PRIMARY KEY,
  repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
  task_hash TEXT NOT NULL,
  task_length INTEGER NOT NULL DEFAULT 0,
  directory TEXT NOT NULL DEFAULT '.',
  requested_limit INTEGER NOT NULL,
  token_budget INTEGER NOT NULL,
  candidate_count INTEGER NOT NULL DEFAULT 0,
  result_count INTEGER NOT NULL DEFAULT 0,
  candidate_tokens INTEGER NOT NULL DEFAULT 0,
  estimated_tokens INTEGER NOT NULL DEFAULT 0,
  saved_tokens INTEGER NOT NULL DEFAULT 0,
  elapsed_ms REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_retrieval_runs_repo_time ON retrieval_runs(repository_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retrieval_runs_directory ON retrieval_runs(repository_id, directory, created_at DESC);
