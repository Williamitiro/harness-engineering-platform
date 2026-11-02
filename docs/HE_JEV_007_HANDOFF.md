# HE-JEV-007A — Handoff de execução controlada

## 1. Estado final

`BLOCKED_G1` — inspeção de pré-requisitos em 02/11/2026; nenhuma homologação G1.
Especificação relida: [Issue #3](https://github.com/Williamitiro/harness-engineering-platform/issues/3), atualização `2026-11-02T21:16:18Z`.
Repositório `Williamitiro/harness-engineering-platform`, worktree única `C:\dev\harness-engineering`.
Entrada limpa em `main` / `10de6958b88ee6fbf66a72642a3c24e59ad55f9a`; um `git fetch origin` e checkout da branch remota existente.
Branch `codex/he-jev-007a`, upstream `origin/codex/he-jev-007a`, HEAD inicial `1989a63e7ccd7596a154f764b0c419828f9bb6f2`.
[PR #4](https://github.com/Williamitiro/harness-engineering-platform/pull/4) confirmado OPEN/Draft, base `main`. Nenhuma nova lane, merge ou deploy.

## 2. Componentes reutilizados e modificados

| Componente | Classificação | Finalidade e limite constatado |
|---|---|---|
| `scripts/jev_adapter.py` | REUTILIZÁVEL / REAL | Cliente MCP, parsing e timeout; digest local não autentica execução. |
| `scripts/jev_live_smoke.py` | REUTILIZÁVEL / REAL | Seleção de provedor, ambiente mínimo, segredo somente na variável do provedor; retries 0 e timeout 30 s. Smoke histórico não repetido. |
| `scripts/native_baseline.py` | BLOQUEADO / SIMULADO | Baseline sintético; live recusa com BLOCKED_G1. Ainda não executa Codex real. |
| `scripts/jev_collector.py` | BLOQUEADO / SIMULADO | Contrato e coleta sintética reutilizáveis; live permanece fail-closed. |
| `scripts/prepare_blind_sandbox.py` | INCOMPLETO | Exportação cega e manifesto reutilizáveis; launcher bwrap usa `--unshare-all` e executa somente canários. Não inicia Codex nem oferece canal ao supervisor. |
| `scripts/canary_probes.py` | INCOMPLETO | Probes existentes reutilizáveis; ausência de caminhos e falha de uma conexão não comprovam G1 no runtime real do Codex. |
| `scripts/jev_evaluator.py` | REUTILIZÁVEL / REAL | Avaliação offline, pareamento e rejeição de proveniência live autoatribuída; manter gabarito fora do executor. |
| `config/jev_multi_domain_policy.json` | REUTILIZÁVEL | Limiares preservados: confiança 0,85 e margem 0,50. |
| `benchmarks/jev/tasks/tasks_all.jsonl` | REUTILIZÁVEL | Fonte de tarefas cegas; não montar checkout com `.git` e gabaritos no executor. |
| `config/mcp/{codex_mcp,jev_code_mcp_template}.json` | INCOMPLETO | Templates de processo filho com variável de segredo; não constituem broker externo sem segredo no agente. |
| `.github/workflows/quality.yml` e testes específicos existentes | REUTILIZÁVEL / OFFLINE | Validam contratos/mocks; CI não homologa runtime G1 local. |
| Integração Claude/Gemini, serviços ou framework novo | DESNECESSÁRIO | Fora da fase autorizada. |
| `docs/HE_JEV_007_HANDOFF.md` | MODIFICADO | Única alteração: diagnóstico e handoff; nenhum código funcional reescrito. |

## 3. Validações executadas

PASS significa apenas a constatação descrita, nunca G1.

| Estado | Comando / inspeção | Resultado e evidência |
|---|---|---|
| PASS | `git status --porcelain=v1`, `git remote -v`, `git rev-parse HEAD`, `git worktree list` | Checkout limpo, remoto esperado, uma worktree; identidade registrada na seção 1. |
| PASS | `git fetch origin`; `git switch --track origin/codex/he-jev-007a` | Uma atualização de referências; branch existente retomada, limpa no HEAD inicial. |
| PASS | `gh pr view 4 --repo Williamitiro/harness-engineering-platform --json state,isDraft,headRefName,headRefOid,baseRefName,url` | OPEN, Draft, head correto, base main. |
| PASS | `Get-Command codex,wsl,docker,podman,bwrap -ErrorAction SilentlyContinue` | Windows encontra `codex.ps1` e `wsl.exe`; não encontra docker/podman/bwrap no PATH Windows. |
| PASS | `wsl --list --verbose` | Ubuntu WSL2 estava Stopped antes da inspeção Linux. |
| PASS | Comando da seção 5 | `/usr/bin/bwrap`, `/mnt/c/Users/itiro/AppData/Roaming/npm/codex`, `/usr/bin/python3`, `WINDOWS_MOUNT_PRESENT`; `command -v node` sem saída. Inspeção iniciou o WSL, sem mudar sua configuração. |
| PASS | Leitura do pacote Codex Windows e dos launchers/templates | Pacote Windows 0.166.0: wrapper exige Node e usa binário win32; launcher bwrap não monta `/mnt/c`. Não há integração de supervisor implementada nesse fluxo. |
| PENDING | Testes direcionados e suíte offline | Não executados: regra de parada G1 atingida antes de implementação; alteração somente documental. |
| PENDING | Preflight G1 end-to-end e piloto A/J | Não implementados/executados; zero chamadas pagas, zero smokes, zero benchmarks. |
| PENDING | CI do push | Sem resultado presumido; consultar [Actions](https://github.com/Williamitiro/harness-engineering-platform/actions), sem monitoramento contínuo. |

## 4. Bloqueio real

Único bloqueio primário: **não há runtime Codex Linux independente dos mounts Windows disponível no ambiente de isolamento existente**. No Ubuntu, `codex` resolve para o wrapper Windows em `/mnt/c`, sem Node no PATH Linux. O launcher bwrap exportado oculta esse mount e isola toda a rede; portanto não consegue executar esse Codex nem conectá-lo ao supervisor autenticado. Liberar `/mnt/c`, herdar o home/credenciais ou abrir egress não atende G1.

Isto demonstra a incompatibilidade do runtime disponível com o launcher existente, não impossibilidade geral do Codex ou do WSL. Não foram executados canários, tentativas de instalação, novos brokers ou arquiteturas alternativas. O smoke aprovado continua válido dentro de seu escopo consultivo histórico.

## 5. Comando de preflight local

Preflight G1 completo indisponível neste estado; não há comando implementado que possa honestamente homologar o fluxo. O único comando local abaixo reproduz **a checagem gratuita de pré-requisitos**, sem acessar segredos ou chamar modelos; saída favorável não libera live:

```powershell
wsl -d Ubuntu --exec sh -c 'command -v bwrap; command -v codex; command -v node; command -v python3; test ! -d /mnt/c && echo WINDOWS_MOUNT_ABSENT || echo WINDOWS_MOUNT_PRESENT'
```

Não usar `canary_probes.py` isoladamente como preflight end-to-end ou prova de autorização.

## 6. Piloto de 3 casos

Comando omitido: executor pareado não implementado nem validado offline. Fase 007B não iniciada.

## 7. Próxima decisão

Corrigir o bloqueio específico. Única ação externa necessária: o operador disponibilizar um runtime Codex Linux autocontido no ambiente G1, independente de `/mnt/c` e do home Windows, com canal restrito ao supervisor confiável que detenha as credenciais. Depois retomar 007A para integrar e comprovar as negativas no mesmo runtime, antes de qualquer piloto. Nenhuma alteração global ou provisionamento de host foi feita nesta sessão.
