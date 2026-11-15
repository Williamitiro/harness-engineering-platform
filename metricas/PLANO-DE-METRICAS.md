# Plano de métricas — Harness Engineering

**Data:** 15/11/2026 · **HEAD medido:** `8d6a3e2` (`main`, versão instalada `v1.2.0`) · **Evidência agregada:**
[`docs/evidence/METRICAS_BASELINE_2026-11-15.json`](../docs/evidence/METRICAS_BASELINE_2026-11-15.json) ·
**Registro:** [`registro.csv`](registro.csv)

Regra deste plano: número sem dado não existe. Cada valor tem uma marca:
**[medido]** (contado agora em dado existente, com comando), **[estimado com método]** (derivado, com o método
escrito) ou **[não medido]** (`null`). Nível de evidência de tudo aqui: `OPERATIONAL_LOG_ONLY_NOT_A_BENCHMARK`.
O Harness **não afirma** que o kit melhora qualidade, tempo ou custo (SPEC §1, §6): o que estas métricas mostram é
**método** (gates, testes, rastreabilidade), não ganho.

> Repositório **público** (`gh repo view` → `PUBLIC`). Tudo o que entra aqui e em `docs/evidence/` fica público.

---

## 1. Dor, usuário e alternativa atual

| | |
|---|---|
| **Dor** | Programar em 10–20 repositórios com Claude Code e Codex. Sem regras comuns, cada agente improvisa: diz "pronto" sem rodar testes, mexe além do pedido, apaga trabalho alheio, e "funcionou" vira afirmação sem prova (ESTADO §4 lista 13 casos reais: baseline contaminado, `VERIFIED` falso, tokens estimados como medidos, 40+ documentos contraditórios). |
| **Usuário** | William Itiro (operador único), trabalhando com Claude Code e Codex; secundariamente, quem usar agentes de programação em vários repositórios. |
| **O que o sistema faz** | Instala, verifica e remove um kit pequeno de regras (`AGENTS.md`) na máquina e em cada repositório, sem apagar nada alheio; exige status com nível de evidência e suíte offline verde; mede o uso real por logs locais (`daily_report.py`, `quality_baseline.py`). |
| **Alternativa atual** | Copiar à mão `AGENTS.md`/skills entre repositórios (foi o que aconteceu nos 7 PRs de 07–08/11, ESTADO §1 HE-R1-07) ou instalar catálogos de skills genéricas sem medir se são usadas. |

## 2. Dados que já existem

| Fonte | Caminho | O que dá para extrair | Período |
|---|---|---|---|
| Histórico Git | este repositório | commits, IDs do backlog (`HE-…`) por commit, commits de correção (`fix`, errata), tags de versão | 01/11–08/11/2026 (141 commits) |
| PRs no GitHub | `gh pr list --state all` | abertura → merge, linhas, estado | PRs #1–#15 (14 PRs; #3 não existe) |
| CI (GitHub Actions) | `gh run list` (workflow *Harness Foundation – stdlib checks*) | taxa de sucesso dos gates, 1ª execução por commit, falhas por dia | 02/11–09/11/2026 (245 execuções) |
| Suíte offline | `tests/` | nº de testes, tempo, resultado | agora (HEAD) |
| Logs do Claude Code | `~/.claude/projects/*harness-engineering*/*.jsonl` (local, fora do Git) | tokens por PR (entrada, cache, saída), modelo, sessões, comandos de teste e resultado | desde ~02/11/2026 (retenção local) |
| Logs do Codex | `~/.codex/sessions/AAAA/MM/DD/rollout-*.jsonl` (local) | tokens acumulados, comandos e `exit_code` | idem; o Codex só aparece em 3 sessões deste repo |
| Relatório diário | `scripts/daily_report.py` | por sessão: repo, Harness ligado?, skills usadas, testes (vermelho→verde, último passou), tokens, erros de ferramenta | qualquer dia com log |
| Linha de base de qualidade | `scripts/quality_baseline.py`; `docs/evidence/HE_R2_BASELINE_QUALIDADE.json` | defeitos confirmados por revisão independente por PR, tokens por PR | plataforma-metalurgica: 238 PRs (17/10–07/11) |
| Recibos de instalação | `docs/evidence/HE_R1_*.json`, `HE_OP_*.json` | instalação, descoberta, ligação em repositórios | 02/11–08/11 |
| ESTADO | `docs/ESTADO.md` | repositórios ligados (7 no `main`), lições que viraram regra (13) | atual |

## 3. Métricas priorizadas (10)

