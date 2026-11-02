# HE-JEV-007A — Handoff G1 / MXC Windows

## 1. Estado final

`BLOCKED_G1` integral: **canários negativos MXC PASS; fronteira broker/Codex ainda PENDING**. O operador executou o preflight corrigido e o agente consultou seu `report.json` local sem repetir o teste. Resultado `exit_code=0`, `canaries_passed=true`, `broker_verified=false`. O bloqueio anterior WSL não é pré-requisito para continuar no Windows.

Worktree única: `C:\dev\harness-engineering`; branch `codex/he-jev-007a`, upstream `origin/codex/he-jev-007a`. Entrada limpa em `3469dcaace7631bd434776c4d02fed376908cefe`; uma atualização `git fetch origin`. PR #4 OPEN/Draft, base main (`10de6958b88ee6fbf66a72642a3c24e59ad55f9a`). Nenhuma branch/worktree/PR adicional.

## 2. Componentes reutilizados e modificados

- `scripts/mxc_g1_preflight.py`: supervisor finito novo, limitado à lacuna Windows; usa o `codex.exe` já instalado e PowerShell do Windows. Não instala ferramentas nem altera configuração global. Uma invocação MXC por execução, timeout 40 s, zero retries. Nenhum processo destacado.
- Perfil `he-jev-g1` passado por argumentos: `windows.sandbox=mxc` explícito, requisitos gerenciados incluídos, `:root=deny`, `:minimal=read`, somente fixture de trabalho com escrita, denies exatos do checkout/home e canários protegidos, rede desabilitada. Sem fallback de sandbox. Artefatos artificiais criados antes do processo; não depende de expansão de globs.
- Canários de arquivo protegido, gabarito e `.git` são artificiais e externos à fixture de trabalho; um deny adicional dentro dela verifica precedência. Somente abre esses arquivos artificiais, sem ler arquivos reais protegidos. Controle positivo de leitura/escrita e negativa de escrita externa. Nenhuma alteração de ACL ou política do host.
- Ambiente do subprocesso limitado a variáveis operacionais Windows, sem herdar chaves/tokens. Probe verifica somente presença/ausência de nomes associados a credenciais; nunca imprime valores. Conexões TCP limitadas a `1.1.1.1:443` e listener loopback artificial do supervisor, timeout de 750 ms cada; timeout/recusa não são promovidos a prova de isolamento. Listener fechado ao fim, sem serviço persistente.
- `scripts/{jev_adapter,jev_live_smoke,native_baseline,jev_collector,prepare_blind_sandbox,canary_probes,jev_evaluator}.py` e políticas existentes preservados. Gabaritos reais não abertos. JEV/OpenRouter/Infisical e limiares 0,85/0,50 inalterados; live continua bloqueado.
- `docs/HE_JEV_007_HANDOFF.md`: atualizado com resultado Windows, substituindo a exigência anterior de runtime Linux.
- Retomada de diagnóstico: `--diagnose-startup` preserva somente stderr de falha em diretório local com ACL para o SID do operador e SYSTEM. A ACL é aplicada antes de iniciar MXC, com duas operações auxiliares limitadas a 5 s cada; falha da ACL aborta sem iniciar MXC. Não altera ACL dos canários, política G1, configurações globais ou saída sanitizada. O arquivo privado não é impresso, publicado nem gravado no checkout.
- Correção após diagnóstico externo: incluir `SystemDrive` na lista explícita de variáveis operacionais do supervisor. O MXC exige essa variável na preparação; ela não é uma credencial. Nenhuma permissão de arquivo/rede foi ampliada.
- Operador autorizou expressamente `-ExecutionPolicy RemoteSigned` somente no PowerShell descartável do MXC após diagnóstico de bloqueio do `probe.ps1`. Argumento adicionado ao processo filho; sem `Set-ExecutionPolicy`, escrita no registro ou alteração global. Permissões filesystem/rede MXC inalteradas.

