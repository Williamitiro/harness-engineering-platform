# HE-JEV-006 — Autorização de piloto real e escopo tecnicamente seguro

**Data:** 2026-11-02. **PR:** #2 (Draft). **Estado:** `BILLING_AUTHORIZED_BY_OWNER / SECRET_PRESENT_LOCAL / PROVIDER_RESPONSE_OBSERVED / ONE_CALL_SMOKE_VERIFIED / MODEL_BENCHMARK_NOT_RUN`.

## Autorização e escopo

O operador verificou localmente:
```
infisical run --env=dev -- python scripts/infisical_verifier.py --check-only
INF Injecting 1 Infisical secrets into your application process
SECRET_TYPESAFE_API_KEY: PRESENTE
```

E autorizou expressamente o uso de chamadas reais à TypeSafe/Jev para testes em 2026-11-02. Presença da variável **não garante** que a chave é aceita pelo provedor. Nenhuma chave foi compartilhada no repositório nem está disponível no GitHub Actions.

## Plano executável — 1 chamada controlada

Criados:
- `scripts/run_jev_live_smoke.ps1`: instala pacote npm pinado v0.5.0 antes de injetar segredo, fora do checkout, com `--ignore-scripts`; então usa Infisical para executar exatamente um smoke.
- `scripts/jev_live_smoke.py`: executa uma única chamada real de classificação consultiva a `jev_classify` com prompt público fixo, sem agência de código, sem acesso a gabaritos nem tarefa privada; saída JSON estritamente resumida; sem raw outputs, sem segredos e com `cost_usd=null`.
- `scripts/jev_adapter.py`: subprocesso com ambiente explícito agora usa um dicionário exato e **não** mistura credenciais herdadas.
- `tests/test_jev_live_smoke.py`: testes offline da limpeza de variáveis, pin de pacote, quantidade de chamadas e saída sem segredo.

Execute em PowerShell confiável, dentro de `C:\dev\harness-engineering`, **após `git pull` da branch do PR**:

```powershell
git switch codex/harness-foundation-v1
git pull --ff-only
pwsh -NoProfile -File .\scripts\run_jev_live_smoke.ps1
```

O script imprime exclusivamente os metadados resumidos do resultado ou uma mensagem de falha sem corpo do provedor. **Não publicar saídas de erro brutas de npm ou logs de processos com a chave.**

## Limites de evidência

- A execução do smoke acontece no host confiável e **não comprova G1**. O pacote Jev executa como processo externo no Windows com uma lista mínima de variáveis, mas sem confinamento de filesystem ou rede por SO.
- Esse desenho é admissível apenas para **uma classificação pública fixa e consultiva**, sem abrir repo, dados privados, ações, agentes, ferramentas de escrita ou tarefas cegas.
- Mesmo sucesso não promove métricas para `VERIFIED_ISOLATED_BENCHMARK`, não compara a condição A com J, não prova melhoria de qualidade/custo, não realiza deploy.
- A execução de agente/benchmark cego exige isolamento externo verificável, gate de rede adequado, segregação de credenciais e recibos independentes. `jev_collector.py --mode live` permanece bloqueado de propósito.
- O script limitado faz no máximo uma chamada MCP; não pode garantir que o provedor faturará uma unidade ou estimar a cobrança. Recomendado conferir o uso real no painel do provedor.

## Próximos gates

1. Confirmar um `PROVIDER_RESPONSE_OBSERVED` no terminal. Se falhar, investigar acesso ao provedor sem expor segredos.
2. Estabelecer e validar o runtime G1 de ponta a ponta e sua trilha de evidência independente.
3. Implementar baseline nativo A real, condição J real em tarefas pareadas, custos observáveis e critérios de adoção.
4. Manter PR Draft, sem aprovação implícita de produção ou merge.

## HE-JEV-006a — diagnóstico seguro após primeira falha

A primeira execução do operador em 2026-11-02 instalou o pacote v0.5.0, recebeu uma variável do Infisical e retornou `SMOKE_FAILED: JevAdapterError`. Essa mensagem genérica **não prova** que a chave foi rejeitada, que houve cobrança ou que o endpoint respondeu.

Correção de observabilidade: `JevMcpClient.classify` categoriza erros do upstream sem repassar mensagens externas. `jev_live_smoke.py` imprime apenas `code=...` estável. Os testes verificam que dados sensíveis inseridos artificialmente em mensagens de erro não aparecem na saída.

Para executar **uma segunda tentativa autorizada**, sem reinstalar o pacote se já estiver íntegro:

```powershell
git switch codex/harness-foundation-v1
git pull --ff-only
pwsh -NoProfile -File .\scripts\run_jev_live_smoke.ps1
```

Códigos possíveis:
- `AUTH_REJECTED`: o provedor recusou autenticação; confira no painel TypeSafe a origem da chave sem divulgá-la. Uma variável presente não comprova validade.
- `BILLING_OR_CREDITS`: crédito/conta/forma de pagamento requer atenção.
- `RATE_LIMITED`: restrição de chamadas; não disparar retries em lote.
- `NETWORK_OR_TLS`: falha de conexão/TLS; avaliar proxy e conectividade da máquina sem transmitir a chave para um host desconhecido.
- `REQUEST_REJECTED`: payload incompatível ou validação upstream.
- `MCP_TIMEOUT`, `MCP_PROCESS_EXITED`, `MCP_INITIALIZE_FAILED`: problema no processo/protocolo local.
- `UPSTREAM_ERROR_UNCLASSIFIED`: não reconhecido; analisar uma reprodução local sanitizada, sem enviar corpo bruto, header Authorization ou variáveis.
- `MCP_PROTOCOL_OR_CLIENT_ERROR` ou `LOCAL_RUNTIME_ERROR`: possível problema no adaptador, executar testes locais offline.

`PROVIDER_RESPONSE_OBSERVED` confirma apenas que uma chamada consultiva de texto público teve resposta, e **não** comprova G1 nem ganho empírico. Todos os comandos de benchmark live de agentes continuam bloqueados.

### Limite de tentativa de rede

O runner fixa `JEV_CODE_MAX_RETRIES=0` e `JEV_CODE_TIMEOUT_MS=30000` no subprocesso MCP para evitar retries HTTP automáticos da camada `jev-code` no teste diagnóstico. Isso limita a uma solicitação lógica sem retries configurados pelo Jev; **não permite inferir cobrança** e não valida comportamento de qualquer intermediário externo. O script não grava a chave.


## HE-JEV-006b — Resolução da causa raiz de AUTH_REJECTED (roteamento OpenRouter vs TypeSafe Direct)

A execução do teste diagnóstico resultou em `SMOKE_FAILED: code=AUTH_REJECTED`.

### Causa raiz técnica

1. A chave armazenada pelo operador no Infisical é originária do **OpenRouter** (prefixo `sk-or-`), injetada sob o nome de variável `TYPESAFE_API_KEY`.
2. O pacote upstream `@french-castle/jev-code` v0.5.0 estabelece que a variável de ambiente decide o provedor padrão, e não realiza roteamento automático baseado apenas no formato da credencial:
   - `TYPESAFE_API_KEY` sem `JEV_CODE_PROVIDER` direciona chamadas para `https://api.typesafe.ai`.
   - O endpoint da TypeSafe espera credenciais nativas (`ts_...` ou `apikey_...`) e rejeita credenciais com formato `sk-or-...` retornando `HTTP 401 Unauthorized`.
   - O utilitário `doctor` do pacote apontou explicitamente:
     `TYPESAFE_API_KEY looks like an OpenRouter key (sk-or-…) but is sent to TypeSafe, as set. If it belongs to OpenRouter, move it to OPENROUTER_API_KEY.`

### Correção de engenharia

1. **Auto-roteamento inteligente e seguro no `isolated_child_env` (`scripts/jev_live_smoke.py`):**
   - Suporta tanto `TYPESAFE_API_KEY` quanto `OPENROUTER_API_KEY`.
   - Quando a credencial fornecida possui o prefixo `sk-or-` e nenhum provedor explícito for declarado, o ambiente isolado do processo filho MCP configura automaticamente `JEV_CODE_PROVIDER=openrouter` e espelha a credencial em `OPENROUTER_API_KEY`.
   - Preserva `typesafe` direto quando a chave for nativa (`ts_...` ou `apikey_...`).
   - Respeita integralmente overrides declarados em `JEV_CODE_PROVIDER` (`typesafe`, `openrouter`, `vercel`).
2. **Suporte no verificador sanitizado (`scripts/infisical_verifier.py`):**
   - Detecta `OPENROUTER_API_KEY` e reporta `provider_hint` sem expor valores ou dados confidenciais.
3. **Cobertura de testes automatizados:**
   - Adicionados testes unitários em `tests/test_jev_live_smoke.py` validando auto-roteamento, precedência de chave, providers explícitos e rejeição de providers inválidos.

### Resultado confirmado em execução real

