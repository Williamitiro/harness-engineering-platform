# Estado do Harness Engineering

**Atualizado em 21/11/2026.** Único lugar com status; teto de 5 KB (`.harness/docs-policy.json`). Detalhe e prova
de cada linha até 21/11: [historico/ESTADO_ATE_2026-11-21.md](historico/ESTADO_ATE_2026-11-21.md). Ao concluir uma
entrega, troque a linha dela; o que não couber vai para `docs/evidence/`.

Este computador roda a **`v1.2.0`** (`~/.harness-engineering/v1.2.0`, atalho `current`). Esta pasta é só de
desenvolvimento.

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
| **Organização de documentos (HE-DOC-02)**: `docs-plan`, `docs-check` (lugar, orçamento, índice), hook `PreToolUse`+`Stop` para Claude Code e Codex, `docs-hook-plan/install/verify/remove`, `action.yml`; política e limpeza deste repositório | ✅ código e testes; hook **não instalado** nesta máquina; tag nova e ensaio real `NOT_RUN` | 38 testes offline (entrada simulada das duas ferramentas; home sintética; comando do hook executado no PowerShell, no cmd e no sh); revisão do PR #17: 10 achados corrigidos; `scripts/docs_gate.py`, SPEC §11 |
| JEV via HTTPS | ✅ código; smoke relatado | `scripts/jev_http.py` |
| Isolamento G1 | ⚠️ só MXC do Codex observado | `evidence/HE_JEV_007A_*.json` |
| Claude Code em benchmark | ❌ nunca homologado | — |

## 2. Pendências, em ordem

1. **HE-DOC-02, o que falta** (cada passo pede o "sim" do operador): (e) tag `v1.3.0` e `harness_release.py install`;
   depois `harnessctl.py docs-hook-plan`, mostrar e aplicar com `docs-hook-install --apply` (altera
   `~/.claude/settings.json` e `~/.codex/hooks.json`); no Codex, aprovar em `/hooks`. (f) Ensaio real: `.md` no lugar
   errado recusado com o caminho certo no Claude Code e no Codex (ou `BLOCKED_*` factual no Codex em Windows).
   Pendente do operador: o plano do GitHub (proteção de branch em privado).
2. **HE-DOC-03** depois do (f): limpeza por repositório, piloto `williamitiro-web` (SPEC §11.4).
3. Ligação pendente: PR #1 do cad e do itiro-negocios-ideias (decisão do dono); `frontend-resiplac` e
   `modelo-de-negocio-resiplac` depois de resolver as alterações locais.
4. Rodar `scripts/daily_report.py` no fim do dia e anotar aqui o que falhar.
5. Primeira tarefa real na plataforma com o Harness, com revisão externa (aceite do HE-R1-05).
6. Revisão independente em todo PR com código (hoje 24 de 238 na plataforma).
7. Métricas: uma linha em `metricas/registro.csv` por entrega.

## 3. Problemas abertos

| Problema | Saída |
|---|---|
| Hook não vê escrita por comando de shell | `Stop` e CI pegam depois |
| `Stop` só olha arquivos gravados na sessão (criação do transcript); no Linux, sem essa data, olha tudo; `git mv` mantém a data antiga | o CI pega |
| Codex no Windows: sandbox já negou o Python do perfil | provar no passo (f) |
| CLIs atrás do upstream (Claude 2.1.268, Codex 0.166.0) | atualizar só com autorização |
| Sem corte financeiro independente | antes de qualquer lote pago |
