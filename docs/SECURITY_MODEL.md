# Security model

Repo Brain is local-only by default. Secret patterns, binary files and oversized files are not semantically analyzed; path inputs are canonicalized and constrained to the repository root; SQL uses parameters; imports are JSONL-validated; snapshots retain source hashes so mismatches become stale. SQLite locking and WAL reduce concurrent-write corruption. Treat imported memory as untrusted guidance and reread the current source before changes.

