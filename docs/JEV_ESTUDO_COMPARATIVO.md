# Pesquisa de componentes Jev / GEV — referências auditadas

**Acesso:** GitHub de upstream + README/SECURITY/package/release/PR em 2026-11-02; modelos e regras de API a confirmar antes de chamada live. O termo usado pelo projeto é **Jev** (TypeSafe/System One); 'GEV' nesta demanda foi interpretado como o Jev discutido no histórico, não como framework independente.

## Componentes, atividade recente e adequação

| Candidato | Sinal de atividade verificado (02/11) | Licença | O que fornece | Risco principal | Decisão |
| --- | --- | --- | --- | --- | --- |
| [FrancoisChastel/jev-code](https://github.com/FrancoisChastel/jev-code) | push 31/10; release v0.5.0 em 08/10; PRs de dependências abertos em 31/10; 55 estrelas | MIT | MCP + CLI + skill, cinco tools, instalação Codex/Claude | config/credenciais e dados a endpoint externo | **Primeiro piloto opt-in** |
| [felpsdev/jev-classifier](https://github.com/felpsdev/jev-classifier) | criado e último push em 18/09; sem release/PR aberto; 4 estrelas | MIT | proxy Observe/Enforce, log de decisões, roteamento de tools | proxy no tráfego do modelo; compatibilidade Codex Responses Lite parcial | **Adiar** |
| [n23eos/jev-skills](https://github.com/n23eos/jev-skills) | push + release v0.3.0 em 02/10; 5 estrelas | MIT | 14 skills consultivas | duplicação da biblioteca ECC, sem prova de economia | Referência de padrões |
| [typesafe-ai/skills](https://github.com/typesafe-ai/skills) | skill oficial consultada via GitHub; fonte da API e boas práticas | MIT na skill consultada | documentação para construir integrador Jev | não executa classificação sozinha | Referência canônica |
| [vinilana/jev-eval-agent](https://github.com/vinilana/jev-eval-agent) | push 17/09; sem releases; 109 estrelas | validar upstream | benchmark com 100 ferramentas fictícias | tarefas mock, sem qualidade de trabalho real | Apenas método |
| [themsquared/jev-benchmark](https://github.com/themsquared/jev-benchmark) | push 24/09; sem releases; 1 estrela | Apache-2.0 | 60 casos de classificação rotulados | mede one-shot e não ganhos completos do harness | Base metodológica |

**Estrelas são metadados informativos, NÃO sinal de qualidade.** O `jev-code` venceu a triagem por ter integração MCP específica, pacote versionado, teste automatizado e manutenção mais recente que o proxy original — não por popularidade.

## Evidências verificadas e ressalvas

- `jev-code` package.json: `@french-castle/jev-code` v0.5.0, Node >=20, MCP SDK + Zod, scripts `lint`, `typecheck`, `check:skill`, `test:coverage`, `smoke`. Existe suíte no repositório, **não rodamos essa suíte aqui**.
- `jev-code` SECURITY.md: tool chama endpoint System One com payload fornecido; setup pode escrever configuração e inserir key nela por padrão. `--no-env` reduz risco de chave persistida, mas ambiente sem home compartilhada ainda é obrigatório no piloto. Variáveis por provider e proxy exigem revisão.
- `jev-classifier` README: sombra `shadow` observa sem forçar, `enforce` tenta controlar `tool_choice` com confidence gate, e Codex Responses Lite é apenas observação. Não confundir com aceleração comprovada do nosso Codex.
- Documentação TypeSafe: `Choice`, `Noul`, `Score` e `Box` são primitivas de julgamento; código mantém permissões e ação final. `Choice` tende a escolher opção mesmo quando nenhuma encaixa: combinar verificação `Noul` ('alguma opção corresponde?') e fallback.
- Cookbook oficial `skill_suggestion`: sugestão de skill entre catálogo extenso, com shortlist e rechecagem. É referência particularmente próxima do nosso problema de progressive disclosure.
- `jev-benchmark`: autor relatou 55/60 acertos com Jev e Claude em seu conjunto, porém as hipóteses e labels são próprias. Não prova superioridade do Jev nem economia para desenvolvimento real.
- Alegações de forte queda de tokens do proxy original devem ser tratadas como alegações do autor sem benchmark independente reprodutível equivalente para Codex/Claude em nossos projetos.
- Avaliar PRs e vulnerabilities upstream atuais antes de instalar; atividade de dependabot por si só não comprova resolução de bugs funcionais.

## Recomendação final

**Primeiro Jev como consultor, não como gateway e não como juiz.** Iniciar por triagem de falhas CI e sugestão de skill dentro de catálogo congelado. Medir `baseline nativo` vs `Jev consultivo` com oráculo rotulado. Exigir `no_match` e `review` como resultados legítimos. Sem teste de integrações reais, estado = pesquisa.

### Fontes primárias
- https://github.com/FrancoisChastel/jev-code
- https://github.com/FrancoisChastel/jev-code/blob/main/SECURITY.md
- https://github.com/felpsdev/jev-classifier
- https://github.com/n23eos/jev-skills
- https://github.com/typesafe-ai/skills/blob/main/skills/typesafe-ai/SKILL.md
- https://docs.typesafe.ai/llms.txt
- https://docs.typesafe.ai/cookbooks/skill_suggestion.md
- https://github.com/themsquared/jev-benchmark