Referências oficiais consultadas: [Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox) e [Permissions](https://learn.chatgpt.com/docs/permissions). A política usa negação por padrão e exceções específicas. Nada foi homologado apenas por configuração declarada.

## 3. Validações executadas

| Estado | Comando / evidência | Resultado |
|---|---|---|
| PASS | `git status --porcelain=v1`, `git branch --show-current`, `git worktree list`, `git remote -v`, `git rev-parse HEAD` | Entrada limpa na lane existente. |
| PASS | `gh pr view 4 --repo Williamitiro/harness-engineering-platform --json state,isDraft,headRefName,headRefOid,baseRefName` | OPEN, Draft, head correto, base main. |
| DIAGNÓSTICO | `codex sandbox --help` | CLI documenta perfil nomeado e `--include-managed-config`. A tentativa `codex sandbox windows --help` não é subcomando nesta versão; tentou iniciar `windows` e falhou com Windows error 2. Não testou G1 nem MXC explícito. |
| FAIL | `python scripts/mxc_g1_preflight.py` (rodada direcionada) | Exit 1, `MXC_START_OR_PROBE_FAILED`, nenhuma saída JSON dos probes. Fixture `C:\Users\itiro\AppData\Local\Temp\he-jev-mxc-g1-h9u_0hox`. |
| FAIL | Mesmo comando, após única correção de diagnóstico sanitizado | Exit 1, stdout vazio, `NO_VALID_PROBE_REPORT`; termos permitidos detectados no stderr: `mxc`, `failed`; nenhum `Windows error N` reconhecido. Fixture `C:\Users\itiro\AppData\Local\Temp\he-jev-mxc-g1-uxhp8lvc`. |
| FAIL REPORTADO | Execução externa do operador com o mesmo comando | Mesmo erro/exit 1, stdout vazio. Fixture reportada `C:\Users\itiro\AppData\Local\Temp\he-jev-mxc-g1-l_zn0nfh`. Não reproduzida novamente pelo agente. |
| FAIL REPORTADO / DIAGNÓSTICO OBTIDO | Execução externa com `--diagnose-startup` | Fixture `C:\Users\itiro\AppData\Local\Temp\he-jev-mxc-g1-6x7kgc_5`; exit 1 antes dos probes. Arquivo privado consultado localmente: a preparação MXC exige `SystemDrive` não vazio, ausente da lista de ambiente do launcher. Nenhum segredo no diagnóstico e nenhum log bruto copiado para Git. |
| FAIL REPORTADO / DIAGNÓSTICO OBTIDO | Execução externa após inclusão de `SystemDrive` | Fixture `C:\Users\itiro\AppData\Local\Temp\he-jev-mxc-g1-lg9di7ec`; exit 1. Log privado confirma que PowerShell iniciou, mas recusou `probe.ps1` pela política de execução. Canários não executados. |
| PASS OBSERVADO | Runtime após `RemoteSigned` autorizado para o filho | Operador executou `python scripts/mxc_g1_preflight.py --diagnose-startup` na versão `7df51b9`. Fixture `C:\Users\itiro\AppData\Local\Temp\he-jev-mxc-g1-3hq11r0e`; relatório local consultado, exit 0. Cópia sanitizada em `docs/evidence/HE_JEV_007A_MXC_CANARIES.json`. Nenhuma repetição pelo agente. |
| PASS | Inspeção estática via `ast.parse` e verificação da tupla `keep` | Sintaxe válida e `SystemDrive` presente na lista. Não executa o launcher nem aprova G1. |
| PASS OBSERVADO | Canários filesystem/rede/ambiente | Controles de leitura/escrita permitidos true; canários protegido, gabarito artificial, `.git` artificial e deny interno DENIED; escrita externa DENIED; variáveis de credencial verificadas ausentes; TCP externo e loopback DENIED. `canaries_passed=true`. Escopo limitado aos probes e à política desta execução, sem atestação externa nem execução de modelo. |
| PENDING | Suíte offline completa | Não executada após falha persistente da rodada direcionada; regra de parada aplicada. |
| PENDING | Fronteira broker/Codex avaliado | Não implementada/validada nesta etapa; `broker_verified=false`. Mesmo canários aprovados isoladamente não liberariam benchmark. |
| PENDING | CI do push | Sem resultado presumido; [Actions](https://github.com/Williamitiro/harness-engineering-platform/actions), sem acompanhamento contínuo. |

Cada fixture retém `command.json` (argumentos exatos sem segredos) e `report.json` (relatório sanitizado). As tentativas anteriores descartaram stderr/stdout brutos; o vocabulário fechado foi insuficiente para explicar a falha. O novo modo opt-in guarda stderr de falha apenas no diretório privado local e retorna seu caminho no campo `private_diagnostic_file`. Isto corrige a perda do diagnóstico, não a causa de inicialização. Não há evidência suficiente para atribuir a falha a uma limitação intrínseca do MXC ou do perfil.

## 4. Bloqueio real

Os bloqueios de inicialização (`SystemDrive` e execução de `probe.ps1`) foram resolvidos e os canários passaram. O único gate técnico ainda aberto é comprovar a fronteira do broker/supervisor com o Codex avaliado: segredo apenas no supervisor, interface restrita e invocações limitadas. O teste atual não implementa nem autentica essa fronteira (`broker_verified=false`) e não executa o modelo Codex. Portanto o isolamento observado do subprocesso MXC não libera benchmark nem prova isolamento end-to-end do futuro executor A/J. Coletor live permanece bloqueado.

## 5. Próximo comando necessário

**Nenhum novo comando necessário para os canários: já passaram; não repetir.** Comando já executado pelo operador, registrado apenas para reprodução futura quando houver mudança relevante:

```powershell
Set-Location -LiteralPath 'C:\dev\harness-engineering'; python .\scripts\mxc_g1_preflight.py --diagnose-startup
```

O comando é gratuito, limita MXC a 40 s (mais até 10 s para preparar a ACL) e não usa background. Não há comando implementado de preflight do broker nesta entrega. Não substituir esse gate por repetição dos mesmos canários.

## 6. Piloto

Comando omitido. Nenhuma chamada paga, smoke JEV, benchmark A/J, N=3 ou N=30 executado. Coletor live não liberado.

## 7. Próxima decisão

Encerrar esta etapa de validação MXC com canários PASS. Próximo trabalho específico, mediante nova ordem: implementar e validar offline a fronteira mínima do supervisor/broker usando o runtime MXC agora observado. Não executar piloto ou ampliar para 007B. Nenhum comando adicional solicitado ao operador nesta entrega; PR permanece Draft, sem merge/deploy.
