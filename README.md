# Harness Engineering — integração seletiva, verificável e reutilizável

> ## SPEC CANÔNICA — EXECUÇÃO POR RELEASES (atualizado em 02/11/2026)
>
> **Leia primeiro:** [SPEC de uso diário + benchmark de agentes obrigatório](docs/HARNESS_SPEC_CANONICA_USO_DIARIO_E_BENCHMARK_V1.md). O [dossiê original dos 12 repositórios](docs/reference/CONSOLIDADO_REPOSITORIOS_HARNESS_ENGINEERING_2026-11-02.md) está preservado como referência histórica.
>
> **Pareto V1:** R1 = pacote nativo e reversível de regras/skills por projeto; **R2 = benchmark real de programação, custo, latência e qualidade como gate obrigatório**, avaliando reutilização de Harbor; R3 = Claude Code; R4–R6 = JEV opcional e demais integrações seletivas. **HE-OP-01 implementado e testado offline:** `project-doctor` e `project-plan` somente-leitura para Codex. `project-attach/verify/remove` continuam propostos; R1/R2 ainda não concluídos. Veja [auditoria e evidências HE-OP-01](docs/HE_OP_01_AUDITORIA_2026-11-02.md).
>
> **Status comprovado:** JEV remoto **já funciona via API HTTPS** no supervisor Python e o piloto A×J de três *classificações* concluiu; **NÃO** equivale a benchmark de desenvolvimento nem a economia comprovada. PR #4 continua Draft. Registros/afirmações anteriores sobre falha Node/MCP ou benchmark sintético **estão superados** quando divergirem da SPEC. Codex e Claude Code permanecem runtimes nativos; nenhum outro projeto é modificado automaticamente.
>
---


> **Estado revisado HE-JEV-001:** implementação offline e CI são reais; o suposto ganho Jev 100% vs. 73,3% foi calculado sobre previsões inventadas em fixtures sintéticas, sem chamadas a modelos. Não é benchmark comparativo. Ver [auditoria independente](docs/AUDITORIA_HE_JEV_001_2026-11-02.md).

> **Segurança e decisão atual (02/11/2026):** resultado A/C antigo é CONTAMINADO (baseline leu solução anterior do Git pai); o runner original NÃO isolava o sistema. Corrigida a execução offline e introduzido bloqueio por padrão de chamadas live sem ambiente previamente isolado. Veja [errata](docs/AUDITORIA_CORRECOES_2026-11-02.md) e [JEV](docs/JEV_DECISAO.md). CI verde será requisito do HEAD novo. Não adotar skills em projeto real apenas com esses dados.


**Status:** Homologação A1 executada. Os únicos executores de código autorizados são **Codex** e **Claude Code**; o repositório NÃO é um runtime próprio de agentes. Codex atingiu Níveis 1 a 5 de maturidade de skills com oráculo externo aprovado (100%); Claude Code está integrado, com runner preparado e status fatual registrado como BLOCKED (autenticação local pendente). O experimento histórico Gemini/Antigravity permanece como arquivo legado.

## Jev / TypeSafe — infraestrutura de benchmark empírico (HE-JEV-002)

A classificação semântica **Jev** é candidata complementar ao Harness, não substituta de Codex, Claude Code, QA determinístico ou política de segurança. Para evitar confusão entre simulação e dados reais, a infraestrutura separa estritamente entradas cegas de gabaritos independentes:

- [Pré-registro do experimento](docs/JEV_PRE_REGISTRO_EXPERIMENTO.md) · [Auditoria independente HE-JEV-001](docs/AUDITORIA_HE_JEV_001_2026-11-02.md)
- [Relatório de isolamento Gate G1](docs/ISOLAMENTO_G1_RELATORIO.md) · [Runbook operacional de benchmark](docs/RUNBOOK_BENCHMARK_EMPIRICO.md)
- [Integração MCP oficial jev-code v0.5.0](docs/JEV_MCP_INTEGRACAO.md) · [Decisão arquitetural](docs/JEV_DECISAO.md)
- Tarefas cegas (`benchmarks/jev/tasks/`) e gabarito holdout (`benchmarks/jev/ground_truth/`).
- Coletor com hash SHA-256 e cronometragem: `scripts/jev_collector.py`.
- Verificador independente com cálculo de Macro-F1 por domínio: `scripts/jev_evaluator.py`.

```powershell
# Execução simulada (100% offline, stdlib)
python scripts/jev_collector.py --tasks benchmarks/jev/tasks/tasks_all.jsonl --condition CONDITION_J_ADVISORY --mode simulation --output docs/evidence/runs/run_sim_j.jsonl
python scripts/jev_evaluator.py --run docs/evidence/runs/run_sim_j.jsonl --ground-truth benchmarks/jev/ground_truth/golden_all.jsonl --policy config/jev_multi_domain_policy.json
```

