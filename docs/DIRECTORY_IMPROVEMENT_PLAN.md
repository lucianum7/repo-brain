# Plano de melhorias do diretório e governança SQL

## Objetivo

Manter cada tipo de informação no seu diretório e dar ao agente uma trilha verificável para localizar, ler e alterar arquivos. O scanner registra mudanças de arquivos por hash; o banco registra o estado estruturado; migrations SQL versionadas alteram somente o schema. Uma atualização nunca deve inferir SQL a partir de uma mudança de código.

## Organização

```text
repo-brain/
├── src/repo_brain/             # serviço, CLI, MCP e interface local
│   ├── migrations/              # somente SQL numerado e imutável
│   └── templates/               # skill instalada localmente
├── tests/                       # testes unitários e de upgrade do banco
├── docs/                        # arquitetura, banco, planos e decisões
├── integrations/               # adaptadores Codex/Claude
├── skills/                      # skill canônica e referências
├── examples/                    # projeto demonstrativo
└── .repo-brain/                 # estado local ignorado pelo Git
```

## O que acontece depois de uma atualização

1. `repo-brain scan` recalcula hashes, registra cada arquivo alterado em `changes` e marca análises antigas como `stale`/`needs_review`.
2. O agente escolhe uma partição com `repo-brain directories` e usa `context --directory DIR --limit N`; os grupos e a ordem de leitura permanecem separados por diretório.
3. O agente relê arquivos atuais antes de editar. Memória stale nunca é tratada como verdade.
4. Uma alteração de schema cria o próximo SQL numerado em `src/repo_brain/migrations/`; migrations aplicadas nunca são reescritas.
5. `repo-brain migrate` executa os SQL empacotados em ordem, registra a versão em `schema_migrations` e o checksum/caminho em `migration_audit`.
6. `repo-brain db check --json` confirma integridade SQLite, versão, pendências e divergências de checksum.
7. O agente atualiza análise de arquivo/diretório, gera `.repo-brain/INDEX.md`, atualiza changelog/documentação e executa testes.

## Fonte única e compatibilidade

O executor não contém cópias inline do schema. Ele carrega `001_*.sql` até a versão mais recente, exige numeração contínua e falha antes de aplicar qualquer coisa quando encontra migration ausente, duplicada ou fora de ordem. Bancos legados são atualizados incrementalmente; a migration 004 reconstrói a tabela de telemetria antiga para o schema compacto e a 005 registra auditoria de origem.

`migration_audit` permite detectar uma edição posterior de um SQL já aplicado. Em bancos anteriores à auditoria, os checksums são registrados na primeira atualização para estabelecer uma linha de base; depois disso, qualquer divergência bloqueia a migração até que uma nova migration seja criada.

## Checklist de implementação

### Código e banco

- [ ] Executar `repo-brain scan` e selecionar a menor partição relevante.
- [ ] Criar nova migration numerada para qualquer alteração de schema.
- [ ] Testar banco vazio, banco da versão anterior e segunda execução idempotente.
- [ ] Confirmar `repo-brain db check --json` sem divergências.
- [ ] Não colocar prompts, código-fonte ou raciocínio privado na telemetria.

### Documentação e estado

- [ ] Atualizar `docs/DATABASE.md` e `docs/DEVELOPMENT.md` quando o schema mudar.
- [ ] Atualizar os três READMEs, changelog e roadmap quando o comportamento público mudar.
- [ ] Atualizar análise do arquivo e do diretório afetados.
- [ ] Regenerar `.repo-brain/INDEX.md`; não versionar banco, caches ou builds.

### Verificação

```bash
python -m pytest -q
ruff check src tests
python -m build
repo-brain db check --json
```

## Eficiência sem controle manual de tokens

O tamanho do contexto é reduzido por diretório, relevância, quantidade de resultados e compactação automática de símbolos/responsabilidades. Os campos `candidate_tokens`, `estimated_tokens` e `compacted_tokens` existem apenas para medir tendência e tempo; não há um teto manual que possa truncar uma tarefa silenciosamente.

## Critérios de aceite

- Arquivo modificado aparece em `changes` com hashes, agente, motivo e timestamp.
- Schema novo possui SQL numerado, teste de upgrade e entrada em `schema_migrations` após aplicação.
- Banco novo e banco legado produzem o mesmo schema final.
- `migration_audit` detecta edição de migration histórica.
- Interface local, CLI, MCP, skills e READMEs mostram a mesma separação por diretório.
- Testes e build passam sem adicionar artefatos gerados ao Git.
