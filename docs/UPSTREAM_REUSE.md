# Reuse-first — inventário e atualização de upstreams

Data de pesquisa-base: 2026-11-02. Os números de estrelas não definem adoção. Atualização é decidida por commits/releases, PRs, licença, compatibilidade, valor e prova.

| Upstream | Repositório | Licença (GitHub) | Status e uso |
| --- | --- | --- | --- |
| Everything Claude Code | https://github.com/affaan-m/ECC | MIT | Fonte de skills. Piloto pinado em `b38be6a7f635...` com dois SKILL.md; integração completa NÃO aprovada |
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

## Addendum 02/11/2026 — Jev/System One (Auditoria de Upstreams)

Inspeção direta via GitHub API e documentação oficial em 02/11/2026:

| Componente | Repositório | Versão / Tag | Commit SHA | Licença | Dependências principais | Status / Decisão |
| --- | --- | --- | --- | --- | --- | --- |
| `jev-code` | [FrancoisChastel/jev-code](https://github.com/FrancoisChastel/jev-code) | `v0.5.0` (2026-10-08) | `74a4569bfe8bb4ad0cc1ba74fa5867f09e267300` | MIT | Node >=20, `@modelcontextprotocol/sdk` (1.31.0), `zod` (4.6.5) | **Candidato prioritário (MCP consultivo)**; PRs de dependências abertos (`#22`, `#24`, `#25`); requer flag `--no-env` e isolamento |
| `jev-classifier` | [felpsdev/jev-classifier](https://github.com/felpsdev/jev-classifier) | Sem release (branch `master`) | `e0c6cc7c6d2b1027be86ad8f4e03e191a88ec402` | MIT | Node >=22, proxy local (porta 8080) | **Adiado**; proxy intercepta tráfego HTTP de modelo; maior risco operacional e de privacidade |
| `jev-skills` | [n23eos/jev-skills](https://github.com/n23eos/jev-skills) | `v0.3.0` (2026-10-02) | `ff2d92b07091209c03d455d562f58c928b7b9e4e` | MIT | Python >=3.10, uv | **Referência de padrões**; 14 skills consultivas; não instalar para evitar sobreposição com ECC |
| `typesafe-ai/skills` | [typesafe-ai/skills](https://github.com/typesafe-ai/skills) | Sem release (branch `main`) | `302eea662c54bca6730873fe245bec1d69ebc23d` | MIT | Markdown / docs | **Referência canônica** da API System One (`Choice`, `Score`, `Noul`, `Box`) |
| Documentação TypeSafe | [docs.typesafe.ai](https://docs.typesafe.ai/llms.txt) | `llms.txt` | N/A | N/A | Endpoint `POST /v1/systemone` | Confirma que Jev é modelo de decisões tipadas, não LLM gerador de código |

Consultar [decisão](JEV_DECISAO.md), [pesquisa comparativa](JEV_ESTUDO_COMPARATIVO.md) e [protocolo](JEV_PILOTO_PROTOCOLO.md). Nenhum upstream foi instalado globalmente nem executado com bypass de permissões. Live execution permanece `NOT_RUN` / `BLOCKED_G1` devido à ausência de isolamento externo em container/VM.