| # | Métrica | Definição | Unidade | Coleta | Frequência | Linha de base (15/11) | Publicável |
|---|---|---|---|---|---|---|---|
| M1 | Testes da suíte offline | testes executados e resultado de `python -W error -m unittest discover -s tests` com `JEV_REAL_INTEGRATION=0` | testes; s | comando local ou log do CI | a cada entrega | **279 testes, OK (2 skipped), 87,2 s** [medido] | sim |
| M2 | Taxa de sucesso do gate de CI | execuções `success` ÷ (execuções − canceladas) do workflow de qualidade | % | `gh run list` | semanal | **90,5 %** (220/243); **100 % desde 04/11** (56/56); `main` 11/11 [medido] | sim |
| M3 | Aprovação do CI na 1ª execução | commits cujo primeiro run do CI passou ÷ commits testados | % | `gh run list` agrupado por `headSha` | semanal | **90,4 %** (123/136) [medido] | sim |
| M4 | Retrabalho (commits de correção) | commits `fix…`, `revert`, "corrig", "errata" ÷ total de commits | % | `git log --format=%s` | por versão | **20,6 %** (29/141) [medido]; concentrado no JEV (02–03/11) | sim, com o contexto |
| M5 | Entregas do backlog concluídas | IDs `HE-…` da SPEC §10 com status ✅ no ESTADO e commit/PR no `main` | entregas | ESTADO §1 + `git log` | por versão | **15 IDs** citados em commits; R1: HE-R1-01…07 e HE-R2-01 ✅ [medido] | sim |
| M6 | Tempo por entrega (PR aberto → merge) | horas entre `createdAt` e `mergedAt` do PR | h (mediana) | `gh pr list --json createdAt,mergedAt` | por PR | **mediana 0,9 h** em 13 PRs (0,0–114,7 h) [medido]. Tempo **ativo** de trabalho: [não medido] | sim |
| M7 | Custo de tokens por entrega | tokens do Claude Code das sessões cujo branch é o do PR (`quality_baseline.py`) | tokens (mediana por PR) | `quality_baseline.py --repo C:/dev/harness-engineering` | por PR | saída **52.517**; entrada sem cache **198.013**; leitura de cache **17,1 mi** (9 de 13 PRs) [medido]. Codex: [não medido]. Custo em US$: [não medido] | sim, como tokens; US$ não |
| M8 | Sessões que terminam com teste verde | sessões deste repo com testes cujo último teste passou ÷ sessões com testes | % | `daily_report.py --json`, filtrado por repo | diária | **12/12** sessões; 106 execuções de teste, 4 falhas, 3 sessões vermelho→verde (01–15/11, 16 sessões) [medido] | sim |
| M9 | Adoção nos repositórios | repositórios com o Harness no `main`; sessões de agente em repositório com Harness ÷ total | repos; % | ESTADO §1; `daily_report.py` | mensal | **7 repos**; **136/197 sessões (69 %)** em repo com Harness, 01–15/11 [medido; o campo reflete o estado atual do repo, não o do dia] | sim |
| M10 | Defeitos por PR revisado | defeitos confirmados pela revisão independente ÷ PRs revisados com código | defeitos/PR | `quality_baseline.py` | por lote de PRs | **neste repo: [não medido]** (0 de 13 PRs com revisão em tabela). Referência da plataforma: **1,05** (20 defeitos, 19 PRs) [medido, outro repositório] | só agregado |

Fora das 10, como contexto: **13 lições que viraram regra** (ESTADO §4) e **40+ documentos consolidados em 4**
(HE-DOC-01). São fatos do repositório, não métricas recorrentes.

## 4. Linha de base calculada agora

Todos os comandos rodaram em 15/11/2026 nesta worktree. Saídas brutas ficaram em `_local/artifacts/metricas/` (fora
do Git, contêm nomes de outros repositórios); o agregado sem esses nomes está no JSON de evidência.

