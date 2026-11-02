# JEV / TypeSafe — decisão arquitetural para Harness Engineering

**Data-base de verificação:** 2026-11-02. **Estado:** `RESEARCHED / NO_INSTALL / NO_LIVE_CALL / NO_ADOPTION`. **Dono da decisão de adoção:** owner após review do Codex. **Executor local opcional:** Gemini 3.8 para preparar fixtures, ambiente e evidências. **Runtimes alvo:** Codex e Claude Code, exclusivamente.

## O que JEV é — e o que não é

Jev é um **modelo de decisões tipadas** (TypeSafe/System One), distinto de LLM generativo. A API responde perguntas delimitadas com probabilidades: `Choice` (categoria), `Noul` (probabilidade de uma afirmação), `Score` (escala), e também `Box` para imagens na API oficial. Não escreve/edita código por si só; não possui autoridade de execução. Números e JSON válidos não garantem classificação correta, calibração suficiente nem segurança.

Não confundir três coisas:
1. `scripts/harness_eval.py::analyze_trajectory`: **parser determinístico** para coletar indícios de leitura de skills e execução de testes. Não chama Jev; só logs e códigos de saída podem atestar eventos.
2. **Jev / System One:** modelo remoto (ou provedor compatível) que classifica evidências fornecidas em solicitações explícitas.
3. **`jev-classifier` / `jev-code` / `jev-skills`:** adaptadores open source distintos para integrar o modelo ao runtime. Instalação de skill sem MCP não cria chamadas ao Jev.

## Decisão principal — três vias consideradas

**Recomendação para piloto futuro: `jev-code` v0.5.0, invocação MCP/CLI explícita em ambiente isolado e em modo consultivo, sem modificação global.** Repositório: https://github.com/FrancoisChastel/jev-code. Oferece cinco tools `jev_classify`, `jev_check`, `jev_score`, `jev_rank`, `jev_ask`, além de skill e integrações Codex/Claude. Publicou v0.5.0 em 2026-10-08 e registrou push em 2026-10-31; licença MIT. Observar que o suporte a novos providers e o contrato de instalação podem evoluir; fixar tag/commit e inspecionar lockfile, dependências e testes antes de executar. **Não executar `setup` global no computador do usuário.**

**Alternativa de menor superfície:** `typesafe-ai/skills` oficial, apenas instruções e SDK; indicado para projetar uma integração de aplicação, não seleciona ferramentas automaticamente. https://github.com/typesafe-ai/skills. O exemplo oficial de seleção de skills usa Choice/ranking com rechecagem; `docs.typesafe.ai/cookbooks/skill_suggestion.md`.

**Alternativa adiada:** `felpsdev/jev-classifier`, proxy/gateway para seleção de tools, com `shadow` e `enforce`; 2026-09-18 último push verificado, 4 estrelas em 2026-11-02, sem release oficial nem PR aberto na consulta. Pode interceptar requisições de modelo e roteá-las a outro endpoint; aumenta a superfície de privacidade, autenticação e causalidade. O README explicita **Codex Responses Lite apenas Observe**, sem forçar tool. Não usar como padrão. Uma alegação de -85%/-88% de input tokens em relatos do autor não é benchmark nosso e não é extrapolável.

**Alternativa específica:** `n23eos/jev-skills`, 14 skills para priorização/seleção, MIT, release v0.3.0 em 2026-10-02. Usa Jev como conselheiro opt-in e não substitui ferramentas de QA nem autorização. Pode ser inspecionado como biblioteca de padrões, evitando duplicar skills com ECC. https://github.com/n23eos/jev-skills.

## Aplicações prioritárias de JEV no Harness

