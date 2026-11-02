# Harness Engineering — integração seletiva, verificável e reutilizável

**Status:** Homologação A1 executada. Os únicos executores de código autorizados são **Codex** e **Claude Code**; o repositório NÃO é um runtime próprio de agentes. Codex atingiu Níveis 1 a 5 de maturidade de skills com oráculo externo aprovado (100%); Claude Code está integrado, com runner preparado e status fatual registrado como BLOCKED (autenticação local pendente). O experimento histórico Gemini/Antigravity permanece como arquivo legado.

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
   - 21 testes unitários em `tests/` cobrindo lifecycle, reversão, proteção contra adulteração, symlinks, checkout sujo e avaliação.
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
