# Reuse-first — inventário e atualização de upstreams

Data de pesquisa-base: 2026-11-02. Os números de estrelas não definem adoção. Atualização é decidida por commits/releases, PRs, licença, compatibilidade, valor e prova.

| Upstream | Repositório | Licença (GitHub) | Status e uso |
| --- | --- | --- | --- |
| Everything Claude Code | https://github.com/affaan-m/ECC | MIT | Fonte de skills. Piloto pinado em b38be6a7f635... com dois SKILL.md; integração completa NÃO aprovada |
| GStack | https://github.com/garrytan/gstack | MIT | Fluxos de planejamento, QA e revisão. Candidato; mapear sobreposição com ECC antes da instalação |
| Harbor | https://github.com/harbor-framework/harbor | Apache-2.0 | Avaliação isolada. Candidato para A1/B; instalação/adequação runtime NÃO comprovada aqui |
| Codex | https://github.com/openai/codex | upstream oficial | Runtime de coding aprovado pelo usuário; usar capacidades nativas |
| Claude Code | https://github.com/anthropics/claude-code | upstream oficial | Runtime de coding aprovado pelo usuário; usar capacidades nativas |

A inspeção do GitHub em 02/11/2026 mostrou pushes recentes em ECC (30/10), GStack (02/11) e Harbor (02/11). Isso demonstra atividade, não garante qualidade/compatibilidade. Revisar releases e issues/PRs que afetam plugins, skills, Windows, segurança, isolamento, SDK e CLI antes de fixar novo commit.

## Quadro de decisão

- **Nativo antes de plugin:** evitar componentes que apenas duplicam ferramentas existentes.
- **Atribuição por componente:** não importar GStack inteiro junto ao ECC; evitar prompts contraditórios e contaminação de contexto.
- **Upstream pinado:** documentar SHA, licença, dependências e hash, aprovar diffs de atualização; nunca referenciar `main` mutável para reprodução.
- **Windows:** separar PowerShell local de shell do sandbox; scripts Bash do ECC podem não funcionar diretamente em PowerShell.
- **Custos:** assinatura comercial pode reportar $0 de faturamento incremental, mas tokens, tempo e limites são custo operacional.
- **Segurança:** revisar hooks, scripts executáveis e MCPs antes de conceder permissões. Nunca confiar na etiqueta de estrelas.

## Pesquisa pendente para Codex

Inspecionar documentação e comportamento efetivos das versões locais de Codex e Claude Code; verificar empacotamento oficial de plugins/skills e o que o Harbor suporta nas versões pinadas. Preencher matriz de compatibilidade com experimentos reproduzíveis. Somente então habilitar novos plugins no ambiente do operador.

## Addendum 02/11/2026 — Jev/System One

Consultar [decisão](JEV_DECISAO.md), [pesquisa comparativa](JEV_ESTUDO_COMPARATIVO.md) e [protocolo](JEV_PILOTO_PROTOCOLO.md). Candidatos atuais: `FrancoisChastel/jev-code` v0.5.0 como MCP consultivo, `felpsdev/jev-classifier` proxy adiado, `n23eos/jev-skills` como fonte de padrões e `typesafe-ai/skills` como referência oficial. Nenhum deles foi instalado ou validado live neste corte. JEV não é oráculo nem controle de segurança. Priorizar integração que preserve os Harnesses nativos, a privacidade e decisões reversíveis.
