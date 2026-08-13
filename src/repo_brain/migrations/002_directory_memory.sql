-- Repo Brain schema migration 002: directory-scoped memory.
CREATE TABLE IF NOT EXISTS directories (
  id INTEGER PRIMARY KEY,
  repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  path TEXT NOT NULL,
  name TEXT NOT NULL,
  parent_path TEXT,
  depth INTEGER NOT NULL DEFAULT 0,
  file_count INTEGER NOT NULL DEFAULT 0,
  active_file_count INTEGER NOT NULL DEFAULT 0,
  fresh_count INTEGER NOT NULL DEFAULT 0,
  stale_count INTEGER NOT NULL DEFAULT 0,
  needs_review_count INTEGER NOT NULL DEFAULT 0,
  pending_count INTEGER NOT NULL DEFAULT 0,
  summary TEXT,
  purpose TEXT,
  responsibilities TEXT NOT NULL DEFAULT '[]',
  entrypoints TEXT NOT NULL DEFAULT '[]',
  risks TEXT NOT NULL DEFAULT '[]',
  architecture_notes TEXT NOT NULL DEFAULT '[]',
  confidence REAL NOT NULL DEFAULT 0.4,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(repository_id, path)
);
CREATE INDEX IF NOT EXISTS idx_directories_parent ON directories(repository_id, parent_path);
CREATE TABLE IF NOT EXISTS directory_analyses (
  id INTEGER PRIMARY KEY,
  repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  directory_id INTEGER NOT NULL REFERENCES directories(id) ON DELETE CASCADE,
  source_fingerprint TEXT NOT NULL,
  summary TEXT NOT NULL,
  responsibilities TEXT NOT NULL DEFAULT '[]',
  entrypoints TEXT NOT NULL DEFAULT '[]',
  risks TEXT NOT NULL DEFAULT '[]',
  architecture_notes TEXT NOT NULL DEFAULT '[]',
  confidence REAL NOT NULL DEFAULT 0.5,
  analyzer TEXT NOT NULL DEFAULT 'agent',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_directory_analyses_dir ON directory_analyses(directory_id, updated_at DESC);
ALTER TABLE files ADD COLUMN directory_id INTEGER REFERENCES directories(id);
