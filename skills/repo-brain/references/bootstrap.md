# Bootstrap reference

`repo-brain init` creates configuration, migrations, inventory, static symbols/dependencies, a persistent queue, and `.repo-brain/INDEX.md`. Agents claim a small batch, read current files, record factual analysis, and complete each claim. A failed worker can leave a lease that expires safely.

