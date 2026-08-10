# Repo Brain

Memória persistente de repositórios para agentes de programação.

[English](README.md) · [Português do Brasil](README.pt-BR.md) · [简体中文](README.zh-CN.md)

O Repo Brain é uma habilidade, CLI, memória SQLite e servidor MCP offline-first. Ele ajuda o agente a encontrar rapidamente onde trabalhar sem reler o repositório inteiro a cada tarefa.

> A memória orienta a descoberta. O código-fonte atual determina a verdade.

## O que a habilidade faz

A skill `repo-brain` ensina um fluxo repetível e baseado em evidências:

1. Verificar a saúde do repositório e executar um scan incremental.
2. Pesquisar a tarefa na memória e ranquear arquivos, símbolos, testes e dependências.
3. Ler o código atual por uma operação auditável antes de editar.
4. Verificar análises obsoletas, dependentes diretos e decisões arquiteturais.
5. Criar um plano persistente para feature, refatoração, migration, alteração de segurança ou bug entre módulos.
6. Fazer a alteração, executar os testes e escanear novamente.
7. Atualizar a análise usando o novo hash e encerrar a sessão.

A habilidade nunca autoriza editar apenas com base em um resumo antigo. Quando o hash de um arquivo muda, sua análise vira `stale`; dependentes diretos podem virar `needs_review`. O agente precisa reler o arquivo atual antes de uma alteração crítica.

## Memória separada por diretório e economia de tokens

A memória é particionada pelo diretório normalizado do repositório. Cada arquivo indexado pertence ao seu diretório imediato, e cada diretório também guarda contagens da subárvore, resumo compacto, responsabilidades, pontos de entrada, riscos e estado de atualização. A análise do diretório é uma camada curta de roteamento; ela nunca substitui a leitura do código-fonte atual.

Comece pelo mapa de diretórios e mantenha a recuperação delimitada:

```bash
repo-brain directories --json
repo-brain directory src/auth --json
repo-brain context "rotacionar tokens de recuperação" --directory src/auth --limit 8 --token-budget 2200 --json
repo-brain analyze-directory src/auth --json-file auth-directory.json
```

`context` retorna `groups` separados por diretório, resumos e estados dos diretórios, uma `read_order` intencional, avisos de dados obsoletos e `estimated_tokens`. O orçamento é aproximado e vem de `[ranking] token_budget` em `.repo-brain/config.toml` (3.000 tokens por padrão). Prefira uma pasta por consulta, limite pequeno e orçamento adequado à tarefa; assim o agente recebe um handoff de descoberta pronto, sem resumos irrelevantes. Use os caminhos retornados com `repo-brain read` e confirme os hashes atuais antes de editar.

A interface local respeita a mesma separação: a barra lateral e o seletor de escopo exibem um diretório por vez (incluindo descendentes). Uma busca em todos os diretórios continua agrupada visualmente, sem misturar arquivos em uma lista única.

## Requisitos

- Python 3.11 ou superior.
- SQLite 3 com suporte a WAL, incluído no Python.
- Git é opcional. Repositórios Git compartilham o banco entre worktrees; projetos sem Git usam `.repo-brain/`.
- Nenhuma chave de API, conta cloud, banco externo, modelo ou internet é necessária durante o uso normal.
- FTS5 é usado quando disponível. Um fallback determinístico mantém a busca funcional sem FTS5.

## Instalação

A partir do pacote publicado:

```bash
python -m pip install repo-brain
```

Durante o desenvolvimento deste repositório:

```bash
python -m pip install -e ".[dev]"
```

Depois instale as integrações no projeto que você quer memorizar:

```bash
cd /caminho/do/seu-projeto
repo-brain install --all
repo-brain init
```

`install --codex` cria `.agents/skills/repo-brain/SKILL.md` e um bloco gerenciado em `AGENTS.md`. `install --claude` cria a skill Claude e um bloco gerenciado em `CLAUDE.md`. O conteúdo existente do usuário é preservado. Use `--dry-run` para visualizar as mudanças.

## Primeiro uso e localização do banco

`repo-brain init` cria a configuração, aplica migrations, inventaria os arquivos, calcula hashes, extrai símbolos/dependências, preenche a fila de bootstrap e gera `.repo-brain/INDEX.md`.

Para ver exatamente qual banco está sendo usado:

```bash
repo-brain db path
```

Em um repositório Git, o padrão é `<git-common-dir>/repo-brain/brain.db`, permitindo que worktrees compartilhem a memória. Em um projeto sem Git, o banco fica em `.repo-brain/brain.db`. O banco e seus arquivos WAL não devem ser versionados; o `INDEX.md` é um dashboard humano compacto e pode ser regenerado.

## Fluxo diário do agente

```text
status → scan → context → ler o código atual → plano (se necessário)
      → editar → testes → scan → atualizar análise → index/sessão
```

Comandos típicos:

```bash
repo-brain status
repo-brain scan
repo-brain context "alterar expiração do token de recuperação e o fluxo de e-mail"
repo-brain read src/auth/password_reset.py
repo-brain impact src/auth/token.py --depth 3
repo-brain analyze src/auth/password_reset.py --json-file analysis.json
repo-brain scan
```

Use `--json` em status, context, search, coverage, reads, changes, grafo, bootstrap e outros comandos consumidos por agentes ou scripts.

## O que é armazenado

