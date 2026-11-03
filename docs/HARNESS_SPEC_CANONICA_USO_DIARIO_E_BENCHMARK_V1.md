# HARNESS ENGINEERING — SPEC CANÔNICA, PLANO DE RELEASES E ACEITE PARA USO DIÁRIO (V1)

**Estado:** ESPECIFICAÇÃO NORMATIVA / implementação multi-repositório e benchmark de programação PENDENTES.  
**Corte das evidências:** 02/11/2026. **Branch de trabalho:** `codex/he-jev-007a`, [PR #4](https://github.com/Williamitiro/harness-engineering-platform/pull/4), ainda Draft e não integrado em `main`.  
**Fonte de entrada integral, preservada sem atualizar afirmações antigas:** [dossiê dos 12 repositórios](reference/CONSOLIDADO_REPOSITORIOS_HARNESS_ENGINEERING_2026-11-02.md).  
**Autoria operacional:** Harness Engineering; executor de código Codex primeiro, Claude Code depois. Revisão independente antes de merge e de alegar ganhos.

> **REGRA PARETO:** O primeiro produto utilizável entrega QUATRO capacidades, não doze integrações: **(1) instalar/verificar/remover um pacote pequeno de regras e skills em repositórios reais; (2) executar agentes nativos; (3) medir tarefas de programação com verificador externo; (4) registrar qualidade, tempo, tokens e custo com origem explícita.** Benchmark é requisito **obrigatório do MVP**, não feature futura. As demais ferramentas entram em releases posteriores, por ganho demonstrado.
>
> **REGRA REUSE-FIRST/EXECUÇÃO MÍNIMA:** escolher primeiro API HTTPS, CLI, SDK e recursos nativos documentados; só criar adaptador quando nenhuma via direta atender ao contrato. Um teste dirigido por dúvida, com critério de parada. O incidente JEV/Node é uma regressão de arquitetura a evitar, não uma razão para reinstalar Node.

## 0. Precedência, fontes e regra de verdade

1. Esta SPEC define escopo, ordem e critérios de aceite **da próxima implementação**, não afirma que funcionalidades futuras já existem.
2. O [dossiê original](reference/CONSOLIDADO_REPOSITORIOS_HARNESS_ENGINEERING_2026-11-02.md) permanece como **evidência histórica de seleção**, com recomendações e análise de relevância. Contém uma afirmação agora **SUPERADA**: JEV não estava funcional devido ao bootstrap Node. Isso foi resolvido por **API direta do OpenRouter**; não retomar diagnóstico de Node/MCP como pré-requisito de JEV.
3. Código e testes do PR #4 prevalecem para o estado técnico efetivo: `scripts/jev_http.py`, `scripts/paired_executor.py`, `scripts/mxc_g1_preflight.py`, `scripts/run_pilot_once.py`, `scripts/harnessctl.py`, `scripts/harness_eval.py` e `config/approved_skills.json`. Documentos antigos podem conter banners/relatos superados. Não tratar `main` como já contendo PR #4.
4. Resultados atribuídos ao operador: smoke HTTP real retornou `typesafe/jev-1.14-20261014`; piloto A×J com **3 tarefas de classificação** retornou `COMPLETED`, `A=3`, `J=3`, `fallback=2`, 3/3 acertos de rótulo em cada condição. Latência média A=4.880,33 ms e J=4.182,33 ms. **Não prova ganho de programação, eficiência econômica nem poder estatístico**.
5. Custo do piloto J: `0.000018858 USD` é **subtotal conhecido**, não total. Custo nativo Codex ausente nas amostras, inclusive nos dois fallbacks. O PR #4 corrige a semântica de `total_cost_usd` para `null` quando incompleto. Não converter tokens de assinatura em preço faturado.
6. GitHub CI do commit `98c1bb1` aprovado; suítes offline e integração Codex/MXC de classificação funcionaram no piloto. **Não há evidência de experiência diária multi-repo, benchmark real de patches, ou paridade live Claude Code**.
7. Documentos usados: dossiê, `docs/MANUAL_HARNESS_V1.md`, `docs/PROTOCOLO_VALIDACAO.md`, `docs/UPSTREAM_REUSE.md`, `docs/DECISOES_E_RISCOS.md`, `docs/HOMOLOGACAO_A1_CODEX_CLAUDE.md` (com errata), README e PR #4. A especificação anterior `SPEC_PLANO_UNICO_HARNESS_ENGINEERING_USO_DIARIO_V1.md` foi uma proposta de uso diário; esta revisão **torna benchmark e telemetria critérios obrigatórios do MVP**, em vez de etapas opcionais após implantação.

## 1. Missão e definição de pronto: o que o usuário recebe

**Missão:** programar normalmente em 10–20 repositórios com Codex e/ou Claude Code, sem operar um novo runtime; disponibilizar capacidades selecionadas, observar seu uso efetivo e descobrir empiricamente **qual executor/modelo/perfil entrega mudanças corretas com menor tempo, consumo e retrabalho**.

**MVP obrigatório (R1 + R2):** em pelo menos **um projeto de desenvolvimento escolhido explicitamente**, oferecer `plan` → `attach` → `verify` → trabalho nativo → `benchmark/report` → `detach`. Deve ser reproduzível e reversível, comparando agente nativo **com e sem** o pacote Harness por tarefas reais e verificador independente. Codex validado primeiro; Claude só quando sua sessão for autenticada e sua proteção nativa validada.

**Não é objetivo:** terceiro runtime de agentes, fábrica autônoma, integração compulsória de 12 repositórios, troca global de perfil do Codex/Claude, instalar `npx` ou servidor MCP para consultar JEV, benchmark sintético tratado como qualidade de programação, instalar Harbor se o executor existente já resolver.

**Diferenciação importante:**
- **Harness de desenvolvimento** = instruções/skills/QA e comparação dos agentes; núcleo obrigatório.
- **JEV** = classificador remoto opcional de tarefas/skills por API HTTPS no supervisor; não escreve código e não escolhe automaticamente o melhor modelo de programação.
- **Harbor** = possível *motor de execução do benchmark* já existente, não sinônimo da capacidade de benchmark. O requisito é **ter benchmark real**, com Harbor **ou** o runner nativo já existente, adotando o de menor custo de integração verificável.

## 2. Arquitetura simples e prática: copiar arquivos, sem MCP obrigatório

```text
C:\dev\harness-engineering  (fonte versionada, catálogo, CLI, benchmark, relatórios)
  |  comando explícito e reversível: harnessctl attach
  +--> C:\dev\projeto-A\
  |      AGENTS.md / CLAUDE.md (só criados quando não existem)
  |      .agents/skills/<selecionadas>/SKILL.md  (Codex)
  |      .claude/skills/<selecionadas>/SKILL.md  (Claude)
  |      .harness/manifest.json (somente arquivos de propriedade do Harness)
  |
  +--> C:\dev\projeto-B\ (mesma estrutura, escolhas diferentes)
  |
  +--> ...outros projetos, instalados sob demanda

Codex/Claude Code continuam sendo executores NATIVOS no próprio projeto.
Benchmark roda no Harness (supervisor confiável), contra cópia descartável,
sem acesso do agente ao gabarito. JEV só via HTTPS direto quando habilitado.
```

### 2.1. Bootstrap simples: a skill pessoal `setup-harness` (DECISÃO R1)

**Decisão de produto:** distribuir um **bootstrap único** no escopo pessoal de cada executor, de modo que a skill possa ser descoberta **antes** de o repositório novo conter qualquer configuração Harness. A skill é uma instrução que invoca a CLI central `harnessctl.py`; **não duplica** código, skills, gabaritos, chaves, runtime, scripts de benchmark ou servidor MCP em cada projeto.

- Codex: instalar opcionalmente **uma vez** a skill em `~/.agents/skills/setup-harness/SKILL.md` (escopo USER conforme documentação de skills Codex). Invocation explícita `$setup-harness`; instalação pessoal só com autorização do operador.
- Claude Code: instalar opcionalmente **uma vez** em `~/.claude/skills/setup-harness/SKILL.md` (escopo pessoal Claude). Invocation explícita, normalmente `/setup-harness`; testar descoberta na versão instalada. Não alterar `~/.claude` sem autorização.
- Alternativa **sem instalar skill pessoal**: comando Python direto no terminal a partir de qualquer repositório, passando `--repo` explícito. Não depende de agentes, MCP, Node, hooks ou daemon. Essa é a rota de recuperação/automação confiável.
- A skill detecta contexto **apenas** para sugerir `--repo`; nunca escolhe silenciosamente outro repositório, não altera arquivos automaticamente e não dispara ao `git init` sem solicitação. "Preparação automática" significa um comando/skill, **não** um hook invasivo.
- Setup lê `git status`, identifica arquivos `AGENTS.md`, `CLAUDE.md` e skills presentes, verifica conflitos, gera plano, pede autorização para copiar **apenas** arquivos selecionados, verifica integridade e registra ownership no manifesto `.harness/manifest.json`. No uso diário, skills nativas são lidas pelo executor, não via servidor central. Copiar arquivos é suficiente para instalar **regras/skills locais**, mas **não** torna o cliente JEV HTTP uma ferramenta interativa automática em sessões Codex/Claude; ela continua no supervisor Python até existir caso de uso e adaptador aprovado.
- Atualizar em novos releases = `project-plan` de atualização → diff aprovado → `project-attach`/equivalente com hash → `project-verify`; `project-remove` limpa apenas os arquivos declarados e inalterados. Sem `git pull` implícito, `curl | bash`, `npx` ou symlink obrigatório.
- Contratos já existentes não são sobrescritos. A primeira versão pode **bloquear colisão** e emitir instruções de ajuste manual; composição/merge estruturado só em release específico, depois de testes de regressão.
- Não é necessário instalar Python ou Infisical **dentro** de cada projeto. O setup requer apenas Python funcional na máquina onde já roda o Harness; execução nativa de Codex/Claude exige suas CLIs/sessões normalmente disponíveis. Infisical é requerido só para operações que acessem segredos, não para a cópia de skills.

**Interface do operador quando R1 estiver implementado** (exemplos PROPOSTOS, não executáveis nesta revisão):

```powershell
# Uma vez por agente/dispositivo: instalar a skill pessoal setup-harness
# Em qualquer projeto novo:
$setup-harness               # dentro de Codex, ação explícita
# ou /setup-harness           # dentro de Claude Code
# ou sem skill, diretamente no PowerShell:
python C:\dev\harness-engineering\scripts\harnessctl.py project-plan --repo . --client codex
python C:\dev\harness-engineering\scripts\harnessctl.py project-attach --repo . --client codex --apply
python C:\dev\harness-engineering\scripts\harnessctl.py project-verify --repo .
```

**Gate adicional R1:** teste de ponta a ponta "repo novo vazio" (plan/copy/verify/detach) e "repo já existente com regras" (no overwrite), incluindo uma execução de `$setup-harness` após instalação pessoal **aprovada**, uma sessão Codex que descubra skill de projeto e rollback exato. Só depois afirmar setup diário pronto.

**Regra de distribuição:** cada projeto recebe **arquivos pequenos** e pinados. Não copiar toda a árvore do Harness nem seus scripts de benchmark, gabaritos, tokens ou servidor dentro de cada projeto. As skills podem ser copiadas (padrão mais simples); alterações são atualizadas mediante `plan` e aprovação. Não pressupor que links simbólicos funcionam ou que ambos clientes descobrem arquivos iguais; adaptar os destinos nativos por cliente.

**Regras de conflito:** se `AGENTS.md`, `CLAUDE.md`, `.agents/skills` ou `.claude/skills` já contêm arquivos de terceiros, não sobrescrever, não concatenar automaticamente e não reivindicar ownership. Apresentar plano/diff e escolher modo compatível por projeto. A limpeza remove apenas bytes que o manifesto comprovar serem propriedade da instalação, recusando arquivo modificado. Instalador atual `harnessctl.py` é restrito a `.poc/`; **os comandos de projeto abaixo são PROPOSTOS, ainda não implementados**.

**Interface proposta, sem criar novo binário:**

```powershell
python C:\dev\harness-engineering\scripts\harnessctl.py project-doctor --repo C:\dev\projeto-A --client codex
python C:\dev\harness-engineering\scripts\harnessctl.py project-plan --repo C:\dev\projeto-A --client codex
python C:\dev\harness-engineering\scripts\harnessctl.py project-attach --repo C:\dev\projeto-A --client codex --apply
python C:\dev\harness-engineering\scripts\harnessctl.py project-verify --repo C:\dev\projeto-A
python C:\dev\harness-engineering\scripts\harnessctl.py project-remove --repo C:\dev\projeto-A --apply
```

Nenhum comando `project-*` deve ser descrito como disponível antes de ser implementado/testado. Padrão leitura sem `--apply`; nenhum instalador global, hook persistente ou registro MCP sem consentimento explícito. **Copiar a skill não prova que o agente a executou.** Monitorar descoberta/invocação/comportamento em tarefa real.

## 3. Os quatro 80/20 que devem funcionar no primeiro release utilizável

| Capacidade essencial | Dor resolvida | Reuso primeiro | Critério objetivo para concluir |
| --- | --- | --- | --- |
| **Onboarding por cópia segura e rollback** | manter 10–20 configs manualmente | `harnessctl.py`, `templates/AGENTS.md`, `templates/CLAUDE.md`, hashes ECC | instalar/verificar/reverter no repo opt-in sem apagar trabalho existente; 2ª execução idempotente |
| **Codex nativo com QA direcionado** | código sem disciplina ou verificação; regressões | CLI Codex, `tdd-workflow` e `verification-loop` ECC, oráculo nativo do projeto | tarefa real altera código, passa critérios externos; skill descoberta/invocada quando aplicável, sem afirmar execução por presença de arquivo |
| **Benchmark de agentes/perfis real** | não saber qual modelo/harness trabalha melhor | `harness_eval.py`, `native_baseline.py`, oráculos/testes; avaliar Harbor no mesmo release por um spike breve | comparação A×B em tarefas cegas idênticas, ambiente reiniciado, resultados reproduzíveis; nenhuma medição sintética como adoção |
| **Telemetria + custo/tempo/qualidade** | gastar franquia e tempo sem saber efeito | campos existentes Codex/Claude e JEV, coletor/avaliador do Harness | relatório por tarefa/condição com cobertura de custo, consumo e qualidade; `null` onde ausente; veredito INCONCLUSIVO permitido |

**Só depois** expandir o pacote para auditoria Cloudflare, EGM, Warp, GStack e outros. Não requerer essas dependências para demonstrar os quatro itens.

## 4. Roadmap de releases com escopo, pré-requisitos e definição de pronto

| Release | Prioridade | Entrega (closed scope) | Dependências / saída |
| --- | --- | --- | --- |
| **R0 — Fundação reconciliada** | **P0, documentar AGORA** | esta SPEC + dossiê imutável no Git; marcar JEV HTTP como resolvido, custos parciais e PR Draft; CI | zero chamadas pagas, nenhuma edição de projeto alheio; **fonte canônica localizável pelo Codex** |
| **R1 — Uso diário mínimo (pacote nativo)** | **P0, IMPLEMENTAR PRIMEIRO** | `project-doctor/plan/attach/verify/remove`; copiar arquivos mínimos de skills+contrato; preservar arquivos existentes; 1 projeto opt-in | testes offline negativos (symlink, colisão, diretório arbitrário, modified-owned, sem secrets), 1 sessão Codex com mudança real e QA |
| **R2 — Benchmark + medição V1** | **P0, PARTE DO MVP, EM SEGUIDA** | `bench plan/run/report` reaproveitando avaliador/runner; A=Codex sem Harness vs B=Codex com Harness, tarefas reais e oráculo independente; uso/tokens/tempo/custos explícitos | 2 tarefas smoke gratuitas/limitadas quando possível; depois lote pré-registrado aprovado; relatório capaz de dizer GANHO/EMPATE/REGRESSÃO/INCONCLUSIVO |
| **R2-H — Decisão Harbor** | **P0, SPIKE DELIMITADO DENTRO DE R2** | verificar se Harbor CLI oficial executa Codex+Claude e mesmos casos, com ambiente seguro já disponível; escolher Harbor ou runner existente | no máximo uma prova sem gasto, documentar limitações Windows/Docker/servidores; **benchmark continua obrigatório mesmo se Harbor for rejeitado** |
| **R3 — Claude Code e comparação entre agentes** | P1 | `project-*` para Claude, sessão autenticada, orçamento, isolamento e benchmark próprio; comparação Codex×Claude em tarefas equivalentes | `PASS` ou `BLOCKED_AUTH/ISOLATION` factual; não usar resultado Codex para homologar Claude |
| **R4 — Roteamento JEV governado** | P1 | consumir `jev_http.py` no supervisor apenas para classes com valor; calibrar confidence/margin/fallback por tipo de tarefa | comparação J0/J1 separada, sem prometer economia ou substituição da programação por classificador; JEV padrão OFF até ganho comprovado |
| **R5 — Cloudflare + EGM + Warp** | P2 | Cloudflare guidance/validadores segurança sob demanda; EGM revisão fresca de specs complexas; Warp triagem/feedback revisado via PR | um módulo por lacuna, diffs, licença/SHA, sem multiplicar modelos/loops automaticamente |
| **R6 — Especializações e escala** | P3 | Superpowers debugging, GStack QA/review, wshobson skill isolada, Impeccable em UI; claude-mem/Skills Manager apenas se justificarem; catalogar 10–20 projetos | custo/compatibilidade medidos, isolamento, rollback; nenhum modo bypass, instalação global ou dupla escrita |

**Regra de sequência:** R1 e R2 são o produto essencial; R3 é paridade/escala; R4–R6 são otimizações. R0 está sendo documentado, **não** equivale a R1 ou R2 implementados. Cada release tem gate explícito e um PR/commit identificável. Não prometer prazo sem capacidade observada. Não criar múltiplas worktrees simultâneas para o mesmo checkout como conveniência.

## 5. Benchmark de agentes — requisito CENTRAL, não opcional

### 5.1 As perguntas que ele deve responder

1. **Harness agrega qualidade?** mesmo Codex/modelo/versão/tarefa em A=sem Harness e B=com pacote Harness. Depois repetir para Claude separadamente.
2. **Qual agente resolve melhor tarefas reais?** comparar Codex vs Claude com mesma especificação, oráculos, condições e orçamento. Como os modelos/assinaturas podem ser diferentes, **não atribuir exclusivamente ao modelo** diferenças que incluem runtime, ferramentas e custo.
3. **Qual entrega mais por recurso gasto?** taxa de tarefas aprovadas, segurança, duração, tokens, retrabalho, consumo de cota da assinatura, e custo de API faturado separadamente.
4. **JEV vale a pena em roteamento simples?** em J0/J1 **separado** do benchmark de software: cobertura de autoaceite, erros de alta confiança, fallbacks, latência, custos completos quando observáveis.

### 5.2 Desenho mínimo de experimento real

- **Dataset pré-registrado:** 8–12 casos curtos e representativos (bugs, pequena feature, testes, refatoração, debugging, segurança), amostrados de código real controlado ou mini-projetos com fixtures fiéis. Escolher primeiro 2 tarefas para ensaio de engenharia ponta a ponta, **não** repetir o smoke JEV. Fixar textos, versões, SHA inicial, duração máxima e custo permitido antes de rodar. Não editar gabarito pós-resultado.
- **Cegamento:** cada condição recebe cópia descartável **idêntica** do código inicial sem história Git contaminante, respostas anteriores, tokens de publicação ou oráculo oculto. O avaliador fora do sandbox roda testes e lê o gabarito. Nenhum agente pode modificar critérios para forçar PASS.
- **Pareamento:** as mesmas tarefas em A e B com modelo, esforço e limites iguais; ordem alternada/randomizada; avaliar diferenças por caso e por tipo. Codex vs Claude e modelos diferentes exigem comparação adicional identificada, não misturar com efeito de skills.
- **Métricas primárias:** `acceptance_pass` (verificador externo), regressões bloqueantes e `wall_seconds_per_accepted_task`. Métricas secundárias: tokens observados, tool calls, retries, rework, tempo humano se medido, custo API **faturado**, cota de assinatura **quando observável**; não converter plano fixo em dólar por chamada.
- **Preço e contabilização:** `cost_source=api_billed|subscription_quota|derived_estimate|unknown`; campo `cost_usd=null` em ausência de observação; `known_cost_subtotal` separado de `total_cost` e de `observed_count/expected_count`. Em fallback somar custos somente se **todas** as parcelas forem conhecidas. Valor `0` só se explicitamente observado.
- **Repetição e escala:** rodar primeiro 2 casos por condição somente após pré-requisitos; ampliar a lote de 8–12 em aprovação separada se qualidade/telemetria/isolamento funcionarem. Não lançar 30 casos só para produzir números. Repetir adicionalmente apenas para resolver variância, não para obter o resultado desejado.
- **Adotar/descartar:** zero defeitos críticos adicionais; resultado funcional não inferior ao baseline; melhoria em ao menos uma métrica de valor pré-registrada sem perda relevante nas outras; cobertura conhecida de métricas; risco e custo de implantação aceitáveis. **Se ambos passam tudo ou custos ficam desconhecidos, INCONCLUSIVO**, não anúncio de vitória.

### 5.3 Formato mínimo de evidência por execução

```json
{
  "schema_version": 1,
  "run_id": "generated-on-execution",
  "project_id": "fixture-or-approved-project",
  "task_id": "pre_registered",
  "initial_source_sha": "pinned",
  "condition": "A_NATIVE_OR_B_HARNESS",
  "client": "codex",
  "model": "record_runtime_value",
  "client_version": "record_runtime_value",
  "skills_discovered": [],
  "skills_invoked": [],
  "skills_behavior_observed": [],
  "acceptance": {"passed": null, "tests_passed": null, "tests_total": null},
  "security": {"negative_canaries_passed": null, "forbidden_effects": []},
  "usage": {"tokens_in": null, "tokens_out": null, "tool_calls": null},
  "finance": {
    "cost_source": "unknown",
    "api_billed_usd": null,
    "subscription_quota_observed": null,
    "known_cost_subtotal_usd": null,
    "total_cost_usd": null,
    "cost_observed_count": 0,
    "cost_expected_count": 1
  },
  "latency_ms": null,
  "retries": 0,
  "oracle_ref": "held_out",
  "outcome": "NOT_RUN",
  "evidence_kind": "NOT_RUN"
}
```

O exemplo é **schema proposto**, não execução real. Relatórios devem registrar também falhas e jobs cancelados; nunca omitir condições que gastaram recursos.

### 5.4 Harbor: componente sério, decisão pequena, sem inventar executor

A documentação [oficial do Harbor](https://github.com/harbor-framework/harbor) declara suporte a **Codex CLI e Claude Code**, datasets e adaptadores para avaliações em contêiner; pode executar localmente via Docker ou em provedores de sandbox. Essa é uma oportunidade de **reusar o motor**, em vez de recriar automação de agentes e avaliação. Não significa que Harbor já esteja integrado ou que Docker/WSL sejam pré-requisitos aprovados no Windows atual.

**Spike R2-H fechado:** (a) mapear interfaces entre `harness_eval.py` e tarefas/verificadores Harbor; (b) confirmar com documentação e um comando de descoberta sem cobrança qual executor/ambiente é utilizável; (c) comparar esforço de adoção e requisitos de isolamento; (d) **decidir uma única rota**: Harbor para execução + nosso verificador/política, **OU** runner já existente com formato de evidência compatível. Sem clonar o Harbor no núcleo, sem criar terceiro runner ou adicionar 50 bibliotecas. Se a integração exigir mudança de infraestrutura desproporcional, marcar `DEFER_HARBOR` e executar o benchmark no runner nativo já demonstrado.

## 6. Dossiê consolidado: destino obrigatório dos 12 candidatos

*Alta relevância do dossiê significa potencial de valor, não autorização de instalar tudo. Preservar fonte, hash, licença, dependências e modo de atualização em cada PR.*

| Upstream | Dor que resolve | Componente que aproveitamos | Release / decisão |
| --- | --- | --- | --- |
| [ECC](https://github.com/affaan-m/ECC) | TDD/QA repetidos inconsistentes | `tdd-workflow`, `verification-loop` pinados; ciclo de arquivo já funciona em sandbox | **R1 essencial**, reusar somente 2 |
| [Harbor](https://github.com/harbor-framework/harbor) | comparação de agentes e modelos com ambiente reproduzível | runner/adapter/datasets, se compatível com políticas existentes | **R2-H, avaliação obrigatória da alternativa** |
| [jev-code](https://github.com/FrancoisChastel/jev-code) | classificações estruturadas baratas | sem MCP/Node; referência da política, nosso `jev_http.py` HTTPS | funcional em piloto; otimização **R4** |
| [Cloudflare security-audit-skill](https://github.com/cloudflare/security-audit-skill) | segurança sem cobertura/rastreio | guidance/ledger/schema/validadores sob demanda | R5, parcial |
| [Google Elephant-Goldfish Model](https://github.com/google/elephant-goldfish-model) | especificação enviesada/não criticada | draft/review/resolve/drift em mudanças arquiteturais | R5, parcial e opt-in |
| [Warp cloud-factory-demo](https://github.com/warpdotdev-demos/cloud-factory-demo) | triagem e aprendizado de correções perdidos | estados de issue, feedback revisado | R5, padrões; sem fábrica Oz |
| [Superpowers](https://github.com/obra/superpowers) | debugging por tentativa e erro | `systematic-debugging`, `receiving-code-review` | R6, seletivo, sem worktrees extras |
| [GStack](https://github.com/garrytan/gstack) | revisão de produto/QA comportamental | módulos review/qa após comparar nativo/ECC | R6, sem pacote inteiro |
| [wshobson/agents](https://github.com/wshobson/agents) | skills especializadas ausentes | uma skill isolada por déficit | R6, catálogo |
| [Impeccable](https://github.com/pbakaus/impeccable) | UI genérica e falhas de UX | auditoria/detector em projeto frontend | R6, por projeto; proibir bypass |
| [claude-mem](https://github.com/thedotmack/claude-mem) | perda de contexto entre sessões | padrões de busca/memória após checar duplicação com Core | R6, condicional |
| [Skills Manager](https://github.com/xingkongliang/skills-manager) | distribuição de muitos plugins/skills | interface opcional, sem dupla autoridade de escrita | R6, só se escala justificar |

**Fora do núcleo nesta etapa** (documentados no dossiê original): Warp factory-agents-template, T3 Code (UI opcional), JetBrains thinkrail, hallmark, taste-skill, TradingAgents, everything-gemini, jev-classifier, jev-skills e typesafe-ai/skills. Nenhum se torna dependência implícita.

## 7. Segurança, autorização e governança

- **Supervisor confiável** retém chaves Infisical e faz HTTPS para JEV; agentes e workspaces de benchmark não recebem valores de chaves, home, SSH, cookies, arquivos de gabarito ou conteúdo privado desnecessário.
- **Canários negativos** devem provar que sandbox realmente nega leitura/escrita/rede/Git quando essa é a política declarada. `MXC_OK` ou CI offline sozinhos não equivalem a homologação integral; exigir evidência por execução e por cliente.
- **Escritas reais** somente com caminho `--repo` explícito, plano visualizável, backup/ownership/rollback; sem hook global silencioso; `git push`, merge, deploy, install externo e despesas requerem aprovação explícita, não deduzida de um pedido geral de documentação.
- **Não herdar** `NODE_OPTIONS`, `OPENROUTER_API_KEY`, `TYPESAFE_API_KEY` ou demais tokens para processos agentes; os novos comandos não devem imprimir ambientes, payloads privados ou custos não observados.
- **Licenças e reuso:** upstream verificado por SHA/release/licença dos **arquivos concretos usados**. Não copiar código de projetos com licença desconhecida; importar só componentes necessários, com controles de atualização.
- **Sem testes pelo teste:** pré-flight grátis para confirmar execução; um piloto pago apenas quando o objetivo não puder ser comprovado sem API; falha repetida significa **parar e corrigir hipótese/arquitetura** antes de rodar novamente.

## 8. Regra antipadrão JEV/Node — processo de decisão para qualquer integração

**Antes de escrever um adaptador:**
1. **Objetivo em uma frase:** qual operação precisa fazer, e por quem? Ex.: “classificar uma tarefa remotamente”.
2. **Busca reutilização em ordem:** capacidade nativa → API HTTPS oficial → SDK/CLI oficial → protocolo MCP se ferramenta precisar ser invocada pelo agente → repositório auxiliar → código novo mínimo.
3. **Escolha comprovada:** registrar endpoint/contrato, autenticação, resposta, permissões, custo e limites. Se API direta atender, **proibido instalar serviço local adicional para a mesma função sem justificativa**.
4. **Uma prova mínima:** teste sem cobrança da forma/contrato; depois uma chamada real autoral delimitada se necessária, registro da resposta sanitizada.
5. **Critério de parada:** se teste falhou, classificar se é contrato, integração ou infraestrutura; **não começar sequência de tentativas em runtime lateral** sem novo indício causal. Preservar evidência e corrigir menor peça.
6. **Só depois** implementar logs, gates e integração por projeto. Qualquer mudança de arquitetura precisa ADR com alternativa rejeitada e razão.

Aplicar a mesma regra a Harbor, Cloudflare, EGM, Skill Manager e memória: não integrar “porque existe” nem porque tem estrelas.

## 9. Backlog executável (HE-OP): o que Codex deve fazer em cada fase

| ID | Release | Arquivos/capacidade | Teste obrigatório | Encerramento |
| --- | --- | --- | --- | --- |
| HE-OP-00 | R0 | esta SPEC, dossiê original, README indexando canônico; status do PR | links abrem, revisão contra HEAD, CI não afetado | **DOCUMENTAÇÃO** |
| HE-OP-01 | R1 | estender `scripts/harnessctl.py` com `project-doctor` + `project-plan`; leitura do projeto sem escrita | repo externo fixture, arquivos existentes, path/symlink/sem secrets | **NEXT TO IMPLEMENT** |
| HE-OP-02 | R1 | `project-attach/verify/remove` + manifesto ownership | aplica, reaplica, recusa colisão, detecta alteração e reverte exato | R1 arquivo |
| HE-OP-03 | R1 | operação Codex em projeto controlado com skill selecionada e verificador externo | descoberta + invocação + comportamento + QA, sem dados de origem vazados | R1 diário |
| HE-BENCH-01 | R2 | adaptar `harness_eval.py` e runners nativos ao formato A/B de programação; corpus pré-registrado | dois patches de software avaliados, sem JEV; mesmo SHA inicial | R2 runner |
| HE-BENCH-02 | R2 | telemetria/aggregator/relatório por tarefa e condição | custo parcial null, quota separada, regressões, medidas observadas | R2 medição |
| HE-BENCH-H | R2-H | Harbor: compatibilidade de agente, ambiente, verificadores | decisão HARBO​R_USE ou DEFER_HARBOR, com prova de reuso e custo | R2 decisão |
| HE-BENCH-03 | R2 | ensaio A/B Codex controlado; lote adicional se autorizado | reporte GANHO/EMPATE/REGRESSÃO/INCONCLUSIVO auditável | **MVP COMPLETO** |
| HE-OP-04 | R3 | pacote Claude e homologação runtime | sessão real ou motivo verificável de BLOCKED | multi-cliente |
| HE-OPT-01 | R4 | JEV em perfil de roteamento opt-in | decisão J0/J1, custo e falso positivo, sem segredos | só ativar com ganho |
| HE-OPT-02 | R5+ | Cloudflare/EGM/Warp + candidatos R6 | comparar baseline, licença, integração reversível | um PR por módulo |

O agente deve preferir arquivos existentes; os nomes `project-*` são proposta de interface, não executáveis ainda. **Não partir desta SPEC para imediatamente instalar 12 repos ou executar N=30.**

## 10. Release gates (objetivos e verificáveis)

**Gate R0 DOCS:** dois arquivos canônicos no GitHub (esta SPEC + dossiê histórico), README aponta para eles, estado atual está correto. CI offline não regrediu. Nenhuma mudança nos projetos consumidores.

**Gate R1 USO DIÁRIO:** `project-plan` read-only; instalação Codex no projeto opt-in sem sobrescrever arquivos, verify e rollback exatos; leitura/invocação quando apropriado; um patch de software com QA externo. Sem secrets, hooks globais nem registrar sucesso baseado apenas em arquivo copiado.

**Gate R2 BENCHMARK (obrigatório para dizer “Harness V1 pronto”):** execução A/B reproduzível em pelo menos dois casos reais controlados, relatório de critérios de aceitação, regressões, latência, tokens, gastos/cotas conhecidos ou `null`, registros de tentativas e justificativa Harbor USE/DEFER. O resultado pode ser **INCONCLUSIVO** em economia; isso não impede que o mecanismo de medição seja considerado funcional, mas impede alegar otimização financeira comprovada.

**Gate R3 PARIDADE:** sessão Claude autorizada com testes próprios, ou status `BLOCKED` sem prometer portabilidade não verificada.

**Gate R4+ ADOÇÃO:** nova capacidade ativada somente se aumenta qualidade/eficiência ou fecha lacuna não coberta, sem derrubar gates anteriores.

## 11. Ordem de serviço CODEx — primeira implementação sem desvios

> **Execute HE-OP-01 na branch de trabalho do Harness, não em outro projeto.** Antes de escrever: `git status --short`, `git branch --show-current`, `git fetch origin`, comparar HEAD com remoto, PR #4, testes e documentação. Não reconciliar conflito por `reset --hard` e não criar worktrees novas por conveniência. Se a worktree tiver alterações desconhecidas ou divergência, **pare e registre**, não apague.
>
> Fonte normativa: `docs/HARNESS_SPEC_CANONICA_USO_DIARIO_E_BENCHMARK_V1.md`; histórico: `docs/reference/CONSOLIDADO_REPOSITORIOS_HARNESS_ENGINEERING_2026-11-02.md`. Revise `scripts/harnessctl.py`, `config/approved_skills.json`, `templates/AGENTS.md`, `templates/CLAUDE.md` e testes. Reutilize funções para caminho, hash, ownership e erro; não crie orquestrador, contêiner novo, banco, HTTP local, Node ou MCP.
>
> **Entrega exata deste turno:** implementar `project-doctor` e `project-plan` **somente-leitura** para um `--repo` explícito, com `--client codex`, exibindo arquivos novos, conflitos, compatibilidade e bloqueios, sem copiar nada e sem acessar secrets. Preservar comportamento anterior `.poc` e compatibilidade dos comandos existentes. Adicionar testes offline positivos/negativos. Se o ambiente de projeto exigir decisão sobre arquivo existente, marcar `BLOCKED_COLLISION` e apresentar plano; não sobrepor. Não tocar Resiplac Core, MarketOS, Forja, Nexus Quant nem `main`.
>
> **Auditoria antes de finalizar:** executar testes direcionados + suíte offline, `git diff --check`, revisar diff e conferir que nenhum recurso prometido existe só no texto. Relatar SHA, comandos reais, resultados, lacunas e próximo item **HE-OP-02**. Commit/push apenas na branch autorizada, sem merge; nenhuma chamada paga ou instalação global. Encerrar após entrega, sem avançar para outra release automaticamente.
>
> **R2 é requisito obrigatório e já tem backlog**: após HE-OP-02/03, implementar HE-BENCH-01/02/H/03 antes de marcar Harness V1 pronto. Evitar a armadilha de chamar “benchmark” o antigo piloto de três classificações JEV.

## 12. Perguntas respondidas, decisões fechadas e fontes

- **“Só copiar um diretório?”** Para regras/skills, essencialmente sim: `AGENTS.md`, `CLAUDE.md`, as pastas nativas de skills e um manifesto de ownership. O gestor é a cópia segura, verificável e reversível; não precisa de MCP.
- **“JEV roda localmente?”** Não; o modelo remoto recebe HTTPS. `jev_http.py` funciona e foi validado. O processo MCP/Node é legado opcional, fora do caminho principal.
- **“Harbor é obrigatório?”** **Benchmark é obrigatório.** Harbor tem prioridade de avaliação no R2 porque é reutilização madura; instalação só se simplificar a execução no ambiente realmente disponível. Runner nativo permanece fallback de infraestrutura, não regressão de escopo.
- **“O Harness já está pronto?”** **Não para uso universal.** R0 documentação/CI e piloto JEV estão operacionais; R1/R2 ainda precisam ser implementados e testados em projeto real.
- **“Modelo mais barato?”** JEV só classifica; não escolher modelo por ranking público. Benchmark por tarefa/aceite precisa evidenciar qualidade/latência/custo/assinatura antes de fazer roteamento de modelos.
- **“Como trabalhar amanhã?”** primeiro executar HE-OP-01 e HE-OP-02/03 na branch; depois benchmark real R2. Não distribuir pacote global antes de R1.

**Fontes internas:** [README](../README.md), [Manual](MANUAL_HARNESS_V1.md), [Protocolo de avaliação](PROTOCOLO_VALIDACAO.md), [dossiê original](reference/CONSOLIDADO_REPOSITORIOS_HARNESS_ENGINEERING_2026-11-02.md), [PR #4](https://github.com/Williamitiro/harness-engineering-platform/pull/4), [Issue #3](https://github.com/Williamitiro/harness-engineering-platform/issues/3).  
**Fonte externa Harbor (consulta de documentação, não teste de execução):** https://github.com/harbor-framework/harbor ; opção Docker local ou provedores sandbox documentados; não presumir compatibilidade instalada com Windows.  
**Critério de verdade contínua:** logs e código executado prevalecem sobre títulos, claims antigos e propostas. As frases “proposto”/“não implementado” não podem ser omitidas em status de release.
