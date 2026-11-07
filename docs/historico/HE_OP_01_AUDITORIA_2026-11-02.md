# HE-OP-01 — auditoria R1/R2 e inspeção somente-leitura

Data local: 02/11/2026 (America/Sao_Paulo). Fonte normativa: [SPEC canônica](HARNESS_SPEC_CANONICA_USO_DIARIO_E_BENCHMARK_V1.md), §§0, 4, 5, 9–11. Escopo executado: somente HE-OP-01. Nenhum outro release foi implementado.

## Reconciliação autorizada e aceite HE-OP-01

O usuário esclareceu a origem documental dos quatro commits e autorizou expressamente sincronizar, commitar e publicar HE-OP-01 na mesma branch/PR. O bloqueio histórico abaixo foi resolvido por fast-forward de `b02765b` para `52f03373a6766ae3c3848ca023804941744183cc`, sem conflito e sem stash/rebase. Nenhuma branch, worktree ou PR adicional foi criado.

Antes da sincronização, os quatro arquivos locais foram copiados para `.poc/he-op-01-backup-20261103T013750Z`, com `manifest.json` contendo HEAD e hashes SHA-256, mais `tracked.patch` binário. Todos os hashes das cópias foram verificados; depois do fast-forward, os quatro arquivos da worktree continuaram idênticos byte a byte ao backup. Para recuperação, copiar os quatro caminhos relacionados no manifesto desse diretório; o backup inclui os dois arquivos originalmente não rastreados e a auditoria original completa.

A SPEC atualizada foi relida. Única incompatibilidade concreta corrigida: aceitar `--repo .` (ou outro relativo explícito), convertendo-o em absoluto sem resolver links, mantendo a rejeição de `..`, symlinks e junctions. Acrescentado teste de subprocesso para os dois comandos com `--repo .`, incluindo ausência de mudanças na árvore. Não houve reimplementação do lifecycle nem instalação de `setup-harness`. `git diff --exit-code origin/codex/he-jev-007a -- AGENTS.md CLAUDE.md docs/HARNESS_SPEC_CANONICA_USO_DIARIO_E_BENCHMARK_V1.md` retornou 0 após sincronizar: as decisões documentais remotas foram preservadas.

Validação após reconciliação (Windows / Python 3.12.10):

| Comando | Resultado |
| --- | --- |
| `python -W error -m unittest discover -s tests -p test_project_inspection.py -v` | 13 testes; OK, sem skips; 1,185 s |
| `python -W error -m unittest discover -s tests -p test_harnessctl.py -v` | 14 testes legados; OK, sem skips; 6,262 s |
| `python -W error -m unittest discover -s tests -v` com `JEV_REAL_INTEGRATION=0` | 130 testes; OK, 2 skips opt-in; 128 passaram; 12,695 s |
| `python -m py_compile scripts/harnessctl.py tests/test_project_inspection.py` | código 0 |
| `git diff --check` | código 0 |

Log local: `.poc/he-op-01-reconciled-offline.log`. Os dois skips são integração de pacote upstream e integração nativa MXC, não executadas localmente. **Aceite HE-OP-01: PASS offline** — inspeção/plano somente-leitura, caminhos/conflitos/bloqueios visíveis, sem leitura de secrets, sem escrita de projeto, comandos anteriores preservados. Identidade Git continua sendo check estrutural, não validação completa; isso permanece explícito na saída e nos limites abaixo. CI do commit publicado e igualdade HEAD/remoto/PR devem ser verificados pelo SHA após o push e reportados na entrega final, sem atribuir o CI dos commits documentais ao código novo.

