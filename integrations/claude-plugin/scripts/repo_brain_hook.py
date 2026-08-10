from __future__ import annotations

import json
import os
import subprocess
import sys


def main() -> None:
    event = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    path = payload.get("file_path") or payload.get("path") or payload.get("tool_input", {}).get("file_path")
    if not path:
        return
    # Hooks are best-effort and never print source content or secrets.
    command = ["repo-brain", "scan"]
    if event == "read":
        command = ["repo-brain", "read", path, "--purpose", "claude-hook"]
    try:
        subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={**os.environ, "REPO_BRAIN_AGENT": "claude"})
    except OSError:
        return


if __name__ == "__main__":
    main()

