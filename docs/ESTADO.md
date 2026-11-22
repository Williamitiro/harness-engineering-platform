# Estado do Harness Engineering

**Atualizado em 22/11/2026.** Único lugar com status; teto de 5 KB (`.harness/docs-policy.json`). Detalhe e prova
de cada linha até 21/11: [historico/ESTADO_ATE_2026-11-21.md](historico/ESTADO_ATE_2026-11-21.md). Ao concluir uma
entrega, troque a linha dela; o que não couber vai para `docs/evidence/`.

Este computador roda a **`v1.4.0`** (`~/.harness-engineering/v1.4.0`, atalho `current`, desde 22/11/2026), com o
hook de documentos instalado no Claude Code e no Codex. Esta pasta é só de desenvolvimento.

## 1. O que existe

| Capacidade | Status | Prova |
|---|---|---|
| Docs canônicos (README, MANUAL, SPEC, ESTADO) | ✅ HE-DOC-01 | revisão |
| Camada 1 (máquina): só `setup-harness`, Claude Code + Codex | ✅ HE-R1-02/04/06, instalada | testes; Codex `DISCOVERED`; Claude chat novo PASS |
| Camada 2 (repositório): `project-plan/attach/verify/remove` | ✅ HE-R1-03; 7 repositórios no `main` | testes; `project-verify` em cada um |
| `setup-harness` oferece regras que faltam no `AGENTS.md` | ✅ HE-R1-07, na `v1.2.0` | 1 teste; ensaio só leitura |
| Instalação por tag (`harness_release.py`) | ✅ | 7 testes; usada aqui |
| Telemetria do runner | ✅ HE-R2-01; execução real `NOT_RUN` | 21 testes |
| Benchmark A/B (R2) | ❄️ congelado | `NOT_RUN` |
| Linha de base de qualidade | ✅ medida (238 PRs, 24 revisados) | `evidence/HE_R2_BASELINE_QUALIDADE.json` |
| Plano de métricas | ✅ documento | `metricas/`; `evidence/METRICAS_BASELINE_2026-11-15.json` |
| Relatório diário | ✅ | 9 testes; MANUAL §4 |
| CI (Linux + Windows, actions por SHA) | ✅ | `.github/workflows/quality.yml` |
| **Organização de documentos (HE-DOC-02)**: `docs-plan`, `docs-check` (lugar, orçamento, índice), hook `PreToolUse`+`Stop` para Claude Code e Codex, `docs-hook-plan/install/verify/remove`, `action.yml`; política e limpeza deste repositório | ✅ na `v1.3.0`, hook instalado. **Claude Code: PASS** no ensaio real (lugar, orçamento e `Stop`). Codex: `NOT_RUN` | 38 testes offline; revisão do PR #17 (10 achados corrigidos); `evidence/HE_DOC_02_ENSAIO_CLAUDE_2026-11-21.json` |
| **Caminho único de documentos (HE-DOC-04)**: `setup-harness` com etapa de documentos e regras de limpeza; `project-verify` com `docs` (`null` sem planta); planta no repositório novo; porteiro diz os bytes que sobram | ✅ `v1.4.0`, instalada; correções da revisão (links, padrão mais específico, `DOCS_NOT_RUN`) em PR para a `v1.4.1` | suíte offline PASS; `evidence/HE_DOC_04_VERIFICACAO_2026-11-22.json`, `evidence/HE_DOC_04_1_REVISAO_2026-11-22.json` |
| **Orçamento do computador (HE-OPS-01)**: `resource-check`, só leitura, 12 regras com causa e dono dos processos | ✅ código, fora de tag; revisão independente (8 de 9 achados corrigidos; perfis do `ms-playwright-mcp` não conferidos); medição 22/11: `FAIL` em 9 de 12 | 27 testes, 8 mutações pegas; `evidence/HE_OPS_01_RESOURCE_CHECK_2026-11-22.json` |
| JEV via HTTPS | ✅ código; smoke relatado | `scripts/jev_http.py` |
| Isolamento G1 | ⚠️ só MXC do Codex observado | `evidence/HE_JEV_007A_*.json` |
| Claude Code em benchmark | ❌ nunca homologado | — |

## 2. Pendências, em ordem

1. **HE-DOC-02, o que falta: o Codex.** Aprovar o hook em `/hooks` e repetir os 3 ensaios (ou `BLOCKED_*` factual no
   Windows). A mensagem do orçamento corrigida no ensaio só chega ao hook instalado na próxima tag. Pendente do
   operador: o plano do GitHub (proteção de branch em privado).
2. **HE-DOC-03:** 5 repositórios `PASS`; `videos-motions` em PR; 10 na fila depois da `v1.4.1`
   (`evidence/HE_DOC_03_REPOS.json`).
3. Ligação pendente: PR #1 do cad e do itiro-negocios-ideias (decisão do dono); `frontend-resiplac` e
   `modelo-de-negocio-resiplac` depois de resolver as alterações locais.
4. Rodar `scripts/daily_report.py` no fim do dia e anotar aqui o que falhar.
5. Primeira tarefa real na plataforma com o Harness, com revisão externa (aceite do HE-R1-05).
6. Revisão independente em todo PR com código (hoje 24 de 238 na plataforma).
7. HE-OPS-01: entrar na próxima tag; depois, a skill `limpeza-de-disco` chamar o `resource-check` (escrita na home).
8. Métricas: uma linha em `metricas/registro.csv` por entrega.

## 3. Problemas abertos

| Problema | Saída |
|---|---|
| Hook não vê escrita por comando de shell | `Stop` e CI pegam depois |
| `Stop` só olha arquivos gravados na sessão (criação do transcript); no Linux, sem essa data, olha tudo; `git mv` mantém a data antiga | o CI pega |
| Codex no Windows: sandbox já negou o Python do perfil | provar no ensaio do Codex |
| CLIs atrás do upstream (Claude 2.1.268, Codex 0.166.0) | atualizar só com autorização |
| Sem corte financeiro independente | antes de qualquer lote pago |
