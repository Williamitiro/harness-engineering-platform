# HE-JEV-006 — Autorização de piloto real e escopo tecnicamente seguro

**Data:** 2026-11-02. **PR:** #2 (Draft). **Estado:** `BILLING_AUTHORIZED_BY_OWNER / SECRET_PRESENT_LOCAL / ONE_CALL_SMOKE_PREPARED / MODEL_BENCHMARK_NOT_RUN`.

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
