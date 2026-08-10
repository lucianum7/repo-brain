---
name: repo-brain
description: Use Repo Brain to locate current repository code, consult evidence-backed memory, log reads, detect stale analyses, and refresh memory after changes.
---

# Repo Brain

Run `repo-brain status` and `repo-brain scan` before non-trivial work. Select a directory with `repo-brain directories`, then query compact context with `repo-brain context "<task>" --directory DIR --token-budget 2200 --json`. Read current source with `repo-brain read FILE`, treat stale analyses as mandatory rereads, and preserve the returned read order. After edits, scan, test, and refresh file/directory analysis. Memory guides discovery; current source code determines truth.

