# JEV no Harness Engineering — decisão de reuso

## Distinção de funções
`scripts/harness_eval.py::analyze_trajectory` é **classificador determinístico de evidências**, escrito neste repositório. Procura execução de comandos, leitura de skills e sequência de testes; deve ser auditável e reproduzível, sem chamada ao JEV.

**Jev (TypeSafe)** é um modelo de classificação. **`jev-classifier`**, https://github.com/felpsdev/jev-classifier, é um gateway/tool router MIT (Node.js 22+, Codex/Claude Code, modo Observe, API key Jev separada). Seu valor possível é **escolha prévia de ferramenta/skill relevante** ou classificação adicional de intenção, não comprovar com certeza quais ferramentas foram usadas ou que o teste realmente passou.

## Decisão
**CANDIDATO / NÃO INSTALADO / NÃO INTEGRADO EM PRODUÇÃO.** Não interceptar chamadas Codex/Claude nem compartilhar credenciais/traces por padrão. A integração proxy pode mudar fluxo e consumir créditos, introduzindo confusão experimental. O README upstream informa que Codex Responses Lite pode apenas registrar sugestões sem impor uma ferramenta; verificar eficácia no modo exato antes de alegar redução de tokens.

## Protocolo opcional futuro
1. Revisar estado atual, licença, PRs, release, modelo/API, dados enviados, custos e comportamento offline.
2. Primeiro modo **Observe** em fixtures sintéticas sem dados de produção, sem alterar runtime nativo.
3. Comparar seleção/routing com catálogo fixo, casos rotulados e matriz de confusão; medir precisão/recall, encaminhamento errado, fallback, latência, custo e vazamento.
4. Nunca delegar ao JEV decisões finais de ACL, autorização, isolamento, execução destrutiva ou aceite de QA. Esses gates continuam determinísticos e controlados fora do modelo.
5. Só adotar se benefício incremental se comprovar contra a escolha nativa de ferramentas, sem afetar a qualidade.

## Fontes
- https://github.com/felpsdev/jev-classifier
- https://github.com/vinilana/jev-eval-agent
- https://github.com/themsquared/jev-benchmark

**Prioridade:** depois de CI/G1/A1 corrigidos. Não há motivo para instalar mais um classificador durante a correção de bugs de segurança.
