# Estado do Harness Engineering

**Atualizado em 22/11/2026.** Único lugar com status; teto de 5 KB (`.harness/docs-policy.json`). Detalhe e prova
de cada linha até 21/11: [historico/ESTADO_ATE_2026-11-21.md](historico/ESTADO_ATE_2026-11-21.md). Ao concluir uma
entrega, troque a linha dela; o que não couber vai para `docs/evidence/`.

Este computador roda a **`v1.5.0`** (`~/.harness-engineering/v1.5.0`, atalho `current`, desde 22/11/2026), com o
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
| **Caminho único de documentos (HE-DOC-04)**: `setup-harness` com etapa de documentos e limpeza; `project-verify` com `docs` (`null` sem planta) | ✅ desde a `v1.4.1` (duas revisões independentes) | suíte offline PASS; `evidence/HE_DOC_04_VERIFICACAO_2026-11-22.json`, `evidence/HE_DOC_04_1_REVISAO_2026-11-22.json` |
| **Recursos do computador (HE-OPS-01/02)**: `resource-check` (só leitura) e `resource-clean plan/apply`; skill `limpeza-de-disco` ligada a eles | ✅ `v1.5.0`, instalada; 1ª limpeza real 22/11: livre 18,2 → 35,9 GB (39 itens, 7 sessões); sessão filha arquivada junto sem perda → corrigido para a `v1.5.1` | 47 testes; mutações das travas pegas; `evidence/HE_OPS_01_RESOURCE_CHECK_2026-11-22.json` |
| JEV via HTTPS | ✅ código; smoke relatado | `scripts/jev_http.py` |
| Isolamento G1 | ⚠️ só MXC do Codex observado | `evidence/HE_JEV_007A_*.json` |
| Claude Code em benchmark | ❌ nunca homologado | — |

## 2. Pendências, em ordem

1. **HE-DOC-02, o que falta: o Codex.** Aprovar o hook em `/hooks` e repetir os 3 ensaios (ou `BLOCKED_*` factual no
   Windows). A mensagem do orçamento corrigida no ensaio só chega ao hook instalado na próxima tag. Pendente do
   operador: o plano do GitHub (proteção de branch em privado).
2. **HE-DOC-03 fechado (22/11):** 11 repositórios `PASS`, 2 pulados, 3 esperam PRs (`evidence/HE_DOC_03_REPOS.json`).
3. **Limitações na `v1.5.0`:** `verify` byte a byte (Windows com autocrlf: `EDITED_BY_PROJECT`, lado seguro);
   planta com um índice só (7 índices de assunto do `modelo-de-negocio-resiplac` sem conferência).
4. Rodar `scripts/daily_report.py` no fim do dia e anotar aqui o que falhar.
5. Primeira tarefa real na plataforma com o Harness, com revisão externa (aceite do HE-R1-05).
6. Revisão independente em todo PR com código (hoje 24 de 238 na plataforma).
7. HE-OPS-02: o dono desliga o parallax-threejs na conta (6 servidores voltaram em minutos) e decide o arquivamento
   automático do app; sem isso o disco volta a encher.
8. Métricas: uma linha em `metricas/registro.csv` por entrega.

## 3. Problemas abertos

| Problema | Saída |
|---|---|
| Hook não vê escrita por comando de shell | `Stop` e CI pegam depois |
| `Stop` só olha arquivos gravados na sessão (criação do transcript); no Linux, sem essa data, olha tudo; `git mv` mantém a data antiga | o CI pega |
| Codex no Windows: sandbox já negou o Python do perfil | provar no ensaio do Codex |
| CLIs atrás do upstream (Claude 2.1.268, Codex 0.166.0) | atualizar só com autorização |
| Sem corte financeiro independente | antes de qualquer lote pago |