Primeira publicação: `197a2bad839d330fd701faaada43cef1e6c173de`. O [CI Linux](https://github.com/Williamitiro/harness-engineering-platform/actions/runs/41561200670) detectou uma falha real de portabilidade no teste existente `test_file_in_parent_path_blocks`: ao encontrar `.agents` como arquivo, `lstat` de um filho lança `NotADirectoryError` no Linux. O código bloqueava como `BLOCKED_PATH`, em vez da colisão prevista. Correção mínima: tratar `NotADirectoryError` junto com caminho inexistente na inspeção dos filhos, mantendo a inspeção do ancestral e o bloqueio `BLOCKED_COLLISION`. Não se alterou ou enfraqueceu o teste. Nova validação Windows: 13 testes dirigidos em 1,276 s, 14 legados em 6,296 s, suíte 130 em 13,737 s (OK, 2 skips), compilação e diff check aprovados. Log: `.poc/he-op-01-portable-offline.log`. A correção é publicada em commit adicional, sem amend/force-push; CI Linux final é conferido na entrega.

## Registro histórico do bloqueio anterior (resolvido)

**Encerramento anterior BLOCKED por concorrência remota:** na conferência final da primeira execução, `git ls-remote` revelou avanço da branch para `52f03373a6766ae3c3848ca023804941744183cc`; após fetch, `HEAD...origin/codex/he-jev-007a` retornou `0 4`. Naquele momento, o PR #4 apontava ao mesmo novo SHA, continuava Draft e tinha CI verde para os commits remotos, não para esta implementação. HEAD local permanecia `b02765b6fc1fdd5ed0a0fc50dbf4fd085a3c1f9b`. Não houve commit, rebase, merge ou push naquela execução. Trabalho preservado na worktree até a coordenação expressamente autorizada acima.

Os quatro commits concorrentes são `71b9d79`, `9d6894a`, `8d405e6` e `52f0337`, alterando somente `AGENTS.md`, `CLAUDE.md` e a SPEC. A leitura do diff remoto mostrou novo gate R1 de bootstrap pessoal `setup-harness` e HE-OP-02B; ambos permanecem PENDENTES e não foram implementados. O novo exemplo `--repo .` também precisa ser reconciliado com o contrato local de caminho absoluto antes de publicação. A auditoria abaixo refere-se à SPEC/HEAD de entrada; os testes certificam apenas a worktree local anterior à integração desses quatro commits. Apenas este registro de bloqueio foi acrescentado após a detecção; desenvolvimento interrompido conforme AGENTS e SPEC §11.

## Identidade e evidências de entrada

- Repositório/worktree: `C:/dev/harness-engineering` (única worktree).
- Branch: `codex/he-jev-007a`, upstream `origin/codex/he-jev-007a`.
- HEAD inicial: `b02765b6fc1fdd5ed0a0fc50dbf4fd085a3c1f9b`.
- `git status --short`: vazio antes de editar; `git fetch origin` seguido de `git rev-list --left-right --count HEAD...origin/codex/he-jev-007a`: `0 0`.
- Remoto: `https://github.com/Williamitiro/harness-engineering-platform.git`.
- [PR #4](https://github.com/Williamitiro/harness-engineering-platform/pull/4): único PR aberto dessa branch; Draft, base `main`, head igual ao HEAD inicial. Dois checks `offline` SUCCESS nesse SHA. Isso não certifica a mudança local deste relatório.
- Manual, protocolo, dossiê histórico, templates, manifesto, CLI, runner, avaliador, testes e workflow foram inspecionados antes da implementação. A SPEC prevalece sobre afirmações históricas do dossiê e do README.

## Auditoria dos critérios dos releases

| Critério | Estado observado após HE-OP-01 | Evidência / lacuna |
| --- | --- | --- |
| R1: doctor/plan por repositório, somente-leitura | IMPLEMENTADO / TESTADO OFFLINE | `scripts/harnessctl.py`; 13 testes novos, inclusive fixture Git externa e caminho relativo |
| R1: attach/verify/remove por projeto, ownership e rollback exato | PENDENTE — HE-OP-02 | Ciclo legado `plan/install/verify/remove` existe, porém restrito a `.poc/` sem checkout Git; não equivale ao onboarding de projeto |
| R1: bootstrap pessoal `setup-harness` e teste ponta a ponta | PENDENTE — HE-OP-02B | Decisão da SPEC §2.1 preservada; nenhuma instalação ou implementação feita neste escopo |
| R1: preservar arquivos existentes, colisões e paths | PARCIAL | Inspeção bloqueia colisões, links e junctions sem ler conteúdo; escrita/rollback por projeto ainda não implementados |
| R1: Codex em projeto opt-in, descoberta/invocação/comportamento e patch com QA externo | NOT_RUN — HE-OP-03 | Nenhum projeto consumidor escolhido/autorizado; presença de skills não prova execução. Evidência A/C histórica contaminada não satisfaz o gate |
| R2: interface bench plan/run/report e corpus de programação pré-registrado | PENDENTE — HE-BENCH-01 | `harness_eval.py` já possui condições A/B/C, setup `.poc`, análise de trajetória e oráculo; `benchmarks/tasks/ratelimit` é base de reuso, não corpus A/B concluído |
| R2: pelo menos dois casos reais pareados, mesmo estado inicial, oráculo independente e isolamento | NOT_RUN | Runner bloqueia live por padrão; campo `isolation_verified` continua false. Dry-run/CI e piloto JEV não comprovam contenção ou ganho de programação |
| R2: telemetria, tentativas, custo/cota e conclusões auditáveis | PARCIAL — HE-BENCH-02 | Avaliador possui tempo/tokens/custo nullable; `paired_executor.py` diferencia subtotal e total incompleto para classificação. Falta relatório de programação com contrato financeiro completo e quota separada |
| R2-H: decisão Harbor USE/DEFER com prova delimitada | NOT_RUN — HE-BENCH-H | Há referência documental; nenhuma decisão de execução demonstrada. Nenhuma instalação ou spike foi executado neste turno |
| R2: ensaio A/B e relatório de resultado | NOT_RUN — HE-BENCH-03 | Não houve benchmark nem chamada de modelo neste turno |

**Gate R1: PENDENTE. Gate R2: PENDENTE. Harness V1 não está pronto.** O piloto A×J de três classificações não substitui o benchmark de engenharia. Afirmações históricas de homologação no corpo antigo do README não foram usadas como prova.

## Contrato entregue e uso

```powershell
python scripts/harnessctl.py project-doctor --repo C:/dev/harness-engineering --client codex
python scripts/harnessctl.py project-plan --repo C:/dev/harness-engineering --client codex
```

Ambos retornaram JSON com `BLOCKED_COLLISION` e código 2 devido ao `AGENTS.md` existente. Ele foi preservado. O plano lista esse bloqueio e três outros arquivos que seriam novos, sem aplicar nenhum deles.

- `--repo` e `--client codex` são obrigatórios; caminho absoluto ou relativo explícito, convertido em absoluto, existente, sem `..`, com marcador `.git` regular ou diretório. Diretórios arbitrários sem marcador são recusados.
- `project-doctor`: compatibilidade **estrutural**, estado `COMPATIBLE_NOT_RUNTIME_VERIFIED` quando livre de bloqueios.
- `project-plan`: mesmos checks, mais SHA ECC e hashes allowlisted de `config/approved_skills.json`; estado `PLANNED_NOT_INSTALLED` quando livre de bloqueios. Propõe `AGENTS.md`, duas skills Codex e `.harness/manifest.json`.
- Contrato reutilizado: `templates/AGENTS.md`; catálogo, hashes, erro e proteção de paths reutilizados do CLI existente. O verificador compartilhado também recusa reparse points/junctions Windows; os 14 testes legados continuam verdes.
- Arquivos, diretórios das skills selecionadas, skill root não vazio, estado legado ou `.harness` preexistentes bloqueiam. Diretórios `.agents/skills` vazios são compatíveis. `CLAUDE.md` existente fica preservado e fora do plano Codex.
- Sem conteúdo de arquivos do destino, Git config, ambiente, credenciais ou corpo de skills do destino; apenas metadados dos caminhos fixos e detecção de skill root não vazio. Nenhum subprocesso, Git, cliente ou hook é invocado pela inspeção.
- Sem flags de escrita: `--apply`, `--source`, `--target` e cliente Claude são recusados nesses comandos. Os comandos legados mantêm seus argumentos e restrições.
- Bloqueios aparecem no JSON; código 0 significa apenas inspeção/plano estático concluído, código 2 significa bloqueio ou argumento inválido. Não significa autorização para instalar.

Limites explícitos: `.git` é somente marcador estrutural (`GIT_MARKER_ONLY`), inclusive no caso de gitfile de worktree. Não é validação Git completa; um marcador artificial pode satisfazer esse check. Não se resolve gitfile para outro caminho. `source_validation`, descoberta, invocação e execução ficam `NOT_RUN`; runtime fica `NOT_PROBED`, ownership `NOT_CLAIMED`. Não há comparação do conteúdo de instruções ancestrais nem promessa de compatibilidade semântica. Nenhuma cópia ECC é buscada ou validada neste escopo. Uma futura operação de escrita deve revalidar fonte, Git, paths e colisões antes de escrever.

## Testes executados

| Comando | Resultado observado |
| --- | --- |
| `python -W error -m unittest discover -s tests -v` antes da mudança (`JEV_REAL_INTEGRATION=0`) | 117 testes em 9,511 s; OK, 2 skips |
| `python -m unittest discover -s tests -p test_project_inspection.py -v` antes da implementação | RED: comandos/função inexistentes |
| `python -W error -m unittest discover -s tests -p test_project_inspection.py -v` após implementação | 12 testes em 0,903 s; OK, sem skips; symlinks e junction Windows executados |
| `python -W error -m unittest discover -s tests -p test_harnessctl.py -v` | 14 testes em 5,003 s; OK |
| `python -W error -m unittest discover -s tests -v` após mudança (`JEV_REAL_INTEGRATION=0`) | 129 testes em 8,863 s; OK, 2 skips (127 executados com sucesso) |
| `python -m py_compile scripts/harnessctl.py tests/test_project_inspection.py` | código 0 |
| `git diff --check` | código 0 |

Os resultados desta seção são da primeira execução, antes da reconciliação. Ambiente: Windows, Python 3.12.10. Log bruto offline: `.poc/he-op-01-offline.log` (ignorado; não depende de publicação). Skips: integração de pacote upstream opt-in e integração nativa MXC opt-in; ambos deliberadamente fora da suíte offline. A validação atual está na seção de reconciliação acima.

Os testes novos comprovam repetibilidade e árvore de destino inalterada, JSON por subprocesso CLI, preservação de colisões, guarda que falha se qualquer arquivo do destino for aberto ou processo disparado, sentinela de secret ausente da saída, paths inválidos, symlinks e junction real. Não constituem benchmark nem teste de runtime LLM.

## Segurança, métricas, rollback e continuidade

Nenhuma instalação, configuração global, hook persistente, modificação em projeto consumidor, merge de PR, deploy, chamada paga ou benchmark. Na primeira execução também não houve push; nesta retomada o push de HE-OP-01 foi expressamente autorizado. Nenhuma métrica de modelo foi coletada: tokens, custo total e quota permanecem desconhecidos/não aplicáveis; não inferir economia. Tempos acima são apenas duração de testes locais.

Arquivos alterados: `scripts/harnessctl.py`, `tests/test_project_inspection.py`, `README.md` e este relatório. A SPEC e o dossiê histórico foram preservados. Rollback do produto: nenhum arquivo instalado a remover; para desfazer código versionado, reverter somente o commit HE-OP-01 na mesma branch, mediante autorização, sem reset ou limpeza destrutiva.

Próximo backlog: **HE-OP-02**, sem execução automática. Depois HE-OP-02B e HE-OP-03, seguidos de HE-BENCH-01/02/H/03 para concluir R2. Publicação do checkpoint autorizada explicitamente pelo usuário conforme AGENTS/SPEC §7; o PR #4 permanece Draft, sem criar PR duplicado. O SHA final, CI e estado do checkpoint constam da entrega do executor.