Execução realizada via `pwsh -NoProfile -File .\scripts\run_jev_live_smoke.ps1`:
```json
{
  "G1_verified": false,
  "benchmark_evidence": false,
  "cost_usd": null,
  "decision_status": "SUCCESS",
  "label": "software-development",
  "latency_ms": 880.07,
  "model": "typesafe/jev-1.14-20261014",
  "model_quality_proven": false,
  "scope": "ONE_CALL_SMOKE_ONLY_NOT_A_BENCHMARK",
  "status": "PROVIDER_RESPONSE_OBSERVED",
  "task_kind": "fixed_public_prompt",
  "tokens_in": 399,
  "tokens_out": 36,
  "upstream": "@french-castle/jev-code",
  "upstream_version": "0.5.0"
}
```

O gate `PROVIDER_RESPONSE_OBSERVED` foi alcançado com sucesso. O modelo servido via OpenRouter (`typesafe/jev-1.14-20261014`) classificou a tarefa com decisão `auto` (`decision_status: SUCCESS`, label `software-development`) em 880ms.

---

## HE-JEV-006c — Dupla auditoria independente do Gemini / correção de escopo

**Revisão:** 2026-11-02. A execução live bem-sucedida no commit `848d001` é **evidência reportada pelo executor local e documentada no PR**, não reproduzida pelo GitHub Actions nem pelo revisor remoto. O CI valida código, mocks e protocolo MCP sem API paga.

### Confirmação da causa raiz

O revisor leu diretamente o código-fonte `FrancoisChastel/jev-code@v0.5.0`: `src/core/config.ts::selectProvider` e `src/core/providers.ts`. O upstream associa `TYPESAFE_API_KEY` ao host TypeSafe por padrão e `OPENROUTER_API_KEY` ao OpenRouter. `JEV_CODE_PROVIDER` seleciona explicitamente o host. O código não faz auto-roteamento por prefixo; o `doctor` apenas avisa sobre inconsistências.

O Gemini conseguiu o smoke live ao selecionar OpenRouter para a credencial de origem OpenRouter que estava catalogada sob nome genérico incorreto. **Essa correção funcionou naquele ambiente.**

### Riscos encontrados no código publicado pelo Gemini e ajustes

1. A versão inicial duplicava a mesma chave para `OPENROUTER_API_KEY` **e** `TYPESAFE_API_KEY`; esta duplicação é desnecessária. Agora o filho recebe somente o nome de variável do provedor escolhido. Não é preciso mudar o valor mantido no Infisical para o smoke legado.
2. Antes, `JEV_CODE_PROVIDER=typesafe` com uma chave conhecida de OpenRouter poderia executar uma chamada mal direcionada. Agora o smoke recusa combinações reconhecidamente inconsistentes antes de criar o processo MCP.
3. Quando existem chaves TypeSafe/OpenRouter distintas sem preferência expressa, o teste antigo escolhia implicitamente OpenRouter. Agora falha em modo fechado e solicita configurar `JEV_CODE_PROVIDER` para eliminar ambiguidades.
4. Para este smoke **Jev System One**, apenas `typesafe`, `openrouter` e `vercel` são suportados. Testar `openai` ou `ollama` requer um smoke específico, com outro contrato de chaves; não se tenta enviá-los por padrão.
5. Foi adicionada uma prova offline contra o **pacote upstream real**: o comando `jev-code doctor` sem `--live`, usando chave artificial com prefixo OpenRouter originalmente em `TYPESAFE_API_KEY`, precisa selecionar `OpenRouter` e base URL `https://openrouter.ai/api`. Nenhuma API paga é chamada nessa prova.

### Limites e estados

| Verificação | Estado |
|---|---|
| Protocolo MCP v0.5.0 sem chave | Validado anteriormente por CI |
| Seleção correta de host com chave sintética pelo `doctor` real | Requer CI do commit corretivo concluído |
| Smoke real em OpenRouter | Reportado `PROVIDER_RESPONSE_OBSERVED` no commit Gemini `848d001` |
| Isolamento total G1 para agentes | NÃO homologado |
| Condições A/J com modelos reais e tarefa cega | NÃO executadas |
| Métricas de custo e eficácia | NÃO verificadas |

**Atenção:** o uso de um prefixo como `sk-or-` é apenas heurística de compatibilidade para a configuração legada. Não valida a autenticidade de uma credencial. Para projetos novos, manter uma variável por provedor e selecionar explicitamente o destino; não escrever segredos em `.env`, comentários de PR ou logs.

**Sem necessidade de repetir o smoke faturável para confirmar a auditoria do CI.** Uma nova chamada live só é indicada se houver mudança operacional de credencial/configuração ou se a integridade do resultado local for questionada. Não habilitar agentes com acesso a chaves enquanto G1 completo estiver pendente.