| Métrica | Valor | Marca | Comando | Evidência |
|---|---|---|---|---|
| M1 | 279 testes, OK, 2 skipped, 87,2 s | [medido] | `JEV_REAL_INTEGRATION=0 python -W error -m unittest discover -s tests` | JSON `suite` |
| M2 | 220 success, 23 failure, 2 cancelled → 90,5 %; falhas: 19 em 02/11, 4 em 03/11; 0 desde 04/11 | [medido] | `gh run list --limit 400 --json conclusion,event,headBranch,createdAt,workflowName,headSha` | JSON `ci` |
| M3 | 123 de 136 commits passaram na 1ª execução | [medido] | idem, agrupado por `headSha` | JSON `ci` |
| M4 | 29 de 141 commits | [medido] | `git log --format=%s \| grep -ciE '^(fix\|revert)\|corrig\|errata'` | JSON `git` |
| M5 | 15 IDs em commits; versões `v1.0.0`, `v1.1.0` (07/11), `v1.2.0` (08/11) | [medido] | `git log --oneline \| grep -oE 'HE-[A-Z0-9-]+' \| sort \| uniq -c`; `git tag` | JSON `git` |
| M6 | mediana 0,9 h; 3 PRs grandes da fundação levaram 27,8–114,7 h | [medido] | `gh pr list --state all --json number,createdAt,mergedAt` | JSON `prs` |
| M6 (tempo ativo) | `null` | [não medido] | — | §6 |
| M7 | mediana 52.517 tokens de saída por PR; soma de 914.245 em 9 PRs | [medido] | `python scripts/quality_baseline.py --repo C:/dev/harness-engineering --project-glob "*harness-engineering*" --out _local/artifacts/metricas/quality_baseline_harness.json` | JSON `tokens_per_pr_claude` |
| M7 (US$) | `null` (assinatura não vira preço por chamada, SPEC §6) | [não medido] | — | — |
| M8 | 12/12; 4 falhas em 106 execuções de teste | [medido] | `python scripts/daily_report.py --date 2026-11-DD --json` para DD = 01…15 | JSON `agent_sessions` |
| M9 | 7 repos; 136/197 sessões | [medido] | ESTADO §1; `daily_report.py` | JSON `agent_sessions.all_repos` |
| M10 | `null` neste repo; 1,05 na plataforma | [não medido] / [medido] | `quality_baseline.py` | `HE_R2_BASELINE_QUALIDADE.json` |

**Limites conhecidos da linha de base**
- A suíte tem 284 `def test_` no fonte e 279 executados: a diferença vem de classes ignoradas ou parametrização,
  não foi investigada.
- Os PRs #1, #2 e #4 (97 commits só em 02/11) vieram de branches `codex/…`, cujas sessões desse período não
  aparecem casadas no `daily_report` nem no `quality_baseline` (só 3 sessões Codex neste repo): tokens dessas
  entregas ficam `null`.
- PR #2 tem registro `<synthetic>` com 0 tokens: tratado como `null`, não como 0.
- "Teste" no `daily_report` = comando reconhecido (`unittest`, `pytest`…); outra forma de rodar não conta.
- M4 conta pela mensagem do commit, não por análise do diff.

## 5. CSV de registro

Arquivo: [`metricas/registro.csv`](registro.csv), separador `;`, UTF-8, decimal com vírgula. Colunas:
`data;sistema;versao;metrica;valor;unidade;contexto;alternativa_valor;fonte_evidencia;publicavel;observacao`.
Já preenchido com as linhas reais da §4. Valor ausente fica vazio (`null`), nunca `0`.

**Como registrar uma linha nova** (ex.: depois de uma entrega):
1. Rode o comando da métrica (§4) e guarde a saída bruta em `_local/artifacts/metricas/` ou, se não tiver nome
   de outro repositório nem texto de conversa, em `docs/evidence/`.
2. Acrescente uma linha ao fim do CSV, sem editar as antigas (o histórico é o próprio arquivo):
   ```text
   2026-11-20;harness-engineering;v1.3.0;M1_testes_suite;291;testes;suite offline OK, 2 skipped;;CI run <id>;sim;
   ```
3. `versao` = tag instalada ou SHA curto; `fonte_evidencia` = comando ou caminho; `publicavel` = `sim`, `nao` ou
   `agregado`; `alternativa_valor` só se houver medida da alternativa (senão vazio).
4. Commit junto com a entrega (`docs(metricas): …`).

## 6. Instrumentação que falta (proposta; nada foi implementado)

| Lacuna | Proposta mínima (reuso primeiro) | Métrica que destrava |
|---|---|---|
| Tempo **ativo** por entrega | `quality_baseline.py` já casa sessões com o branch do PR: somar a duração (1º → último evento) das sessões de cada branch, com pausas > 30 min descontadas | M6 ativo |
| Tokens do Codex por PR | `codex_usage` já lê `rollout-*.jsonl`; falta casar o `cwd`/branch da sessão com o PR deste repo (hoje 0 casados) | M7 Codex |
| Custo em US$ | só com `cost_source` = `api_billed`; em assinatura continua `null` (SPEC §6). Para o Claude, `total_cost_usd` do `stream-json` existe só como estimativa | M7 US$ |
| Revisão independente neste repo | publicar o resultado do `/code-review` ou da revisão do Codex em tabela no PR (o formato que `quality_baseline.py` já conta) | M10 |
| Retrabalho por diff | contar arquivos alterados de novo em até 7 dias após o merge (`git log --follow`) em vez de só a mensagem | M4 mais fiel |
| Série diária automática | rodar `daily_report.py --json --output _local/artifacts/daily/AAAA-MM-DD.json` no fim do dia (MANUAL §4.1 já pede) e um script de 20 linhas que agrega a série em linhas do CSV | M8, M9 |
| Skill disparou × seguida | já está no desenho do R2 (❄️ congelado); não retomar só para o portfólio | — |

