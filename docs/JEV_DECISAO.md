# JEV / TypeSafe — decisão arquitetural para Harness Engineering

**Data-base de verificação:** 2026-11-02. **Estado:** `PILOTO_OFFLINE_VALIDADO / LIVE_BLOCKED_G1 / INCONCLUSIVE_FOR_PRODUCTION`. **Dono da decisão de adoção:** owner após revisão independente do Codex. **Runtimes alvo:** Codex e Claude Code, exclusivamente.

## O que JEV é — e o que não é

Jev é um **modelo de decisões tipadas** (TypeSafe/System One), distinto de LLM generativo. A API responde perguntas delimitadas com probabilidades: `Choice` (categoria), `Noul` (probabilidade de uma afirmação), `Score` (escala), e `Box` para visão computacional. Não escreve/edita código por si só; não possui autoridade de execução. Números e JSON válidos não garantem classificação correta nem autorizam ações no sistema operacional.

Três camadas estritamente separadas:
1. `scripts/harness_eval.py::analyze_trajectory`: **parser determinístico** de logs e transcripts para atestar leitura de skills e execução de oráculos. Não usa Jev; eventos são binários e auditáveis.
2. **Jev / System One:** modelo remoto (ou gateway compatível) que classifica evidências sintéticas/sanitizadas em solicitações explícitas.
3. **`jev-code` v0.5.0:** adaptador MCP stdio open source recomendado como candidato exclusivo para integração consultiva, sem proxy.

## Decisão principal — avaliação dos upstreams

- **Candidato Prioritário:** `FrancoisChastel/jev-code` tag `v0.5.0` (commit `74a4569bfe8bb4ad0cc1ba74fa5867f09e267300`, MIT). Fornece ferramentas MCP `jev_classify`, `jev_check`, `jev_score`, `jev_rank`, `jev_ask`. Configuração exige isolamento em sandbox descartável com `--no-env` para impedir gravação de segredos no perfil do operador.
- **Alternativa Adiada:** `felpsdev/jev-classifier` (commit `e0c6cc7c6d2b1027be86ad8f4e03e191a88ec402`, MIT). Proxy HTTP local (porta 8080) com interceptação de tráfego. Adiado por introduzir intermediário de rede desnecessário e violar o modelo de execução direta.
- **Referência de Padrões:** `n23eos/jev-skills` tag `v0.3.0` (commit `ff2d92b07091209c03d455d562f58c928b7b9e4e`, MIT). 14 skills consultivas mantidas como referência conceitual; instalação rejeitada para evitar sobreposição com ECC.
- **Referência Canônica:** `typesafe-ai/skills` (`main` commit `302eea662c54bca6730873fe245bec1d69ebc23d`, MIT). Referência oficial da API TypeSafe.

## Resultados do Benchmark Offline (Fase J1)

Medição sintética comparativa entre a **Condição A** (agente nativo via system prompt) e a **Condição J** (mesmo agente com Jev consultivo e policy gate local):

| Métrica | Condição A (Nativa) | Condição J (Jev Consultivo) | Impacto / Diferença |
| --- | --- | --- | --- |
| Amostra total (N) | 30 | 30 | Casos sintéticos congelados (5 escopos) |
| Acurácia macro | 73.3% (22/30) | 100.0% (30/30) | +26.7 p.p. |
| Decisões automáticas aceitas | 30/30 (100%) | 20/30 (66.7%) | Jev abstém em incertezas |
| Acurácia nas decisões automáticas | 73.3% (22/30) | 100.0% (20/20) | Eliminação de erros de alta confiança |
| Erros de alta confiança | 8 (inclui 2 falhas adversariais) | 0 | Gate local barrou todas as incertezas |
| Casos encaminhados para revisão | 0 (forçou resposta) | 10 (33.3%) | Abstenção segura em casos ambíguos |
| Latência média | 2.901 ms | 191 ms (Jev) | ~93% mais rápido no classificador |
| Tokens médios de entrada | 2.181 tokens | 200 tokens (Jev) | ~90% de economia de input |
| Tokens médios de saída | 170 tokens | 32 tokens (Jev) | ~81% de economia de output |

## Estado de Segurança e Gate G1

- O Gate de Isolamento G1 **não está homologado**.
- Execução local Windows não garante contenção contra acesso a credenciais de host, SSH, chaves de API, Git pai ou rede não monitorada.
- Chamadas live ao endpoint Jev estão marcadas como **`NOT_RUN` / `BLOCKED_G1`**.
- Nenhum agente foi executado com bypass de permissões (`--dangerously-skip-permissions`).

## Recomendação Técnica e Próximos Passos

1. **Recomendação:** `INCONCLUSIVE_FOR_PRODUCTION`. O modelo demonstrou vantagens expressivas de proteção e latência no benchmark offline, mas a adoção em produção requer isolamento G1 comprovado e validação de custos/tokens com provedor real.
2. **Revisão Independente:** Todos os artefatos, código e testes estão prontos no PR #2 para revisão de segurança e decisão pelo **Codex**.
3. **Plano de Rollback:** Se rejeitado pelo Codex, a remoção da integração Jev não afeta o runtime nativo do Harness. Basta descartar as configurações de MCP e fixtures sem impacto funcional.