**Aviso de evidência:** resultados de simulação são categorizados compulsoriamente como `SYNTHETIC_SIMULATION_ONLY`. Chamadas reais live permanecem `BLOCKED_G1` até a homologação de container isolado e aprovação de faturamento pelo operador.

## Comece aqui

- [Relatório de homologação A1 (Codex e Claude Code)](docs/HOMOLOGACAO_A1_CODEX_CLAUDE.md)
- [Manual técnico e decisões](docs/MANUAL_HARNESS_V1.md)
- [Procedimento operacional e comandos](docs/RUNBOOK_CODEX_CLAUDE.md)
- [Protocolo experimental e critérios de aceite](docs/PROTOCOLO_VALIDACAO.md)
- [Handoff de conclusão para Codex](docs/HANDOFF_CODEX.md)
- [Fontes, revisão e política de atualização](docs/UPSTREAM_REUSE.md)
- [Registro de riscos e fases](docs/DECISOES_E_RISCOS.md)
- [Evidência empírica Codex Condição C](docs/evidence/EVAL_CODEX_C_RATELIMIT.json)
- [Evidência empírica Codex Baseline Condição A](docs/evidence/EVAL_CODEX_A_RATELIMIT.json)
- [Evidência diagnóstica Claude Code](docs/evidence/EVAL_CLAUDE_C_RATELIMIT.json)
- [Legado A0](docs/A0_RELATORIO_2026-11-01.md) e [HE-AG-001](docs/HE_AG_001_RELATORIO_2026-11-01.md)

## Entregue nesta branch

1. **Ciclo de vida de skills ECC (`scripts/harnessctl.py`):**
   - Planejamento (`plan`), instalação com `--apply`, verificação (`verify`) e remoção estrita (`remove --apply`).
   - Bloqueio fail-closed contra colisões, symlinks de ancestrais absolutos, alterações no checkout do ECC e divergência de hashes contra `config/approved_skills.json`.
   - Limpeza integral de diretórios intermediários (`.agents` e `.claude`) e reversão atômica em falhas parciais.
2. **Avaliador e Homologador Nativo (`scripts/harness_eval.py`):**
   - Execução padronizada dos runtimes nativos oficiais (Codex CLI e Claude Code) em sandboxes descartáveis `.poc/`.
   - Verificação empírica dos Níveis 1 (`FILE_PRESENT`), 2 (`DISCOVERED`), 3 (`INVOKED`), 4 (`BEHAVIOR_OBSERVED`) e 5 (`OUTCOME_VERIFIED`).
   - Avaliação contra oráculo externo congelado e imune a adulteração pelo agente (`benchmarks/tasks/ratelimit/oracle.py`).
   - Monitoramento de canário de contenção (`.poc/canary_sentinel.txt`).
3. **Contratos Nativos de Projeto:**
   - [`templates/AGENTS.md`](templates/AGENTS.md): Contrato para agentes Codex.
   - [`templates/CLAUDE.md`](templates/CLAUDE.md): Contrato para agentes Claude Code.
4. **Testes Unitários e CI Offline:**
   - 42 testes unitários em `tests/` cobrindo lifecycle, reversão, proteção contra adulteração, pipeline empírico do Jev e avaliação.
   - Execução em CI GitHub Actions (`.github/workflows/quality.yml`) 100% offline, sem LLM e sem credenciais.

```powershell
# Execução da suíte de testes unitários (100% offline, stdlib)
python -m unittest discover -s tests -v

# Auditoria matemática de evidências legadas
python scripts/audit_legacy.py docs/evidence/HE_AG_001_RESULTADOS.csv --expected-input 419019

# Avaliação padronizada em modo dry-run (sem chamada a LLM)
python scripts/harness_eval.py --client codex --condition C --dry-run
```

## Política de segurança

Sem credenciais no Git; sem automação de publicação; sem alteração da home do usuário ou de configurações globais; sem execução com LLM em CI. Branches e PRs passam por revisão independente. Evidência de arquivo copiado não é evidência de skill executada: a homologação exige comprovação em trajetória e aprovação por oráculo externo.

## PRs

O PR #1 contém o trabalho anterior A0 e evidências HE-AG-001; **não é reescrito por esta entrega**. Esta branch (`codex/harness-foundation-v1`, PR #2) parte do commit de #1 e deve ser integrada apenas após revisão técnica humana, sem merge automático.
