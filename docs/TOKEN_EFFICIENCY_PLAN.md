# Plano de eficiência de tokens e tempo

## Objetivo

Reduzir o contexto enviado ao agente sem perder evidência e registrar o custo aproximado de cada recuperação. O sistema não impõe um orçamento de tokens: ele entrega um conjunto compacto limitado por relevância e quantidade de resultados, enquanto mede o tamanho aproximado para comparação.

## Princípios

1. **Diretório antes de arquivo.** Escolha a menor partição relevante antes de buscar contexto.
2. **Contexto compacto automático.** Entregue caminhos, estados, resumos curtos, símbolos limitados e uma ordem de leitura.
3. **Fonte atual acima da memória.** `stale` e `needs_review` sempre exigem releitura.
4. **Métricas sem conteúdo.** Registre hash da tarefa, tamanho, contagens, tokens aproximados e duração; nunca grave a tarefa inteira, código-fonte ou raciocínio privado.
5. **Melhoria baseada em dados.** Ajuste o limite de resultados e o ranking com base em métricas, sem bloquear a recuperação por um orçamento de tokens.

## Métricas registradas

Cada chamada de `context` cria uma linha em `retrieval_runs`:

| Métrica | Significado |
| --- | --- |
| `candidate_tokens` | Estimativa dos candidatos ranqueados antes da compactação. |
| `estimated_tokens` | Estimativa do contexto compacto realmente entregue. |
| `compacted_tokens` | Diferença aproximada removida ao limitar responsabilidades e símbolos. |
| `candidate_count` / `result_count` | Quantidade antes/depois da seleção por relevância. |
| `requested_limit` | Quantidade máxima de resultados solicitada. |
| `elapsed_ms` | Tempo local de busca, compactação e registro. |
| `directory` | Escopo usado na consulta. |
| `task_hash` / `task_length` | Identificação não reversível e tamanho; o texto não é salvo. |

As estimativas usam o tamanho serializado dividido por quatro, uma aproximação consistente para comparar consultas. Elas não são uma fatura do modelo.

## Metas operacionais

- Contexto compacto por diretório e limite de resultados adequado à tarefa.
- Redução mensurável por compactação de campos, sem ocultar resultados por um limite artificial de tokens.
- Tempo local médio abaixo de 250 ms em repositórios pequenos/médios; investigar p95 acima de 1 s.
- Zero edição baseada em resultado `stale` sem releitura registrada.
- Uma consulta delimitada por diretório antes de uma busca global.

## Fluxo recomendado

```text
status → scan → directories → context --directory --limit
       → read atual → editar/testar → scan → analyze → efficiency
```

Exemplo:

```bash
repo-brain directories --json
repo-brain context "alterar expiração do token" --directory src/auth --limit 8 --json
repo-brain read src/auth/password_reset.py
repo-brain scan
repo-brain efficiency --directory src/auth --json
```

Use o relatório geral para acompanhar tendência:

```bash
repo-brain efficiency --limit 100 --json
```

O mesmo relatório está disponível no MCP como `brain_efficiency` e na interface local em `/api/efficiency`.

## Fases de implementação

### Fase 0 — linha de base

Executar pelo menos 20 consultas representativas, registrar `repo-brain efficiency` e anotar tarefas que precisaram de busca global, releitura ou repetição.

### Fase 1 — escopo e compactação (implementada)

Partições por diretório, `--directory`, limite de resultados, grupos, `read_order` e avisos de obsolescência. A compactação automática reduz detalhes repetidos sem impor um bloqueio por tokens.

### Fase 2 — telemetria local (implementada)

Migration 003 registrou métricas iniciais; migration 004 remove o campo de controle legado. `context` registra tokens aproximados, candidatos, compactação e duração; CLI, MCP, UI, `status`, `INDEX.md` e exportação disponibilizam os resultados.

### Fase 3 — ajuste orientado por dados

Revisar semanalmente as médias por diretório. Ajustar `max_context`, ranking, quantidade de símbolos e responsabilidades quando houver contexto insuficiente, resultados irrelevantes ou repetição de buscas.

### Fase 4 — otimizações futuras

- Cache de resultados por `task_hash`, escopo e fingerprint do índice, com invalidação no `scan`.
- Pré-resumos por diretório somente quando a cobertura semântica estiver fresca.
- Paginação de símbolos e dependências em tarefas grandes.
- Benchmark automatizado com consultas fixas, comparando tokens, tempo e cobertura.

Embeddings, chamadas de rede e armazenamento de prompts não fazem parte do caminho padrão: só devem ser considerados se a medição local mostrar necessidade clara.

## Critérios de aceite

Uma melhoria de eficiência está pronta quando:

- `pytest`, Ruff e build passam;
- `repo-brain efficiency --json` mostra métricas após uma consulta;
- nenhuma tarefa ou fonte é persistida na tabela de métricas;
- o relatório identifica escopo, limite de resultados, tokens estimados, compactação e tempo;
- a documentação explica que não existe controle de orçamento de tokens;
- a mudança registra data, hipótese, métrica observada e decisão de manter ou reverter.

## Registro de decisões

Para cada ajuste futuro, acrescente uma entrada em `decisions` ou no changelog com este formato:

```text
Data: AAAA-MM-DD
Hipótese: limitar por diretório e compactar símbolos reduz tokens sem perder arquivos relevantes.
Mudança: ranking/limit/compactação ajustados.
Medição: média antes/depois, compacted_tokens, elapsed_ms e quantidade de releituras.
Decisão: manter, ajustar ou reverter; motivo baseado nos dados.
```

Esse registro evita otimizações intuitivas que economizam tokens mas aumentam retrabalho, tempo ou risco de edição incorreta.
