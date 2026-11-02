# HE-JEV-007A — Executor mínimo A/J e preflight nativo

## 1. Estado final

`READY_FOR_LOCAL_G1_PREFLIGHT`, com **preflight nativo G1 PASS OBSERVADO pelo operador** na versão `032bf27`. Relatório local consultado pelo agente: exit 0, `broker_verified=true`, `canaries_passed=true`, zero chamadas pagas. Mantido o nome de estado contratual; o resultado detalhado do preflight é PASS. Nenhum modelo ou benchmark executado pelo agente.

Lane: `Williamitiro/harness-engineering-platform`, worktree `C:\dev\harness-engineering`, branch `codex/he-jev-007a`, upstream `origin/codex/he-jev-007a`, PR #4 OPEN/Draft -> main. Entrada limpa em `487e08a243e946b76d72b87c8ab9b3cfd84ce342`. Base main `10de6958b88ee6fbf66a72642a3c24e59ad55f9a`. Uma atualização de referências, sem nova lane/merge/deploy.

## 2. Componentes reutilizados e modificados

- `scripts/mxc_g1_preflight.py`: conserva fixture/política/canários já observados, SystemDrive e RemoteSigned autorizado somente no filho; adiciona `--native-broker`. Pelo novo caminho, os mesmos probes são executados por `command/exec` do Codex app-server com `permissionProfile=he-jev-g1`. A callback do piloto só recebe controle após PASS real nesta invocação; não há flag para autoatribuir G1.
- `scripts/codex_native_broker.py`: processo finito do app-server oficial, por stdin/stdout privados, sem listener/serviço persistente. Reutiliza leitores e encerramento de `JevMcpClient`. Supervisor aceita apenas RPCs construídos pelo executor, recusa pedidos de permissões/ferramentas adicionais, limita consumo do protocolo e turnos; mesmos perfil/workspace usados nos canários e na classificação.
- Fronteira explícita: **o Codex app-server é supervisor nativo confiável fora do MXC; os processos de tarefa/ferramenta ficam dentro do MXC**. A autenticação nativa existente do Codex fica no supervisor; ela não é copiada para fixture, logs ou ambiente de ferramentas. Isto não alega que o processo inteiro do app-server esteja dentro do MXC. OpenRouter/Infisical nunca entram no ambiente desse supervisor ou das tarefas; JEV roda apenas em seu subprocesso MCP confiável, com ambiente explícito. Não se cria outro agente.
- Ambiente de ferramentas construído por `shell_environment_policy.inherit=none` e lista operacional; leitura do checkout/home e canários protegidos negada, rede de ferramentas desabilitada. Supervisor tem o acesso de rede necessário ao provedor, sem expô-lo como ferramenta ao modelo. MCPs, plugins e hooks herdados são substituídos por tabelas vazias nesta invocação; documentos de projeto desabilitados; instrução de classificação explícita e schema de labels. Evento de uso de ferramenta durante classificação aborta o supervisor.
- `scripts/paired_executor.py`: CLI única `preflight`/`pilot`. Reutiliza `build_native_prompt`, `load_tasks`, cliente JEV e seleção de credenciais/pin v0.5.0 existentes. Não instala nem baixa pacotes. A usa Codex nativo; J usa OpenRouter explicitamente, e review/uncertain/limiares insuficientes acionam o mesmo modelo Codex de A. Confiança 0,85 e margem 0,50 preservadas.
- A conta nativa usada nesta implementação é a identidade ChatGPT já autenticada no Codex, por um alias de provedor com protocolo Responses e endpoint Codex ChatGPT. O alias evita sobrescrever IDs reservados e fixa `request_max_retries=0`, `stream_max_retries=0`, idle timeout 30 s. Não lê/copia auth.json. Compatibilidade/autenticação do primeiro turno real não foi testada com API paga.
- Limites: até 3 tarefas; até 3 turnos A + 3 JEV + 3 fallbacks, sem retries do executor/provedores configurados. Codex: timeout de classificação 60 s, no máximo 6 turnos nativos no processo; JEV: 30 s por classificação. São limites lógicos, não prova de limite financeiro ou contagem faturada pelo provedor. Custos e tokens indisponíveis permanecem null; uso JEV/fallback fica separado, latência J cobre o pipeline inteiro. Erro aborta sem retry; não há recibo parcial de sucesso se o piloto não completar.
- `tests/test_paired_executor.py`: testes offline de limiares, fallback para o mesmo modelo, limites, contaminação, segregação de segredo, RPC/perfil e negação de ampliação. Integração nativa gratuita opt-in foi SKIP na suíte; o operador executou separadamente o preflight nativo real com PASS, sem repetição do agente.
- `scripts/jev_collector.py` e `scripts/jev_evaluator.py`: preservados fail-closed. O novo launcher não altera a aceitação de registros pelo avaliador histórico: resultados pareados OBSERVED não são promovidos a VERIFIED nem aceitos automaticamente pelo loader antigo. Scoring autenticado do avaliador antigo não foi liberado; o piloto mínimo registra decisões e métricas observadas para inspeção do operador, sem recomendação de adoção.

