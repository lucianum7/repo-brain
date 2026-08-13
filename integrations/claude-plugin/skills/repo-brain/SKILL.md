---
name: repo-brain
description: Use Repo Brain to locate current repository code, check stale memory, log reads, and refresh memory after edits.
---

When tuning retrieval, review MCP `brain_efficiency` and record the observed token/time tradeoff in the task decision log.

Use the canonical workflow in `skills/repo-brain/SKILL.md`: scan, choose a directory partition, request compact context, read current source, plan, change, test, scan, and update file/directory analysis. Prefer MCP `brain_read_file` and pass `directory` plus a result `limit` to `brain_context`; manual token caps are not part of the interface. Never treat stale memory as truth or mix unrelated directory partitions.
