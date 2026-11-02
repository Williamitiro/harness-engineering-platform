# HE-JEV-007A — Handoff G1 / MXC Windows

## 1. Estado final

`BLOCKED_G1`. O `MXC_OK` reportado pelo operador é compatibilidade, não aprovação G1. O bloqueio anterior do launcher WSL não é pré-requisito para continuar no Windows e está superado pelo adendo da Issue #3 (relido, atualização `2026-11-02T21:28:48Z`).

Worktree única: `C:\dev\harness-engineering`; branch `codex/he-jev-007a`, upstream `origin/codex/he-jev-007a`. Entrada limpa em `3469dcaace7631bd434776c4d02fed376908cefe`; uma atualização `git fetch origin`. PR #4 OPEN/Draft, base main (`10de6958b88ee6fbf66a72642a3c24e59ad55f9a`). Nenhuma branch/worktree/PR adicional.

## 2. Componentes reutilizados e modificados

- `scripts/mxc_g1_preflight.py`: supervisor finito novo, limitado à lacuna Windows; usa o `codex.exe` já instalado e PowerShell do Windows. Não instala ferramentas nem altera configuração global. Uma invocação MXC por execução, timeout 40 s, zero retries. Nenhum processo destacado.
- Perfil `he-jev-g1` passado por argumentos: `windows.sandbox=mxc` explícito, requisitos gerenciados incluídos, `:root=deny`, `:minimal=read`, somente fixture de trabalho com escrita, denies exatos do checkout/home e canários protegidos, rede desabilitada. Sem fallback de sandbox. Artefatos artificiais criados antes do processo; não depende de expansão de globs.
- Canários de arquivo protegido, gabarito e `.git` são artificiais e externos à fixture de trabalho; um deny adicional dentro dela verifica precedência. Somente abre esses arquivos artificiais, sem ler arquivos reais protegidos. Controle positivo de leitura/escrita e negativa de escrita externa. Nenhuma alteração de ACL ou política do host.
- Ambiente do subprocesso limitado a variáveis operacionais Windows, sem herdar chaves/tokens. Probe verifica somente presença/ausência de nomes associados a credenciais; nunca imprime valores. Conexões TCP limitadas a `1.1.1.1:443` e listener loopback artificial do supervisor, timeout de 750 ms cada; timeout/recusa não são promovidos a prova de isolamento. Listener fechado ao fim, sem serviço persistente.
- `scripts/{jev_adapter,jev_live_smoke,native_baseline,jev_collector,prepare_blind_sandbox,canary_probes,jev_evaluator}.py` e políticas existentes preservados. Gabaritos reais não abertos. JEV/OpenRouter/Infisical e limiares 0,85/0,50 inalterados; live continua bloqueado.
- `docs/HE_JEV_007_HANDOFF.md`: atualizado com resultado Windows, substituindo a exigência anterior de runtime Linux.

Referências oficiais consultadas: [Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox) e [Permissions](https://learn.chatgpt.com/docs/permissions). A política usa negação por padrão e exceções específicas. Nada foi homologado apenas por configuração declarada.

## 3. Validações executadas

| Estado | Comando / evidência | Resultado |
|---|---|---|
| PASS | `git status --porcelain=v1`, `git branch --show-current`, `git worktree list`, `git remote -v`, `git rev-parse HEAD` | Entrada limpa na lane existente. |
| PASS | `gh pr view 4 --repo Williamitiro/harness-engineering-platform --json state,isDraft,headRefName,headRefOid,baseRefName` | OPEN, Draft, head correto, base main. |
| DIAGNÓSTICO | `codex sandbox --help` | CLI documenta perfil nomeado e `--include-managed-config`. A tentativa `codex sandbox windows --help` não é subcomando nesta versão; tentou iniciar `windows` e falhou com Windows error 2. Não testou G1 nem MXC explícito. |
| FAIL | `python scripts/mxc_g1_preflight.py` (rodada direcionada) | Exit 1, `MXC_START_OR_PROBE_FAILED`, nenhuma saída JSON dos probes. Fixture `C:\Users\itiro\AppData\Local\Temp\he-jev-mxc-g1-h9u_0hox`. |
| FAIL | Mesmo comando, após única correção de diagnóstico sanitizado | Exit 1, stdout vazio, `NO_VALID_PROBE_REPORT`; termos permitidos detectados no stderr: `mxc`, `failed`; nenhum `Windows error N` reconhecido. Fixture `C:\Users\itiro\AppData\Local\Temp\he-jev-mxc-g1-uxhp8lvc`. |
| PENDING | Canários filesystem/rede/ambiente | Sem relatório válido: nenhuma negação comprovada. Não confundir falha de inicialização com contenção. |
| PENDING | Suíte offline completa | Não executada após falha persistente da rodada direcionada; regra de parada aplicada. |
| PENDING | Fronteira broker/Codex avaliado | Não implementada/validada nesta etapa; `broker_verified=false`. Mesmo canários aprovados isoladamente não liberariam benchmark. |
| PENDING | CI do push | Sem resultado presumido; [Actions](https://github.com/Williamitiro/harness-engineering-platform/actions), sem acompanhamento contínuo. |

Cada fixture retém `command.json` (argumentos exatos sem segredos) e `report.json` (relatório sanitizado). Não foram gravados stderr/stdout brutos; o diagnóstico usa vocabulário fechado. A correção melhorou observabilidade, não corrigiu a causa de inicialização. Não há evidência suficiente para atribuir a falha a uma limitação intrínseca do MXC ou do perfil. Nenhum teste adicional autorizado executado após a repetição.

## 4. Bloqueio real

O launcher com política restrita não produziu relatório dos canários no contexto desta sessão. Logo, leitura negada, ambiente sem credenciais e egress negado permanecem NÃO COMPROVADOS. `MXC_OK` não cobre esta política. Não foi demonstrada inviabilidade geral do MXC e não se propõe WSL como alternativa. A origem da falha de inicialização ainda requer diagnóstico externo; não se alegou causa raiz com base apenas nos termos sanitizados.

## 5. Próximo comando necessário

Executar uma vez em PowerShell nativo externo à sessão de agente, a partir do repositório, sem Infisical e sem injetar credenciais:

```powershell
Set-Location -LiteralPath 'C:\dev\harness-engineering'; python .\scripts\mxc_g1_preflight.py
```

O comando é gratuito, limitado a 40 s, não usa background e imprime o caminho da fixture. Não repetir automaticamente. Se falhar, preservar o `report.json` sanitizado e encerrar; não enviar logs brutos ou segredos ao chat/GitHub.

## 6. Piloto

Comando omitido. Nenhuma chamada paga, smoke JEV, benchmark A/J, N=3 ou N=30 executado. Coletor live não liberado.

## 7. Próxima decisão

Diagnosticar a falha do launcher MXC fora desta sessão com o comando acima. Só retomar homologação após obter relatório dos canários e comprovar a fronteira do supervisor. Sem merge/deploy e sem configurações globais alteradas. Sessão encerrada no limite de uma rodada e uma correção.