Referência oficial do transporte e dos métodos: [Codex App Server](https://learn.chatgpt.com/docs/app-server). Contrato conferido também no schema gerado pelo Codex 0.166.0 instalado. [Permissions](https://learn.chatgpt.com/docs/permissions) e [MXC](https://learn.chatgpt.com/docs/windows/windows-sandbox) orientam a política existente. Nenhuma mudança global.

## 3. Validações executadas

| Estado | Comando / evidência | Resultado |
|---|---|---|
| PASS OBSERVADO, anterior | `python scripts/mxc_g1_preflight.py --diagnose-startup` pelo operador | `docs/evidence/HE_JEV_007A_MXC_CANARIES.json`: exit 0; controles positivos true; protegido/gabarito/.git/deny interno/escrita externa DENIED; env de credenciais ausente; TCP externo e loopback DENIED. Não repetido nesta sessão. |
| PASS | `python -m unittest discover -s tests -p test_paired_executor.py -v` | 7 testes, 6 PASS e 1 integração nativa SKIP, 0 falhas. Uma execução. |
| PASS | `JEV_REAL_INTEGRATION=0`, `HE_NATIVE_G1=0`; `python -W error -m unittest discover -s tests -v` | 93 testes, 2 skips, 0 falhas, 6,037 s. Uma execução, wrapper com limite 20 s. Log `C:\Users\itiro\AppData\Local\Temp\he-jev-007a-offline-t5yxpp_r\suite.log`. |
| PASS OBSERVADO | `python scripts/paired_executor.py preflight`, executado pelo operador | Caminho `app-server -> command/exec -> MXC`, versão `032bf27`, fixture `C:\Users\itiro\AppData\Local\Temp\he-jev-mxc-g1-_xz0541n`. Relatório local consultado e preservado em `docs/evidence/HE_JEV_007A_NATIVE_G1.json`: exit 0, controles positivos true, todos os canários negativos DENIED, env de credenciais verificado ausente, `broker_verified=true`, `canaries_passed=true`, `paid_calls=0`. Nenhum turno/modelo/JEV chamado; sem repetição do agente. |
| PENDING | Piloto de 3 casos | Nenhuma chamada paga nesta sessão. Modelo/conta/provedor reais não exercitados pelo novo executor. |
| PENDING | CI do push | Consultar Actions do PR #4; sem acompanhamento contínuo nem resultado presumido. |

Gabaritos reais não foram abertos nesta sessão nem disponibilizados ao agente. Sem smoke, N=3/N=30, retries ou rodadas exploratórias de testes. Evidência histórica intacta.

## 4. Bloqueios reais

O preflight gratuito nativo passou; não há bloqueio observado dos canários ou da execução de comandos MXC pelo supervisor nativo. Essa evidência cobre os probes e a política testados, não é atestação criptográfica externa nem execução de classificação. Autenticação e comportamento do primeiro turno real permanecem não exercitados; serão observados no piloto limitado. Custos desconhecidos continuam null. Resultados do piloto não contornam o gate de proveniência do avaliador histórico. O piloto continua fail-closed se sua própria prova gratuita falhar.

## 5. Comando de preflight local

Comando já executado pelo operador com PASS; não é necessário repeti-lo isoladamente agora:

```powershell
python C:\dev\harness-engineering\scripts\paired_executor.py preflight
```

É o teste gratuito da fronteira nativa, sem chamadas de modelos. Processo finito, sem background. Retorna relatório sanitizado e fixture; em falha, apenas diagnóstico privado local, sem publicar seu conteúdo.

## 6. Comando do piloto de 3 casos

Somente após PASS do preflight nativo, no terminal do operador, fase 007B separada. Fluxo pareado validado offline; este comando NÃO foi executado. Usa o pacote JEV já instalado e a conta ChatGPT do Codex; modelo explicitamente escolhido abaixo, sem fallback para outro modelo. A saída deve ser nova e fora do checkout:

```powershell
infisical run --env=dev -- python C:\dev\harness-engineering\scripts\paired_executor.py pilot --max-tasks 3 --model gpt-6.1-sol --output "$env:TEMP\he-jev-007a-pilot-3.json"
```

O comando repete a prova gratuita em um processo nativo novo e só então despacha os casos, no mesmo supervisor/perfil daquela prova. Não iniciar agora; não ampliar para 30. Arquivo existente não é sobrescrito. JEV sempre seleciona OpenRouter e mantém segredo apenas no supervisor MCP.

## 7. Próxima decisão

Próxima execução: o piloto local limitado a três casos da seção 6, pelo operador, em fase 007B separada. Não ampliar para 30. Se falhar, preservar relatório/diagnóstico e encerrar sem retry. Nenhum piloto disparado nesta sessão; sem merge/deploy, PR permanece Draft.

## Atualização — retomada do piloto autorizada pelo operador

O piloto anterior abortou antes de gerar recibo. A preparação nativa gratuita reproduziu a causa: `thread/start` informa o arquivo global `.codex/AGENTS.md`, que o cliente anterior recusava antes de `turn/start`. Esse caminho não despachou inferência. O código agora permite somente esse arquivo de política conhecido, além da fixture; não permite auth.json, outros arquivos do home ou gabaritos como fontes. Permissões MXC das ferramentas não foram ampliadas.

Também foi corrigido encerramento potencialmente bloqueante dos pipes, adicionados checkpoints antes/depois de cada etapa e relatório Markdown/JSON inclusive em erro. O avaliador aritmético existente roda no supervisor após a coleta; gabaritos não entram em prompts, ambiente ou workspace de agentes. Erro preserva A/J/fallback já observados e aborta sem retry.

Validação desta correção: uma execução direcionada, 13 testes (12 PASS, 1 SKIP); uma suíte completa offline, 99 testes, zero falhas, 2 skips, 5,279 s. Log: `C:\Users\itiro\AppData\Local\Temp\he-jev-pilot-fix-offline-zd01jnrh\suite.log`. Diagnóstico gratuito de preparação sem turno confirmou a fonte global; nenhum smoke JEV pago foi repetido.

O usuário autorizou agora executar e produzir resultado do piloto. Uma única execução será disparada por `scripts/run_pilot_once.py`, supervisor confiável Windows fora do MXC, com limite total de 180 s, no máximo três casos e zero retries. Timeout encerra somente a árvore PID filha criada pelo supervisor. Sem N=30. Como é demorado, o disparo é a última operação da sessão; sem polling/monitoramento posterior.

Artefatos desta tentativa: `C:\Users\itiro\AppData\Local\Temp\he-jev-pilot-once-20261102-final\pilot.json`, `pilot.md`, `pilot.invocation.json`, `launch.json`, `stdout.log`, `stderr.log`. O Markdown final é gerado automaticamente ao encerrar, inclusive em falha, com acertos/latências quando houver pares completos, resultados parciais e erro por etapa. Custos desconhecidos continuam null e adoção permanece INCONCLUSIVA com N=3. Resultado live PENDING no momento deste checkpoint; não confundir testes offline com benchmark aprovado.