| Caso | Pergunta delimitada | Saída | Quem decide/executa |
| --- | --- | --- | --- |
| Skill picker | Dentre poucas skills permitidas, qual combina com pedido? Há alguma relevante? | `Choice`/ranking + verificação de match | Codex/Claude decide se lê skill; ACL e escopo determinísticos |
| Triagem CI | Este log aponta falha infra, flake, erro de produto ou indeterminado? | Classe + confiança | Ferramenta de testes/operador valida; nunca auto-mergar |
| Prioridade de revisão | Qual achado merece olhar primeiro? | `Score`/ranking | Codex audita diff, sem autoaceite |
| Seleção de evidências | Qual arquivo/log é mais relevante à pergunta? | rank de referências permitidas | Busca e autorização ficam no código |
| Perguntas qualitativas | Este requisito está ambíguo? Há candidato sem match? | `Noul` com revisão de incerteza | Agente solicita contexto; nunca executa alteração destrutiva |

**Não usar Jev para:** julgar se um comando realmente foi executado (evento determinístico), declarar CI verde sem log, segurança, autorização, segredo, isolamento, merge/deploy, gastar créditos sem gate, ou substituir o LLM Codex/Claude Code.

## Integração planejada

```text
Codex / Claude Code nativos
   ├── skills oficiais / ECC aprovadas
   ├── testes e oráculos independentes (determinísticos; fonte de verdade)
   └── Jev tool OPCIONAL (MCP explícito, via jev-code, fora do caminho crítico)
        └── contexto sintético/sanitizado -> TypeSafe/OpenRouter/host autorizado
                  -> {label/probabilities/confidence} -> policy gate local
                        ├── alta confiança: recomendação de baixa consequência
                        └── dúvida/erro: fallback para runtime nativo + revisão
```

A policy nunca troca o runtime do Codex/Claude, nunca instala plugin global, nem deve expor história inteira de trabalho. Preferir `Observe` e entrada sintética primeiro; apenas pedidos curtos e opções fechadas. Ferramentas existentes devem continuar acessíveis sem Jev e sem queda de disponibilidade.

## Limites e riscos
- `jev-code setup` pode gravar skill, MCP config e, por padrão, copiar chave de API para configuração do agente; exigir `--no-env`, inspecionar `--dry-run`, usar somente sandbox com configs descartáveis e não compartilhar home/credenciais.
- Chamadas Jev podem enviar evidências ao host escolhido, incluindo através de gateway. Redigir/sintetizar logs e desidentificar secrets/paths. Nenhuma saída de projeto real sem autorização.
- Proxy `jev-classifier` pode interceptar conteúdo de requisições do modelo; impacto superior a MCP manual. Não usar `enforce` no piloto.
- Confiança informada não é autorização; erro de API é `ERROR` e retorna ao caminho nativo. Nenhuma exceção de política.
- Não comparar 'output tokens' isoladamente, nem extrapolar economia de tool catalog para todos os usos.
- Consultar specs e contratos atuais antes de implementar: https://docs.typesafe.ai/llms.txt ; https://docs.typesafe.ai/cookbooks/skill_suggestion.md ; https://github.com/FrancoisChastel/jev-code/blob/main/SECURITY.md.

## Critério de avanço
1. CI e revisão de segurança do Harness mantidos verdes; G1 externo ainda não comprovado e portanto impede **execução de agente no host**.
2. Prova offline da policy e coleta de métricas com fixtures rotuladas.
3. Validação opt-in de `jev-code` em ambiente separado, sem writes na home, sem login global, sem proxy e sem dados sensíveis.
4. Classificação com taxa de erros e indecisão medidas em casos de hard negatives e adversariais; custos/latência medidos.
5. **Só** considerar autoencaminhamento de baixo risco com ganho demonstrado e decisão assinada. Se não houver melhoria, `REJECT/DEFER`.

Detalhes executáveis: [JEV_PILOTO_PROTOCOLO.md](JEV_PILOTO_PROTOCOLO.md), [JEV_ESTUDO_COMPARATIVO.md](JEV_ESTUDO_COMPARATIVO.md), [JEV_HANDOFF_GEMINI.md](JEV_HANDOFF_GEMINI.md).
