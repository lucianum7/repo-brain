# Claude Code integration

The distributable plugin is under `integrations/claude-plugin/`. It contains a skill, hooks, plugin manifest and `.mcp.json`. Hooks are best-effort: failures are swallowed and they never send source content to Repo Brain. Install the project skill with `repo-brain install --claude`.

