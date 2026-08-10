# Repo Brain

Memória persistente de repositório para agentes de programação — Codex, Claude Code e MCP.

O Repo Brain cria um mapa local e auditável em SQLite: localização de arquivos, hashes, símbolos, dependências, análises, leituras, decisões, planos e alterações. A busca contextual indica por onde começar e destaca memória obsoleta.

> A memória orienta a descoberta. O código-fonte atual determina a verdade.

## Início rápido

```bash
pip install .
cd meu-projeto
repo-brain install --all
repo-brain init
repo-brain context "alterar expiração do token de recuperação de senha"
repo-brain read src/auth/password_reset.py
repo-brain ui
```

O banco é compartilhado entre worktrees Git em `<git-common-dir>/repo-brain/brain.db`; projetos sem Git usam `.repo-brain/brain.db`. Confirme com `repo-brain db path`.

O fluxo é offline, sem API ou telemetria. Use `--json` nos comandos para integração com agentes.

Veja a documentação em `docs/` e a skill em `skills/repo-brain/SKILL.md`.

