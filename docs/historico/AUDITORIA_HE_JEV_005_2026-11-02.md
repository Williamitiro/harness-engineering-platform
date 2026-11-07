# Auditoria independente HE-JEV-005 — 2026-11-02

**Base auditada:** `c03716fe5f86edb857eaf680d371f1c13bde2c66`. **PR:** #2 (Draft).

## Evidência verificada diretamente no GitHub

- Run 41502686152: 70 testes executados; 69 OK e 1 FAIL. Falha em `test_cli_installed_detection`: o runner Ubuntu não tem Infisical instalado. Os quatro testes MCP reais foram executados e passaram, mas os testes MCP não fazem chamadas pagas nem atestam respostas de modelo.
- O conjunto `tests/test_jev_real_package.py` originalmente tentava chamar `npx -y` na descoberta completa; isso podia baixar o pacote no job chamado "offline", além de produzir ResourceWarning em pipes abertos.
- `scripts/native_baseline.py`: o modo `simulation` produz decisões e tokens **sintéticos**; o modo `live` sempre levanta `BLOCKED_G1`. O baseline nativo está apenas instrumentado, não observado. A frase "registra tokens reais" só se aplica a futuro modo live ainda não implementado.
- `scripts/jev_collector.py`: modo live recusa execução de forma incondicional, inclusive quando flags de autorização são fornecidas. O comando `infisical run ... --mode simulation` é apenas simulação, não piloto live.
- `scripts/canary_probes.py`: canários úteis contra alguns caminhos e egress para **um** destino (8.8.8.8:53), mas timeout ou conexão recusada **não certificam bloqueio universal de rede**. As verificações por caminho não provam ausência de todos os mounts, credenciais, gabaritos ou escapes de sandbox. `G1_VERIFIED` local deve ser interpretado estritamente como resultado da suíte de canários naquele ambiente — não como atestação independente integral.
- `scripts/prepare_blind_sandbox.py`: o gerador `run_isolated_bwrap.sh` executa somente os canários; ele **não executa** a classificação Jev live, não injetou credencial e não prova a cadeia de execução ponta a ponta. O manifesto aponta `environment_isolated=false` e `G1_verified=false`.
- `scripts/infisical_verifier.py` confirma configuração/local e presença da variável no processo, não validade da credencial junto ao provedor TypeSafe nem confinamento de credenciais durante chamadas.
- Não houve autorização para cobrança, mudança de configurações globais, merge ou execução live.

## Correções no GitHub

1. Teste Infisical determinístico com mocks (presença/ausência no PATH), sem exigir instalação local no runner.
2. Integração real do upstream passa a ser opt-in por `JEV_REAL_INTEGRATION=1`. CI divide teste unitário offline e teste de integração sem API faturável.
3. Subprocesso de `tools/list` agora drena e fecha pipes em `communicate()`, evitando ResourceWarning.

## Estados corrigidos (fail-closed)

| Gate | Estado auditado |
| --- | --- |
| CI no commit base | FAIL 1/70; reavaliar após correções |
| MCP protocolo upstream | 4 testes previamente PASS em CI, sem API |
| Infisical no Windows | Evidência **relatada pelo executor local**; não inspecionável pelo GitHub |
| G1 host Windows | REJECTED |
| G1 WSL2-bwrap | CANARY_PASS_REPORTED; **FULL_ATTESTATION_NOT_VERIFIED** |
| Baseline A real | NOT_RUN; simulation only |
| Piloto JEV com TypeSafe | NOT_RUN/BLOCKED_G1/BLOCKED_AUTHORIZATION |
| Decisão empírica A versus J | NOT_ESTABLISHED |

## Próxima execução externa estritamente necessária

Em terminal confiável Windows, fora do ambiente de agentes, verificar a presença da chave sem imprimir conteúdo:

```powershell
infisical run --env=dev -- python scripts/infisical_verifier.py --check-only
```

Este comando **somente verifica presença**, não executa API nem avalia segurança. O usuário ainda precisa autorizar explicitamente limites financeiros e o piloto, e executar auditoria completa de isolamento e observabilidade dentro do sandbox real. **Não executar live com os scripts atuais**: `jev_collector.py` bloqueia por projeto; será necessário implementar uma ponte segura com atestação confiável antes do piloto.

Não executar `infisical run` em volta do agente avaliado. Não publicar segredos nem resultados brutos que possam incluí-los.

## Critério de conclusão

Aprovar CI no HEAD final, checar separadamente prova do protocolo JEV e evidência de segurança G1, implementar baseline real A e condição J com dados pareados e comprovadamente blindados, mais aprovação de orçamento. Preservar o PR Draft e o código fail-closed até então.
