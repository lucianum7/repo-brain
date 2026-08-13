-- Repo Brain schema migration 005: immutable migration source audit.
CREATE TABLE IF NOT EXISTS migration_audit (
  version INTEGER PRIMARY KEY REFERENCES schema_migrations(version) ON DELETE CASCADE,
  name TEXT NOT NULL,
  checksum TEXT NOT NULL,
  source_path TEXT NOT NULL,
  verified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_migration_audit_checksum ON migration_audit(checksum);