O SQLite armazena identidade do repositório, caminhos relativos/normalizados, hashes, linguagem/categoria, contagem de linhas, estados de análise, partições de diretórios, análises de diretórios, símbolos, dependências, módulos, sessões, leituras, alterações, planos, decisões, observações e tags. As análises de arquivo são versionadas em `analysis_history`; as de diretório ficam em `directory_analyses` com fingerprint da fonte.

Por padrão, o Repo Brain não armazena cópias completas dos arquivos. Arquivos que parecem secretos (`.env`, chaves, certificados, credenciais e padrões semelhantes) não passam por análise semântica. Hooks de leitura/escrita registram caminhos, hashes, ferramentas, sessões e horários — nunca o conteúdo bruto de uma escrita.

## Comandos principais

| Área | Comandos |
| --- | --- |
| Configuração | `init`, `install`, `uninstall`, `migrate`, `doctor` |
| Saúde | `status`, `coverage`, `stale`, `index`, `db path`, `db check`, `db vacuum` |
| Descoberta | `search`, `context`, `directories`, `directory`, `file`, `symbols`, `modules` |
| Grafo | `deps FILE`, `dependents FILE`, `impact FILE --depth N` |
| Auditoria | `read FILE`, `reads`, `changes`, `history` |
| Memória do agente | `session`, `analyze`, `analyze-directory`, `plan`, `decision` |
| Bootstrap | `bootstrap status`, `claim`, `complete`, `fail` |
| Portabilidade | `export`, `import` |
| Integrações | `mcp serve`, `ui`, `integrate codex`, `integrate claude` |

Use `repo-brain COMMAND --help` para os argumentos exatos.

## Modo bootstrap

Projetos grandes podem ser analisados cooperativamente:

```bash
repo-brain bootstrap claim --limit 10
repo-brain read caminho/do/arquivo.py --purpose bootstrap
repo-brain analyze caminho/do/arquivo.py --json-file analysis.json
repo-brain bootstrap complete caminho/do/arquivo.py
```

As claims têm lease; dois agentes não recebem o mesmo item ativo. Um worker que falhar libera o item após o vencimento do lease.

## Análises e evidências

Um agente pode salvar uma análise factual e concisa:

```json
{
  "summary": "Cria e rotaciona tokens de recuperação de senha.",
  "responsibilities": ["validar expiração", "evitar replay"],
  "security_notes": ["invalidar o token anterior após a rotação"],
  "risks": ["replay se a rotação não for atômica"],
  "tags": ["auth", "security"],
  "confidence": 0.9
}
```

Observações importantes devem incluir arquivo, hash, intervalo de linhas e confiança. Não armazene raciocínio privado do modelo nem segredos.

## Servidor MCP

Inicie o servidor local por stdio:

```bash
repo-brain mcp serve
```

Ele oferece ferramentas para status, scan, context, busca, leitura, símbolos, dependências, impacto, sessões, análises, planos, decisões, bootstrap e atualização do índice. `brain_read_file` valida o caminho, lê um intervalo, registra a leitura e devolve hash e estado atuais.

Configure o host MCP para executar `repo-brain` com os argumentos `mcp serve`. O repositório também inclui o manifesto do plugin Claude e um template `.mcp.json`.

## Interface local

A interface local, sem dependência web externa, usa a mesma camada de serviços:

```bash
repo-brain ui --host 127.0.0.1 --port 8765
```

Abra <http://127.0.0.1:8765>. A tela mostra quantidade de arquivos, cobertura semântica, estados fresh/stale e resultados de busca contextual. O servidor fica local, salvo se você escolher outra interface.

## Codex e Claude Code

A skill canônica está em `skills/repo-brain/SKILL.md`. O plugin Claude distribuível fica em `integrations/claude-plugin/`, com skill, configuração de hooks, script seguro e configuração MCP. Os hooks são best-effort: uma falha do Repo Brain nunca deve bloquear a edição do usuário.

## Configuração

`repo-brain init` cria `.repo-brain/config.toml`. Configure inclusões/exclusões, tamanho máximo, extensões permitidas/ignoradas, padrões de segredo, limite de ranking e lease do bootstrap. Mantenha banco, WAL e logs locais fora do controle de versão.

## Exportação e importação

```bash
repo-brain export
repo-brain import .repo-brain/export/snapshot.jsonl
```

Snapshots contêm metadados sanitizados, hashes, análises, relações e decisões — não o código completo. Memória importada continua ligada aos hashes de origem e deve ser tratada como stale quando o código atual divergir.

## Segurança e privacidade

- Offline-first e sem telemetria.
- Validação canônica de caminhos contra traversal e fuga da raiz.
- SQL parametrizado contra injeção.
- Arquivos secretos, binários e grandes não são carregados semanticamente.
- WAL, foreign keys, busy timeout e transações curtas favorecem uso concorrente.
- O código atual sempre tem prioridade sobre a memória.

Leia [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) para o threat model.

## Exemplo e desenvolvimento

O cenário de aceitação fica em `examples/demo-project/`:

```bash
repo-brain --root examples/demo-project init
repo-brain --root examples/demo-project context "alterar expiração do token e o fluxo de e-mail de recuperação"
```

Valide testes e build:

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests
python -m build
```

Mais detalhes estão em [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DATABASE.md](docs/DATABASE.md), [docs/MCP.md](docs/MCP.md), [docs/CODEX.md](docs/CODEX.md), [docs/CLAUDE.md](docs/CLAUDE.md) e [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Licença

Apache License 2.0. Veja [LICENSE](LICENSE).