## 7. Três provas para o portfólio

| # | Dor | O que o sistema faz | Métrica | Imagem / vídeo |
|---|---|---|---|---|
| P1 | "O agente disse que estava pronto e não estava" | toda entrega passa pela suíte offline e pelo CI em Linux e Windows antes do merge; status sempre com nível de evidência | **279 testes em 87 s**; CI **100 % verde desde 04/11** (56/56), `main` 11/11; 90,4 % dos commits passam na 1ª execução | print da aba Actions com a sequência verde + terminal com `Ran 279 tests … OK`; vídeo de 30 s rodando a suíte |
| P2 | "Cada repositório tem regras diferentes e eu copio arquivos à mão" | um comando instala o kit numa versão marcada; em cada repo, plano → "sim" → aplicar → verificar, sem apagar nada alheio | **7 repositórios** ligados no `main`; **69 %** das sessões de agente (136/197, 01–15/11) já em repo com o Harness; 3 versões (`v1.0.0`→`v1.2.0`) em 2 dias | GIF do `/setup-harness` mostrando o plano e o "sim"; captura do `harness_release.py status` |
| P3 | "Número bonito sem prova" | regra `null ≠ 0`, auditoria que invalida o próprio resultado (A1 contaminado, JEV 100 % × 73 % sintético), relatório diário só com contagens | **13 erros reais viraram regra**; retrabalho **20,6 %** concentrado na fase JEV e zero falhas de CI depois; tokens por entrega medidos (mediana **52,5 mil** de saída por PR, 9 de 13 PRs) | tabela "Aconteceu → Regra" (ESTADO §4) em carrossel; trecho do JSON com `null` em vez de `0` |

Para público técnico, o que demonstra **método** é P1 e P3: gates objetivos (suíte, CI em dois sistemas, versão
marcada) e a disciplina de evidência (níveis, `null`, auditorias que derrubam o próprio resultado). P2 mostra uso.
Não usar como prova: "o kit melhora a qualidade" (não medido, R2 congelado).

## 8. Confidencialidade

- Este repositório é **público**: números agregados daqui podem ser publicados, com a data e o HEAD.
- Os logs locais (`~/.claude/projects`, `~/.codex/sessions`) contêm texto de conversa e nomes de outros
  repositórios (inclusive de clientes, como a Resiplac). Nunca publicar nem commitar: só contagens, como fazem
  `daily_report.py` e `quality_baseline.py`. As saídas brutas ficam em `_local/artifacts/` (fora do Git).
- Números da plataforma-metalurgica (M10) são de outro repositório: publicar só agregado, sem títulos de PR.
- Não publicar US$ estimado como custo real nem tokens parciais como total.
- Prints de terminal: conferir que não aparecem caminhos de cliente, chaves (`OPENROUTER_API_KEY`), e-mail ou
  nomes de repositórios privados.

## Produtividade e confiabilidade do uso de agentes (resumo)

| Pergunta | Resposta hoje | Marca |
|---|---|---|
| Tarefas executadas | 13 PRs no `main` (+1 aberto), 15 IDs do backlog em commits, 16 sessões de agente neste repo (13 Claude, 3 Codex) em 01–15/11 | [medido] |
| Taxa de sucesso nos gates | CI 90,5 % geral, 100 % desde 04/11; 1ª execução 90,4 %; sessões terminando com teste verde 12/12 | [medido] |
| Retrabalho | 20,6 % dos commits são correção | [medido] (por mensagem) |
| Testes da suíte | 279, OK, 87 s | [medido] |
| Tempo por entrega | mediana 0,9 h de PR aberto a merge; tempo ativo `null` | [medido] / [não medido] |
| Custo de tokens por entrega | mediana 52,5 mil de saída e 198 mil de entrada sem cache por PR (Claude, 9 PRs); Codex e US$ `null` | [medido] / [não medido] |
