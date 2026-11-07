# Dossiê de adoção de repositórios open source — Harness Engineering

**Data de corte:** 02/11/2026  
**Projeto:** [`Williamitiro/harness-engineering-platform`](https://github.com/Williamitiro/harness-engineering-platform)  
**Natureza:** inventário técnico consolidado, análise de aderência, priorização e plano de adoção controlada.  
**Decisão:** **integração seletiva; não criar outro harness, runtime ou orquestrador.**

> **Importante:** “Alta relevância” significa que o projeto oferece uma solução potencialmente útil a uma dor concreta do Harness. **Não** significa instalação aprovada, ganho empírico comprovado, segurança homologada ou incorporação automática de todo o repositório. A classificação separa relevância estratégica, oportunidade de reuso e autorização para executar.

## 1. Resumo executivo

O Harness Engineering foi concebido para aumentar a qualidade verificável, segurança e eficiência de **Codex CLI** e **Claude Code**, preservando seus runtimes nativos. Seu papel é selecionar capacidades reutilizáveis, fixar versões e hashes, estabelecer contratos mínimos, executar verificações independentes e registrar evidências. O próprio manual rejeita um novo framework multiagente, cópias indiscriminadas de skills, autoavaliação circular e testes sintéticos tratados como resultados de produção.

As análises consolidadas abrangem: o vídeo **“Software Engineering Is Becoming Factory Engineering”** (Warp/Zach Lloyd), o vídeo **“Top 10 GitHub Repos This Week | Oct 26 – Nov 1 | Agents Learn Taste”**, estudos prévios de ECC, Harbor, GStack, Skills Manager, wshobson/agents e Elephant-Goldfish Model e a auditoria do piloto Jev/TypeSafe. As decisões foram cruzadas com `README.md`, `docs/MANUAL_HARNESS_V1.md`, `docs/UPSTREAM_REUSE.md`, `docs/DECISOES_E_RISCOS.md`, `docs/JEV_DECISAO.md`, `config/approved_skills.json` e PR #4 no GitHub.

**Decisão principal:** manter **ECC** como fonte já aprovada de componentes selecionados; acrescentar, após destravar o fluxo atual, **auditoria especializada da Cloudflare**, **revisão adversarial de especificações do EGM** e **mecanismos leves de triagem/feedback da Warp**. **GStack** e **Superpowers** são bibliotecas complementares para lacunas pontuais. **Harbor**, **Jev**, **claude-mem**, **Skills Manager** e **wshobson/agents** são candidatos condicionais: resolvem dores reais, mas possuem pré-requisitos ou sobreposição que impedem instalação automática. **Impeccable** é altamente útil nos *projetos de interface*, não no núcleo do Harness.

**Bloqueio operacional em 02/11/2026:** o piloto pareado A/J com Jev ainda não demonstrou classificação real concluída. Conforme o relato operacional mais recente, houve falha na inicialização do processo local JEV, sem mensagem causal preservada; isso não constitui evidência de rejeição da chave OpenRouter. O **PR #4 permanece Draft**. Resolver observabilidade do bootstrap e reconciliar o estado local/remoto vem antes de adicionar dependências ou repetir ensaios pagos. Os testes offline e o `MXC_OK` não comprovam, por si, a conclusão de G1 nem o funcionamento ponta a ponta do JEV.

## 2. Matriz única de seleção

**Legenda de decisão:** `MANTER` = já selecionado e controlado; `INTEGRAR PARTE` = aproveitar módulo/skill/padrão específico, com revisão; `CANDIDATO GATED` = valor claro, mas depende de pré-condições; `FORA DO NÚCLEO` = usar no produto de destino, não como dependência do Harness. **P0** = corrigir bloqueio corrente; **P1** = próxima evolução aprovada; **P2** = somente se lacuna não atendida; **P3** = horizonte condicionado.

| # | Repositório | Dor / problema real que resolve | Componente a aproveitar | Grau e modalidade | Prioridade / decisão |
|---|---|---|---|---|---|
| 1 | **[ECC — Everything Claude Code](https://github.com/affaan-m/ECC)** | Agentes não recebem procedimento consistente; skills não necessariamente são descobertas/invocadas; regressão em TDD e verificação. | `tdd-workflow`, `verification-loop`, eventualmente outras skills somente após medição. | **Alta — parcial, já implementada** | **P0: MANTER**, sem importar catálogo completo |
| 2 | **[Cloudflare security-audit-skill](https://github.com/cloudflare/security-audit-skill)** | Auditorias de segurança superficiais, achados não reproduzíveis, lacunas de cobertura e falsos positivos em fronteiras de confiança. | Modo *guidance*, `AI-AND-LLM.md`, classes de ataque, `report-schema.json`, validadores e ledger. | **Alta — parcial, com skill dedicada sob demanda** | **P1: INTEGRAR PARTE** após sandbox validado |
| 3 | **[Google Elephant-Goldfish Model (EGM)](https://github.com/google/elephant-goldfish-model)** | Especificações incorretas por viés do mesmo agente/contexto; decisões implícitas e divergência entre design e código. | `egm-draft`, `egm-review`, `egm-resolve`, `egm-drift-report` em alterações arquiteturais. | **Alta — parcial e opt-in** | **P1: INTEGRAR PARTE** em tarefas complexas |
| 4 | **[Warp cloud-factory-demo](https://github.com/warpdotdev-demos/cloud-factory-demo)** | Issues entram sem triagem ou critérios de pronto; correções humanas não viram melhoria durável das skills. | Estados de triagem; `PRODUCT.md`/`TECH.md`; coleta de feedback de revisão e proposta de atualização de skill via PR. | **Alta — padrões/módulos, sem Oz obrigatório** | **P1: INTEGRAR PARTE**, sem fábrica autônoma |
| 5 | **[GStack](https://github.com/garrytan/gstack)** | Falta de revisão crítica com perspectiva de produto, QA comportamental e revisão de PR orientada à produção. | Comparar `review`, `qa` e funções pontuais com funcionalidades nativas e ECC. | **Alta para revisão/QA; sobreposição elevada** | **P2: SELETIVO**, não instalar pacote inteiro |
| 6 | **[Superpowers](https://github.com/obra/superpowers)** | Correções apressadas, debugging por tentativa e erro e conclusão de tarefas sem prova. | Principalmente `systematic-debugging`, `receiving-code-review`, verificação quando houver lacuna comprovada. | **Alta conceitual; sobreposição elevada** | **P2: SELETIVO**, não impor fluxo completo |
| 7 | **[Harbor](https://github.com/harbor-framework/harbor)** | Não existe garantia empírica de que uma skill melhora resultado, custo e tempo frente ao baseline. | Runner de benchmark em contêiner, adapters de agentes, datasets e execução reproduzível. | **Alta como infraestrutura experimental; condicional** | **P2/P3: CANDIDATO GATED** |
| 8 | **[jev-code](https://github.com/FrancoisChastel/jev-code)** | Classificações simples em lote podem consumir agente caro e gerar decisões pouco estruturadas. | MCP stdio consultivo: `jev_classify`, `jev_check`, `jev_score`, `jev_rank`, `jev_ask`. | **Alta para piloto A/J; não homologada** | **P0: DIAGNOSTICAR**; sem adoção antes de resultado real |
| 9 | **[claude-mem](https://github.com/thedotmack/claude-mem)** | Perda de decisões e contexto entre sessões de Codex/Claude, retrabalho e repetições. | Captura seletiva, síntese e busca de observações com políticas de privacidade; não duplicar segundo cérebro. | **Alta funcional; condicional em dados/custos** | **P2/P3: CANDIDATO GATED** |
| 10 | **[wshobson/agents](https://github.com/wshobson/agents)** | Lacunas especializadas em tarefas de código e dificuldade de portabilidade de skills entre clientes. | Skills ou plugins individuais não existentes no ECC/nativo; matriz de compatibilidade por harness. | **Alta como catálogo de componentes, não como instalação global** | **P2: SELETIVO** |
| 11 | **[Skills Manager](https://github.com/xingkongliang/skills-manager)** | Inventário e distribuição de skills em múltiplas ferramentas ficam difíceis quando o catálogo cresce. | Interface de catálogo, presets, inspeção de fontes, snapshots e sincronização controlada. | **Alta apenas se escala justificar; ferramenta externa** | **P3: CANDIDATO GATED**; sem concorrência com `harnessctl` |
| 12 | **[Impeccable](https://github.com/pbakaus/impeccable)** | Interfaces geradas por agentes parecem genéricas; problemas de UX/responsividade/acessibilidade passam sem inspeção. | Detector determinístico, `critique`, `audit` e regras auditáveis para UI. | **Alta para produtos com UI — fora do núcleo** | **P2: FORA DO NÚCLEO** (MarketOS/Core/Forja) |

**Interpretação:** os itens 1–6 são os mais diretamente conectados à qualidade do trabalho de engenharia. Os itens 7–11 têm relevância alta **sob condições específicas** — não devem inflar o escopo sem evidência. O item 12 deve ser considerado **no repositório de destino que possui interface**, sem dependência global do Harness.

## 3. Fichas técnicas: problema, ganho esperado, limites e integração

### 3.1 ECC — fonte principal já selecionada

- **Problema que resolve:** falta de procedimentos consistentes e reaproveitáveis em programação assistida por agente.
- **O que agrega:** skills documentadas para TDD, verificação, revisão e outras especialidades; técnicas de *progressive disclosure*.
- **O que temos:** `config/approved_skills.json` fixa ECC em **`b38be6a7f6350964d59328b52f0624e1d1d552d1`**, com apenas **`tdd-workflow`** e **`verification-loop`**; `scripts/harnessctl.py` oferece planejamento, instalação, verificação e remoção com controles de hash e colisão.
- **Sobreposição:** é a principal base; integrar Superpowers/GStack integralmente sobre ECC cria instruções concorrentes.
- **O que fazer:** manter o piloto selecionado e preservar a distinção `FILE_PRESENT` → `DISCOVERED` → `INVOKED` → `BEHAVIOR_OBSERVED` → `OUTCOME_VERIFIED`. Só adicionar nova skill com déficit observado e melhoria mensurável.
- **Critério de aceite:** skill de fato invocada, evidência independente, manutenção de invariantes de segurança, resultado melhor ou ao menos não inferior, custo e latência conhecidos.
- **Decisão:** **MANTER PARCIAL**, jamais instalação em massa.

### 3.2 Cloudflare Security Audit Skill — especialização de segurança

- **Problema que resolve:** relatórios vagos de segurança e confusão entre suspeita, vulnerabilidade confirmada e evidência ausente.
- **Como funciona:** seis fases; ledger de cobertura, verificação por agente independente, resultados estruturados em `confirmed` / `needs_validation` / `rejected`, validação dos JSON por scripts determinísticos.
- **Reuso concreto:** `skills/security-audit/AI-AND-LLM.md`, `ATTACK-CLASSES.md`, `report-schema.json`, `validate-findings.cjs`, `validate-coverage-ledger.cjs`; eventualmente a skill de **guidance**, sem toda a fábrica.
- **Dor específica do Harness:** segurança de MCP, prompt injection, segredos/ambientes, contaminação de oráculos, fronteira supervisor confiável versus processos de tarefa, validação de achados.
- **Cuidado:** modo de auditoria integral pode abrir diversas ondas de agentes; o próprio upstream requer sandbox com rede, sistema de arquivos e recursos restritos. **Sem sandbox: apenas análise estática, nunca executar código alvo.**
- **Aceite:** relatório com rastro de fonte e estado de confirmação, sem efeitos colaterais, sem classificações de gravidade especulativas; não exigir auditoria integral para cada patch.
- **Decisão:** **INTEGRAR PARCIAL**, depois do desbloqueio atual.

### 3.3 Google Elephant-Goldfish Model — especificações criticadas sem viés da conversa

- **Problema que resolve:** um único agente entrevistar, planejar, validar e implementar tende a reutilizar as próprias premissas; a especificação parece coerente, mas contém lacunas não questionadas.
- **Como funciona:** agente com contexto (**Elephant**) elabora design; revisores com contexto fresco (**Goldfish**) criticam hipóteses antes da implementação. Há fluxos de `bootstrap`, `brainstorm`, `draft`, `review`, `resolve` e `drift-report`.
- **Reuso concreto:** revisão independente de `SPEC.md`, decisões arquiteturais importantes e comparação *spec vs code*; não exigir execução para correções triviais.
- **Sobreposição:** revisões e oráculos existentes; o EGM acrescenta principalmente **crítica de design antes de programar**, não substitui QA de código.
- **Custo/risco:** múltiplos revisores podem consumir tokens; estabelecer orçamento e limite de rodadas.
- **Aceite:** encontrar defeitos reais na especificação, resolvidos pelo responsável, evitando revisões circulares e sem gerar documentos redundantes.
- **Decisão:** **INTEGRAR PARCIAL sob demanda**. Fonte upstream oficial confirmada: `google/elephant-goldfish-model` (não confundir com bibliotecas de Gemini de terceiros).

### 3.4 Warp Cloud Factory Demo — fluxo leve de triagem e aprendizado

- **Problema que resolve:** pedidos ambíguos não têm rota de decisão; feedback de revisão se perde, repetindo erros nas próximas PRs.
- **Reuso concreto 1 — triagem:** estados `Ready to implement`, `Ready to spec`, `Needs info`, `Wait to implement`; ligação explícita entre Issue, especificação, implementação, revisão e critérios de aceite.
- **Reuso concreto 2 — feedback:** o demo contém skill/fluxo de coleta de correções humanas em revisões de PR, identificação de regra durável e **proposta de PR para atualizar skill**. Manter revisão/aprovação humana; nunca autoaplicar nem automesclar política.
- **Reuso concreto 3 — QA funcional:** a ideia de verificar comportamento observável pode ser aplicada nos projetos com browser/GUI usando ferramentas já disponíveis.
- **Sobreposição:** o Harness já trata validação independente e PRs. Não precisamos introduzir Oz, Jira, Slack, serviço de orquestração nem cadeias automáticas de agentes.
- **Limites:** o repositório é um **demo** (MIT, último push identificado em agosto de 2026); monitoramento pós-deploy aparece na visão geral, mas não deve ser considerado entregue ponta a ponta.
- **Aceite:** cada issue tem decisão rastreável, cada correção reutilizada passa por revisão, nenhuma implantação/merge automático e nenhum custo recorrente invisível.
- **Decisão:** **APROVEITAR PADRÕES E SCRIPTS ESPECÍFICOS**, não copiar a fábrica.

### 3.5 GStack — revisão de produto, PR e QA

- **Problema que resolve:** revisão puramente sintática e testes verdes não garantem comportamento esperado nem experiência funcional.
- **Potencial de reuso:** fluxos de `review`, `qa` e planejamento crítico; revisão de implementação contra objetivo de produto.
- **Sobreposição:** ECC, testes nativos e componentes de QA já adotados. Determinadas rotinas `ship` podem fazer commits/PRs; isso requer política de autorização explícita.
- **Cuidado de instalação:** upstream descreve Node/Bun e capacidades diferentes por host; no Codex o nível declarado é **experimental**, enquanto Claude tem suporte mais completo. O modo team tem atualização automatizada — incompatível com a regra de pinning se habilitado indiscriminadamente.
- **Aceite:** detectar falhas reais adicionais em uma amostra controlada **sem** duplicar revisores ou modificar globais.
- **Decisão:** **COMPARAR MÓDULOS ISOLADOS**. Não instalar GStack inteiro por padrão.

### 3.6 Superpowers — debugging e disciplina de execução

- **Problema que resolve:** o agente pula para correções sem diagnóstico, não checa o resultado e declara conclusão precoce.
- **Reuso concreto:** `systematic-debugging`, `receiving-code-review` e possíveis práticas de verificação de conclusão.
- **Sobreposição:** `tdd-workflow`, `verification-loop`, planos e regras do próprio Harness já atendem partes grandes do pacote.
- **Cuidado:** o fluxo padrão favorece investigação, aprovação de design, TDD detalhado, delegação e revisão; isso pode aumentar custo/latência em tarefas simples. `using-git-worktrees` conflita com a atual preferência operacional de evitar múltiplas árvores de trabalho no repositório ativo.
- **Aceite:** menos tentativas até identificar causa-raiz em incidentes reais, sem aumentar desproporcionalmente o número de chamadas.
- **Decisão:** **SELEÇÃO PONTUAL**; rejeitar instalação global da metodologia inteira.

### 3.7 Harbor — executor independente de benchmarks

- **Problema que resolve:** ausência de comparações reais reproduzíveis entre baseline e configuração com skills, especialmente em tarefas multietapas.
- **Como funciona:** executa agentes em ambientes isolados e datasets; apoia Codex e Claude Code, entre outros, e está associado ao Terminal-Bench.
- **O que podemos reutilizar:** formato de tarefas/ambientes, execução padronizada, coleta de resultados e separação entre agente e avaliação.
- **Sobreposição:** `harness_eval.py` e scripts locais de benchmark já existem. Harbor só se justifica se oferecer **isolamento/portabilidade/repetibilidade** que não podemos obter com a via nativa aprovada.
- **Dependências e riscos:** exemplo local do upstream usa Docker. **Não impor WSL** ao operador por causa dessa ferramenta; avaliar compatibilidade Windows ou fornecedor isolado somente se necessário, com custo autorizado.
- **Aceite:** A×C ou A×J pareados e cegos, custo total real, diferença de qualidade independente e rollback, comparados com o runner existente.
- **Decisão:** **CANDIDATO DE INFRAESTRUTURA EXPERIMENTAL**, não trocar o executor atual agora.

### 3.8 jev-code — classificação consultiva A/J, sem substituir o agente

- **Problema que resolve:** muitas decisões de classificação/ranqueamento simples podem consumir chamadas longas de modelos generativos e produzir saídas pouco estruturadas.
- **O que entrega:** MCP stdio e cinco operações consultivas para classificar, checar, pontuar e ranquear evidências; usa modelo remoto Jev/TypeSafe via endpoint configurado.
- **O que já temos:** `scripts/jev_adapter.py`, contratos MCP, tarefas cegas, holdout independente, métricas e piloto pareado preparados. A documentação fixa candidato `jev-code` v0.5.0; o benchmark sintético **não prova superioridade** e está explicitamente marcado como simulação.
- **Problema atual:** no ensaio relatado, o processo local não respondeu à inicialização e o adaptador reduziu falhas diferentes a `JEV_ERROR`; não houve classificação A/J. Antes de novos gastos, preservar **fase, stderr saneado, tipo de erro, código de saída, timeout e comando/versão sem segredos** para diferenciar falha de spawn, encerramento prematuro e erro de protocolo. Não presumir erro na chave OpenRouter.
- **Aceite:** bootstrap gratuito do processo e handshake verificável; G1 seguro; somente então piloto **limitado** com respostas reais e comparação contra baseline, latência e custo; sem conclusões por outputs sintéticos.
- **Decisão:** **DIAGNOSTICAR/CORRIGIR O BLOQUEIO ATUAL**, manter candidato; **não declarar adotado**.

### 3.9 claude-mem — continuidade operacional entre sessões

- **Problema que resolve:** contexto de uma sessão desaparece quando o agente fecha; correções e decisões são repetidas.
- **O que entrega:** hooks de captura, síntese de observações, pesquisa e reinjeção de contexto; integração documentada com vários clientes.
- **O que podemos aproveitar:** separação entre evento bruto, resumo e busca seletiva; histórico por projeto; referências às decisões anteriores.
- **Sobreposição:** possível colisão com o Segundo Cérebro do Resiplac Core e mecanismos nativos de memória/histórico. **Não sincronizar automaticamente históricos de repositórios ou segredos com serviço externo.**
- **Riscos:** instala serviços/hooks e possui caminhos de observação hospedada e provedores de IA; verificação de fluxo de dados, consentimento, retenção, filtros de segredos, custos e modo exclusivamente local quando exigido.
- **Aceite:** recuperar decisões corretas sem vazamento, degradação de performance ou alteração não autorizada de configurações globais.
- **Decisão:** **PILOTO LOCAL/SANITIZADO SOMENTE SE A DOR PERSISTIR**; não empilhar vários sistemas de memória.

### 3.10 wshobson/agents — catálogo complementar multi-harness

- **Problema que resolve:** demandas especializadas em Python, JS/TS, segurança e revisão podem não estar cobertas pelas duas skills ECC selecionadas.
- **O que entrega:** catálogo amplo de agentes, skills, comandos e plugins com rotas de compatibilidade distintas por cliente.
- **Reuso concreto:** **um item específico por lacuna validada**, com preferência por skill sem hooks pesados, script de instalação global ou múltiplas dependências.
- **Sobreposição:** altíssima com ECC/GStack/Superpowers; source skill não equivale automaticamente a plugin executável com a mesma capacidade em todos os clientes.
- **Aceite:** registro de dono, SHA, licença, dependências, nível de descoberta/invocação/resultado e remoção segura.
- **Decisão:** **FONTE SECUNDÁRIA DE COMPONENTES**, não nova base do Harness.

### 3.11 Skills Manager — gestão de catálogo ao crescer

- **Problema que resolve:** distribuição manual e divergente de skills em ferramentas e projetos.
- **O que entrega:** biblioteca central, presets, comparação de arquivos, snapshots, instalação por cliente e sincronização.
- **Sobreposição:** nosso `harnessctl.py` já controla lifecycle do conjunto reduzido de skills pinadas, com invariantes de segurança e ownership.
- **Risco:** dois gerenciadores escrevendo a mesma pasta podem quebrar hashes, ownership e rollback; sync/symlinks requerem cuidado. A função de backup remoto exige política explícita de dados.
- **Aceite:** ganho demonstrado quando houver múltiplos projetos/skills; `harnessctl` segue como autoridade de manifesto para skills homologadas; nenhuma dupla escrita nos mesmos arquivos.
- **Decisão:** **FERRAMENTA OPERACIONAL OPCIONAL**, não integrar seu engine ao Harness sem necessidade.

### 3.12 Impeccable — melhoria visual no produto de destino, não no core

- **Problema que resolve:** UI funcional, mas genérica, pouco acessível ou fraca em responsividade/UX.
- **O que reaproveitar:** detector de padrões determinísticos, saída JSON, auditoria de componentes e avaliação de interface.
- **Onde usar:** repositórios de aplicações com frontend (MarketOS, Resiplac Core, Forja), mediante autorização de cada projeto.
- **RISCO CRÍTICO:** a documentação informa que um cenário do modo **Live** pode recorrer a executar Codex/Claude com bypass de aprovações e sandbox. Isso é **incompatível** com o Harness; proibir tal modo/configuração.
- **Decisão:** **USAR APENAS ANALISADOR/QA ESTÁTICO E CONTROLADO**, se o projeto de interface tiver necessidade; não instalar como dependência do Harness central.

## 4. Candidatos estudados que **não** entram no núcleo agora

| Projeto | Link | Por que não incluir no núcleo neste ciclo |
|---|---|---|
| Warp `factory-agents-template` | https://github.com/warpdotdev-demos/factory-agents-template | Template de orquestração Oz/Jira/Slack/GitHub, autoavanço e múltiplos agentes; acrescenta plataforma e complexidade. **Licença não identificada nos metadados GitHub consultados**: não copiar trechos de código sem validação legal. Referência arquitetural, não dependência. |
| `pingdotgg/t3code` | https://github.com/pingdotgg/t3code | Boa interface opcional para controlar Codex, Claude e Antigravity; não melhora por si os oráculos nem o benchmark. Avaliação como aplicativo externo, não componente do repositório. |
| `JetBrains/thinkrail` | https://github.com/JetBrains/thinkrail | IDE com runtime Pi e modelo de worktrees por workspace; fora da estratégia de Codex/Claude nativos e consolidação de uma única worktree operacional. |
| `Nutlope/hallmark` | https://github.com/Nutlope/hallmark | Skill visual relevante a frontends, mas redundante com investigação do Impeccable; não é componente do Harness. |
| `Leonxlnx/taste-skill` | https://github.com/Leonxlnx/taste-skill | Direção de arte/frontend, útil em produtos de UI; não altera capacidade central de avaliação de agentes. |
| `TauricResearch/TradingAgents` | https://github.com/TauricResearch/TradingAgents | Framework de análise financeira/trading; fora do escopo do Harness de engenharia. |
| `salmandev/everything-gemini` | https://github.com/salmandev/everything-gemini | Foco em ecossistema Antigravity, diferente dos dois executores oficiais desta arquitetura. Não substituir ECC, Codex ou Claude. |
| `felpsdev/jev-classifier` | https://github.com/felpsdev/jev-classifier | Proxy HTTP interceptador de chamadas de modelos: superfície de risco e complexidade desnecessárias frente ao MCP stdio candidato. |
| `n23eos/jev-skills` | https://github.com/n23eos/jev-skills | Catálogo de skills consultivas; apenas referência, para evitar redundância de instalações. |
| `typesafe-ai/skills` | https://github.com/typesafe-ai/skills | Fonte documental para contrato de API Jev/System One; consultar, não instalar como camada adicional de execução. |

## 5. Mapa de cobertura: o que já existe e o que realmente falta

| Capacidade | Situação do Harness | Lacuna genuína | Fonte potencial |
|---|---|---|---|
| Runtime de edição/código | Codex/Claude nativos definidos | Não construir terceiro runtime | Nenhuma |
| Lifecycle e pinning de skills | `harnessctl.py` e ECC pinado | Provar continuamente execução/ganho sem instalar tudo | ECC, eventualmente Skills Manager só como UI externa |
| Verificação independente de resultado | `harness_eval.py`, CI, oráculos e holdouts | Especialização em segurança e QA comportamental | Cloudflare, GStack |
| Planejamento/especificações | AGENTS/CLAUDE, docs e contratos próprios | Revisão adversarial independente antes de mudanças grandes | EGM |
| Gestão de entrada e feedback | PRs/hand-offs manuais; não há fábrica autônoma exigida | Triagem padrão e aprendizado revisado de correções humanas | Warp cloud-factory-demo |
| Debugging de falhas reais | Procedimentos nativos/ECC | Diagnóstico de causa-raiz sem novas rodadas cegas | Superpowers (`systematic-debugging`) |
| Benchmark externo repetível | Scripts próprios, alguns testes sintéticos sem valor de comparação empírica | Diferencial A×C ou A×J real com isolamento e custo registrado | Harbor, quando necessário |
| Classificação consultiva barata | Pipeline Jev/TypeSafe preparado, piloto live sem sucesso | Inicialização observável e resultado real | `jev-code` + correção mínima do adaptador local |
| Memória entre sessões | Soluções e planos de conhecimento em diferentes projetos | Recuperar histórico sem expor segredos e sem duplicar fontes | claude-mem, condicional |
| UI gerada por agentes | Fora do core do Harness | Regras visuais e QA para produto | Impeccable no repo de frontend |

**Distinção fundamental:** instalar skill não prova invocação; invocação não prova comportamento; comportamento não prova resultado melhor. Todo candidato deve passar pela mesma cadeia de evidências e pelo mesmo custo total de propriedade.

## 6. Sequência pragmática de execução

### P0 — Destravar e consolidar o trabalho existente (antes de novos plugins)

1. **Congelar o escopo das mudanças:** reconciliar branches/worktrees, estado local/remoto e PRs ativos antes de editar o Harness; um responsável pela integração, sem alterações concorrentes de Codex e Gemini no mesmo checkout.
2. **Diagnosticar o bootstrap JEV:** registrar exceção de criação do subprocesso, stderr saneado, saída/encerramento prematuro, timeout e resposta MCP de inicialização. **Não** transformar todas as causas em `JEV_ERROR` sem evidência adicional. Não imprimir chaves nem payload sensível.
3. **Manter o Gate G1 como requisito de segurança:** reconhecer o avanço de MXC/preflight, mas não concluir G1 ou eficiência JEV por um simples comando `echo MXC_OK`.
4. **Retomar, somente quando autorizado, o piloto já delimitado:** sem voltar a 30 casos, sem reruns pagos automáticos, sem novas chamadas só para descobrir falha de processo local. Comparar A e J apenas após bootstrap e fronteiras de confiança verificáveis.
5. **Preservar o ECC pinado:** não trocar versões ou introduzir skills durante o diagnóstico para evitar mudar simultaneamente múltiplas variáveis.

**Saída P0:** erro JEV explicado por evidência causal; repositório sincronizado; PR/documentação refletem estado real; nenhuma afirmação não suportada de ganho empírico.

### P1 — Incrementos de alto valor e baixo acoplamento

1. **Cloudflare (guidance):** adicionar à lista de candidatos pinados e experimentar a classificação `confirmed`/`needs_validation`/`rejected` e um ledger mínimo em revisão defensiva; nenhuma auditoria integral automática.
2. **EGM (spec review):** acionar somente em mudanças grandes de arquitetura/contratos, com revisão independente e limite explícito de turnos.
3. **Warp (triagem e feedback):** padronizar estados de issue e promover correções humanas recorrentes a propostas de mudança de skills via PR revisado; sem orquestração Oz.

**Saída P1:** mudança pequena e reversível por candidato, proprietário único, documentação de alcance, prova de valor e nenhuma dependência global inesperada.

### P2 — Capacidade adicional apenas após identificar a lacuna

- **GStack:** escolher *uma* capacidade de revisão/QA não coberta pelo Codex/Claude/ECC e confrontar seu resultado com o método atual.
- **Superpowers:** usar debugging sistemático em um incidente real, sem adotar toda a cerimônia de planejamento/delegação/worktrees.
- **wshobson/agents:** buscar skills específicas quando as fontes preferenciais não resolverem o problema.
- **Harbor:** usar se comparações isoladas com runtimes nativos não puderem ser executadas de maneira confiável sem ele.
- **Impeccable:** somente dentro do produto frontend específico e **sem bypass de sandbox**.

### P3 — Escala e conveniência, sem contaminar o núcleo

- **claude-mem:** piloto com dados sintéticos ou saneados e fluxo local/consentido; documentar custo e retenção.
- **Skills Manager:** só se a complexidade de gestão de diversas skills/clientes superar o `harnessctl`; nunca dois gerenciadores no mesmo diretório.
- **T3 Code:** opcional como interface externa, sem modificar o contrato dos runtimes.

## 7. Critérios universais de aceite para qualquer integração

Uma integração só passa de **candidato** para **adotada** se registrar, no mínimo:

1. **Dor identificada:** incidente, tempo desperdiçado, erro ou lacuna verificável que a ferramenta pretende resolver.
2. **Reuso comprovado:** funcionalidade nativa e ECC foram examinados; não há duplicação sem justificativa.
3. **Fonte e licença:** repositório canônico, licença aplicável aos arquivos copiados, tag/SHA, data, dependências e riscos de scripts/hooks.
4. **Isolamento real:** nenhuma leitura de segredos, `ground_truth`, `.git` proibido ou sistema pessoal pelo agente; executor não recebe credenciais por conveniência.
5. **Operação governada:** ação destrutiva, network, push, merge, deploy ou despesa exigem autorização específica; atualizações não ocorrem silenciosamente.
6. **Evidência externa:** execução e comportamento observados por logs/artefatos; correção avaliada por oráculo independente.
7. **Resultado mensurável:** qualidade, taxa de erro, latência, tokens, custo, esforço humano e variância versus baseline; nulo/inconclusivo é resultado aceitável.
8. **Rollback:** remoção idempotente, sem resíduos ou mudanças globais, com worktree/repo e estado remoto reconciliáveis.

**Não criar “testes pelo teste”.** A prova deve ser proporcional à dúvida. Para solução documental/skill, uma verificação dirigida pode bastar; para conexão de runtime/credenciais, controles de segurança são obrigatórios; para alegar aumento de produtividade/qualidade, é obrigatório observar tarefas reais.

## 8. Decisões executivas fechadas

| Pergunta | Resposta |
|---|---|
| Instalar todos os projetos de alta relevância? | **Não.** Alta relevância não é autorização de instalação; adotar apenas a fração que resolve lacuna real. |
| Substituir Codex CLI ou Claude Code? | **Não.** São os runtimes de referência e não serão substituídos por fábrica, IDE ou orquestrador novo. |
| Reinstalar ECC completo? | **Não.** Manter as duas skills pinadas; ampliar apenas se prova justificar. |
| Qual melhoria arquitetural mais distinta? | **EGM** para crítica independente de especificações e **Cloudflare** para auditoria especializada. |
| Qual melhoria de processo com pouco acoplamento? | **Warp cloud-factory-demo**: triagem e promoção supervisionada de feedback. |
| Qual melhoria depende do piloto atual? | **Jev / `jev-code`**, que segue sem veredito empírico após falha de inicialização. |
| Incluir Harbor agora? | **Não por padrão.** Somente se responder a uma lacuna de benchmark isolado não atendida com meios existentes. |
| Instalar gerenciador e memória globais? | **Não por padrão.** Podem criar sobreposição, custos e risco sobre fontes de verdade. |
| Usar WSL para todos os componentes? | **Não.** Preferir Windows nativo quando fornece isolamento efetivo; WSL/Docker só quando houver necessidade comprovada e decisão consciente. |
| Próxima ação imediata? | **Corrigir observabilidade do bootstrap JEV e consolidar estado de repositório/PR**, antes de qualquer ampliação. |

## 9. Rastreabilidade e fontes

### Código-fonte e documentos do Harness

- [Repositório Harness Engineering](https://github.com/Williamitiro/harness-engineering-platform)
- [Manual técnico e não objetivos](https://github.com/Williamitiro/harness-engineering-platform/blob/main/docs/MANUAL_HARNESS_V1.md)
- [Reuso, licenças, upstreams e TypeSafe/Jev](https://github.com/Williamitiro/harness-engineering-platform/blob/main/docs/UPSTREAM_REUSE.md)
- [Decisões e riscos](https://github.com/Williamitiro/harness-engineering-platform/blob/main/docs/DECISOES_E_RISCOS.md)
- [Manifesto de skills aprovadas](https://github.com/Williamitiro/harness-engineering-platform/blob/main/config/approved_skills.json)
- [Decisão JEV](https://github.com/Williamitiro/harness-engineering-platform/blob/main/docs/JEV_DECISAO.md)
- [PR #4 — HE-JEV-007A (Draft)](https://github.com/Williamitiro/harness-engineering-platform/pull/4)

### Fontes técnicas externas verificadas

- [ECC](https://github.com/affaan-m/ECC) · [Cloudflare security-audit-skill](https://github.com/cloudflare/security-audit-skill) · [EGM — Google](https://github.com/google/elephant-goldfish-model) · [Warp Cloud Factory Demo](https://github.com/warpdotdev-demos/cloud-factory-demo)
- [GStack](https://github.com/garrytan/gstack) · [Superpowers](https://github.com/obra/superpowers) · [Harbor](https://github.com/harbor-framework/harbor) · [jev-code](https://github.com/FrancoisChastel/jev-code)
- [claude-mem](https://github.com/thedotmack/claude-mem) · [wshobson/agents](https://github.com/wshobson/agents) · [Skills Manager](https://github.com/xingkongliang/skills-manager) · [Impeccable](https://github.com/pbakaus/impeccable)
- Vídeos: [Warp — Software Engineering Is Becoming Factory Engineering](https://youtu.be/tUPPVhBBcoM) · [Full Stack — Top 10 GitHub Repos](https://youtu.be/A3grJN81Ryk)

**Alcance da verificação:** documentação, listagem de arquivos, metadados GitHub, licenças declaradas, histórico de atualização e estado remoto do Harness consultados em 02/11/2026. **Não foram executados benchmarks adicionais, instalações, chamadas pagas nem testes de compatibilidade em Windows.** Situações registradas somente no checkout local precisam ser reconciliadas com o remoto antes de mudança. A análise do vídeo “Top 10” utilizou descrição/capítulos do vidIQ e auditoria direta dos repositórios; o transcript completo não pôde ser obtido por falta de créditos da conta conectada.

---

**Conclusão:** o objetivo não é somar ferramentas, mas **reduzir erro e retrabalho com poucas capacidades auditáveis**. Prioridade operacional: estabilizar Jev/G1 e o repositório; prioridade arquitetural seguinte: Cloudflare, EGM e triagem/feedback da Warp; os demais candidatos somente por lacuna real, com isolamento, custo e benefício demonstrados.