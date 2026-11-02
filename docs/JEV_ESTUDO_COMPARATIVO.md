# Pesquisa de componentes Jev / GEV — referências auditadas

**Acesso:** GitHub de upstream + API oficial TypeSafe em 2026-11-02. O termo técnico canônico é **Jev** (TypeSafe/System One). Não se trata de um framework de agentes concorrente, mas de um modelo de decisões tipadas (`Choice`, `Score`, `Noul`, `Box`).

## Componentes, atividade recente e auditoria de repositórios

| Candidato | Tag / Branch | Commit SHA | Data | Licença | O que fornece | Risco principal | Decisão |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [FrancoisChastel/jev-code](https://github.com/FrancoisChastel/jev-code) | `v0.5.0` | `74a4569bfe8bb4ad0cc1ba74fa5867f09e267300` | 2026-10-08 (push 31/10) | MIT | MCP stdio + CLI + skill; 5 tools (`jev_classify`, `jev_check`, `jev_score`, `jev_rank`, `jev_ask`) | Gravação em config do usuário pelo instalador; envio de payload a endpoint externo | **Candidato prioritário (MCP consultivo opt-in)** |
| [felpsdev/jev-classifier](https://github.com/felpsdev/jev-classifier) | `master` (sem releases) | `e0c6cc7c6d2b1027be86ad8f4e03e191a88ec402` | 2026-09-18 | MIT | Proxy HTTP local (porta 8080) com modos Observe/Enforce; log de decisões | Interceptação de tráfego de modelo; suporte a Codex apenas em Observe (Responses Lite) | **Adiar (risco de proxy desnecessário)** |
| [n23eos/jev-skills](https://github.com/n23eos/jev-skills) | `v0.3.0` | `ff2d92b07091209c03d455d562f58c928b7b9e4e` | 2026-10-02 | MIT | 14 skills consultivas para Codex e Claude Code | Sobreposição com biblioteca ECC; sem comprovação de ROI econômico | **Referência de padrões** |
| [typesafe-ai/skills](https://github.com/typesafe-ai/skills) | `main` | `302eea662c54bca6730873fe245bec1d69ebc23d` | 2026-10-15 | MIT | Skill canônica TypeSafe (`skills/typesafe-ai/SKILL.md`) | Instruções de design; não executa chamadas automaticamente | **Referência canônica de API** |
| [vinilana/jev-eval-agent](https://github.com/vinilana/jev-eval-agent) | `main` | `b34a12f...` | 2026-09-17 | MIT | Benchmark com 100 ferramentas sintéticas | Conjunto mock sem verificação de tarefas de engenharia de software | Apenas inspiração de método |
| [themsquared/jev-benchmark](https://github.com/themsquared/jev-benchmark) | `main` | `f8190c1...` | 2026-09-24 | Apache-2.0 | 60 casos sintéticos rotulados | Classificação one-shot sem harness de validação | Referência metodológica |

## Evidências verificadas e ressalvas técnicas

- **`jev-code` v0.5.0:**
  - Pacote npm: `@french-castle/jev-code` v0.5.0.
  - Dependências: `@modelcontextprotocol/sdk` (1.31.0), `zod` (4.6.5), Node.js >=20.
  - Pull requests abertos auditados em 02/11/2026: PR #25 (`@modelcontextprotocol/sdk` 1.32.2), PR #22 (`zod` 4.6.7), PR #24 (dev-dependencies), PR #19 (publicação manual).
  - Comportamento de segurança: `jev-code setup` por padrão grava chaves de API nas configurações do agente. Deve-se usar obrigatoriamente `--no-env`, `--project` e `--dry-run` em ambiente descartável para impedir vazamento de credenciais ou poluição do perfil do operador.
- **`felpsdev/jev-classifier`:**
  - Sem tags ou releases versionados. Branch única `master`.
  - Modo `enforce` tenta reescrever `tool_choice`, o que viola o princípio de execução nativa do Harness. O README esclarece que com Codex Responses Lite o proxy opera apenas em `observe`. Rejeitado para o caminho crítico.
- **Documentação TypeSafe (`docs.typesafe.ai`):**
  - Primitivas: `Choice` (seleção categórica ponderada com probabilidades), `Score` (classificação ordinal em rubric), `Noul` (probabilidade escalar de afirmação verdadeira/falsa), `Box` (bounding box para visão computacional).
  - O documento `introduction/coding-agents.md` enfatiza explicitamente: **Jev não é um LLM de chat ou geração de código**. Não substitui o Codex ou Claude Code.
  - A recomendação oficial de uso em agentes de codificação é consultiva: atuar como classificador auxiliar de baixa latência (sub-250ms) e baixo custo de tokens.

## Recomendação final

1. **Reuso estrito:** Priorizar `FrancoisChastel/jev-code` v0.5.0 exclusivamente como servidor MCP stdio em modo consultivo, sem proxy e sem escrita em configurações globais.
2. **Separação de responsabilidades:**
   - Determinístico: `scripts/harness_eval.py::analyze_trajectory` e testes unitários/oráculos (fonte da verdade).
   - Probabilístico / Consultivo: Jev para triagem de falhas CI, pré-seleção de skills e priorização de code review.
3. **Gate de Contenção G1:** Sem isolamento em container/VM com canários negativos externos, nenhuma chamada live ao Jev está autorizada. O status da fase live permanece `NOT_RUN` / `BLOCKED_G1`.

### Fontes primárias auditadas
- https://github.com/FrancoisChastel/jev-code (tag `v0.5.0`, commit `74a4569bfe8bb4ad0cc1ba74fa5867f09e267300`)
- https://github.com/felpsdev/jev-classifier (commit `e0c6cc7c6d2b1027be86ad8f4e03e191a88ec402`)
- https://github.com/n23eos/jev-skills (tag `v0.3.0`, commit `ff2d92b07091209c03d455d562f58c928b7b9e4e`)
- https://github.com/typesafe-ai/skills (commit `302eea662c54bca6730873fe245bec1d69ebc23d`)
- https://docs.typesafe.ai/llms.txt e https://docs.typesafe.ai/introduction/coding-agents.md
