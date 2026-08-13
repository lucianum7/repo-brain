-- Repo Brain schema migration 004: compact retrieval telemetry.
-- Rebuild the legacy table so the active schema has no manual token cap fields.
PRAGMA foreign_keys=OFF;
CREATE TABLE retrieval_runs_compact (
  id INTEGER PRIMARY KEY,
  repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
  task_hash TEXT NOT NULL,
  task_length INTEGER NOT NULL DEFAULT 0,
  directory TEXT NOT NULL DEFAULT '.',
  requested_limit INTEGER NOT NULL,
  candidate_count INTEGER NOT NULL DEFAULT 0,
  result_count INTEGER NOT NULL DEFAULT 0,
  candidate_tokens INTEGER NOT NULL DEFAULT 0,
  estimated_tokens INTEGER NOT NULL DEFAULT 0,
  compacted_tokens INTEGER NOT NULL DEFAULT 0,
  elapsed_ms REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO retrieval_runs_compact
  (id,repository_id,session_id,task_hash,task_length,directory,requested_limit,
   candidate_count,result_count,candidate_tokens,estimated_tokens,compacted_tokens,
   elapsed_ms,created_at)
SELECT id,repository_id,session_id,task_hash,task_length,directory,requested_limit,
       candidate_count,result_count,candidate_tokens,estimated_tokens,
       MAX(0,candidate_tokens-estimated_tokens),elapsed_ms,created_at
FROM retrieval_runs;
DROP TABLE retrieval_runs;
ALTER TABLE retrieval_runs_compact RENAME TO retrieval_runs;
CREATE INDEX idx_retrieval_runs_repo_time ON retrieval_runs(repository_id, created_at DESC);
CREATE INDEX idx_retrieval_runs_directory ON retrieval_runs(repository_id, directory, created_at DESC);
PRAGMA foreign_keys=ON;
