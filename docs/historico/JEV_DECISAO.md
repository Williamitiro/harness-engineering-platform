# JEV / TypeSafe — decisão arquitetural para Harness Engineering

> **Revisão independente HE-JEV-003:** o comparativo preliminar 73,3% vs. 100% foi produzido por simulação com dados pré-preenchidos em fixtures, **não por chamadas reais a modelos Jev, Codex ou Claude Code**. Ver [AUDITORIA_HE_JEV_001_2026-11-02.md](AUDITORIA_HE_JEV_001_2026-11-02.md) e [AUDITORIA_HE_JEV_002_2026-11-02.md](AUDITORIA_HE_JEV_002_2026-11-02.md). Não autoriza adoção em produção.

**Data-base de verificação:** 2026-11-02. **Estado:** `PILOTO_OFFLINE_VALIDADO / LIVE_BLOCKED_G1 / NO_EMPIRICAL_MODEL_RESULTS`. **Dono da decisão de adoção:** owner após revisão independente do Codex. **Runtimes alvo:** Codex e Claude Code, exclusivamente.

## O que JEV é — e o que não é

Jev é um **modelo de decisões tipadas** (TypeSafe/System One), distinto de LLM generativo. A API responde perguntas delimitadas com probabilidades: `Choice` (categoria), `Noul` (probabilidade de uma afirmação), `Score` (escala), e `Box` para visão computacional. Não escreve/edita código por si só; não possui autoridade de execução. Números e JSON válidos não garantem classificação correta nem autorizam ações no sistema operacional.

Três camadas estritamente separadas:
1. `scripts/harness_eval.py::analyze_trajectory`: **parser determinístico** de logs e transcripts para atestar leitura de skills e execução de oráculos. Não usa Jev; eventos são binários e auditáveis.
2. **Jev / System One:** modelo remoto (ou gateway compatível) que classifica evidências sintéticas/sanitizadas em solicitações explícitas.
3. **`jev-code` v0.5.0:** adaptador MCP stdio open source recomendado como candidato exclusivo para integração consultiva, sem proxy (`scripts/jev_adapter.py`).

## Decisão principal — avaliação dos upstreams

- **Candidato Prioritário:** `FrancoisChastel/jev-code` tag `v0.5.0` (commit `74a4569bfe8bb4ad0cc1ba74fa5867f09e267300`, MIT). Fornece ferramentas MCP `jev_classify`, `jev_check`, `jev_score`, `jev_rank`, `jev_ask`. Configuração exige isolamento em sandbox descartável com `--no-env` para impedir gravação de segredos no perfil do operador.
- **Alternativa Adiada:** `felpsdev/jev-classifier` (commit `e0c6cc7c6d2b1027be86ad8f4e03e191a88ec402`, MIT). Proxy HTTP local (porta 8080) com interceptação de tráfego. Adiado por introduzir intermediário de rede desnecessário e violar o modelo de execução direta.
- **Referência de Padrões:** `n23eos/jev-skills` tag `v0.3.0` (commit `ff2d92b07091209c03d455d562f58c928b7b9e4e`, MIT). 14 skills consultivas mantidas como referência conceitual; instalação rejeitada para evitar sobreposição com ECC.
- **Referência Canônica:** `typesafe-ai/skills` (`main` commit `302eea662c54bca6730873fe245bec1d69ebc23d`, MIT). Referência oficial da API TypeSafe.

## Resultados do Benchmark Offline vs. Preparação Empírica

> **AUDITORIA CRÍTICA HE-JEV-001 / HE-JEV-002 / HE-JEV-003:** A tabela comparativa inicial (73,3% vs. 100,0%) foi produzida com campos pré-preenchidos manualmente em arquivos JSONL de fixtures (`native_predicted`, `predicted`). **Nenhum modelo real nem chamada de API foi executada naquela rodada.** Tais valores não constituem prova de superioridade de modelo nem embasam adoção em produção.

A arquitetura foi corrigida nas missões HE-JEV-002 e HE-JEV-003 para suportar uma avaliação verdadeiramente cega e empírica:
1. **Separação Cega:** Tarefas cegas (`benchmarks/jev/tasks/`) nunca contêm respostas ou rótulos esperados.
2. **Gabaritos Independentes:** Holdout ground truth (`benchmarks/jev/ground_truth/`) com justificativas e controle de abstenção.
3. **Isolamento de Sandbox:** O script `scripts/prepare_blind_sandbox.py` exporta exclusivamente tarefas para o workspace descartável, eliminando `.git` e histórico.
4. **Adaptador Oficial `jev-code` v0.5.0:** `scripts/jev_adapter.py` implementa cliente MCP stdio (JSON-RPC 2.0) com atestação criptográfica (`binding_digest`), sem proxy intermediário e sem escrita no perfil pessoal.
5. **Configurações Nativas:** `config/mcp/codex_mcp.json` e `config/mcp/claude_mcp.json` fornecem os templates nativos oficiais para Codex e Claude Code.

| Métrica / Status | Simulação Sintética Inicial | Benchmark Empírico Live |
| --- | --- | --- |
| Amostra | N=30 sintéticos pré-preenchidos | Blind Tasks N=30 (multi-domínio) |
| Chamada a Modelo | Não (`SYNTHETIC_SIMULATION_ONLY`) | Bloqueada até Gate G1 (`NOT_RUN / BLOCKED_G1`) |
| Prova de Qualidade de Modelo | Falso (`model_quality_proven=false`) | Exige pareamento A/J em container isolado |
| Status Atual | `SIMULATION_ARITHMETIC_ONLY` | `READY_FOR_AUTHORIZED_PILOT` (Gate G1 pendente) |

## Estado de Segurança e Gate G1

- O Gate de Isolamento G1 **não está homologado no host local**.
- A execução no host Windows expõe credenciais (`~/.ssh`, `~/.aws`, `.gemini`, Git pai) e saída direta à rede.
- Chamadas live ao endpoint Jev estão marcadas como **`NOT_RUN` / `BLOCKED_G1`**.
- Nenhum agente foi executado com bypass de permissões (`--dangerously-skip-permissions`).

## Recomendação Técnica e Próximos Passos

1. **Recomendação:** `INCONCLUSIVE_FOR_PRODUCTION` / `NO_EMPIRICAL_MODEL_RESULTS`. Toda a infraestrutura para execução real (adaptador MCP, atestação, cegamento, golden holdout) foi construída e testada, mas a adoção em produção requer a realização do piloto live homologado em container.
2. **Revisão Independente:** Todos os artefatos, código e testes estão prontos no PR #2 para revisão de segurança e decisão pelo **Codex**.
3. **Plano de Rollback:** Se rejeitado pelo Codex, a remoção da integração Jev não afeta o runtime nativo do Harness. Basta descartar as configurações de MCP e fixtures sem impacto funcional.
