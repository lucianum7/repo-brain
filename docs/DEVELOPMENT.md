# Development

The project uses Python standard library modules for portability. `Brain` is the shared application service; keep CLI, MCP and UI as thin adapters. Add schema changes as numbered migrations and preserve source-hash semantics. Run `pytest`, `ruff check src tests`, and `python -m build`.

