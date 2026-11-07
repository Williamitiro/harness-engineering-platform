# Análise — como instalar o Harness em qualquer ferramenta e qualquer repositório

**Data:** 03/11/2026 · **Autor:** Claude (análise, sem código) · **Base:** SPEC canônica e relatórios HE-OP na branch
`codex/he-jev-007a`, documento `HARNESS_ENGINEERING_PLATFORM__REUSO_TECNICO_E_BENCHMARKS_2026-11-02.md`, pesquisa
na documentação oficial das ferramentas (links no fim) e conferência no disco desta máquina.

Legenda de evidência: **[V]** lido em documentação oficial ou conferido nesta máquina · **[V3]** fonte de terceiros ·
**[U]** não verificado.

---

## 1. Conclusão em 5 linhas

1. **Existe um padrão quase universal, e é ele que devemos usar:** skills no formato *Agent Skills* (`SKILL.md`,
   agentskills.io) e regras no `AGENTS.md`. A maioria das ferramentas lê os dois.
2. **"Global" funciona para as skills:** uma pasta `~/.agents/skills` atende Codex, Cursor, OpenCode, Copilot e
   Gemini CLI sem fazer nada. Claude Code e Antigravity precisam de um "apontador" para essa mesma pasta.
3. **"Global" não funciona para as regras:** não existe um arquivo de regras global que todas leiam. Regras ficam
   **no repositório** (`AGENTS.md`), que é o lugar certo para elas, porque cada projeto tem as suas.
4. **Recomendação: modelo em 2 camadas.** Camada da máquina: as skills, instaladas uma vez. Camada do repositório:
   o contrato e as skills específicas do projeto, instaladas pela `setup-harness`. Uma tabela de adaptadores diz
   onde cada ferramenta procura.
5. **A SPEC está certa na direção e no rigor**, mas precisa de 6 ajustes (seção 5). O mais importante: **o benchmark,
   como está desenhado hoje, mediria errado**, porque o braço "sem Harness" já carregaria as skills globais.

---

## 2. Como cada ferramenta encontra skills e regras

| Ferramenta | Lê `~/.agents/skills` (global)? | Lê `.agents/skills` (repo)? | Regras do repo | Observação |
|---|---|---|---|---|
| **Codex** (CLI, IDE, desktop) | ✅ [V] | ✅ [V] | `AGENTS.md` [V] | É o "dono" do padrão `.agents` |
| **Claude Code** | ❌ [V] precisa de `~/.claude/skills` | ❌ precisa de `.claude/skills` | `CLAUDE.md`; lê `AGENTS.md` só se não houver `CLAUDE.md` [V] | **Nesta máquina já funciona**: `~/.claude/skills` é junction para `~/.agents/skills` [V] |
| **Cursor** | ✅ [V] | ✅ [V] | `AGENTS.md` e `.cursor/rules` [V] | Também lê `.claude/skills`, o que pode listar a skill duplicada |
| **OpenCode** | ✅ [V] | ✅ [V] | `AGENTS.md`, com fallback para `CLAUDE.md` [V] | Também lê `.claude/skills` |
| **GitHub Copilot** | ✅ [V] | ✅ [V] | `AGENTS.md`, `.github/copilot-instructions.md` [V] | |
| **Gemini CLI** | ✅ (alias) [V] | ✅ (alias) [V] | `GEMINI.md`; `AGENTS.md` só se configurado [V] | Sendo substituído pelo Antigravity CLI [V] |
| **Antigravity** | ❌ usa `~/.gemini/config/skills` [V] | ✅ [V] | `AGENTS.md` e `GEMINI.md` [V] | Caminhos mudaram recentemente; reconferir |
| Kilo, Cline, Amp | ✅ (segundo a tabela do `npx skills`) [U] | ✅ [U] | `AGENTS.md` [V] | |
| Roo, Goose, Windsurf, Kiro, Grok, Qwen | ❌ cada uma tem pasta própria [U] | pasta própria [U] | `AGENTS.md` (maioria) [V] | Precisam de adaptador |
| DeepSeek | Não há CLI de agente própria identificada | — | — | Normalmente se usa o modelo DeepSeek **dentro** de outra ferramenta (OpenCode, Cline…), e aí vale a regra dela |

**Leitura prática:**
- **Skill nova numa ferramenta nova:** se a ferramenta segue o padrão (a tendência de 2026), ela lê `~/.agents/skills`
  e `.agents/skills` **sem você fazer nada**. Se não segue, basta uma linha na tabela de adaptadores. Nunca é preciso
  reescrever a skill.
- **Plugins** (Claude, Codex, Gemini, OpenCode…) **não são portáveis**: cada um tem um formato. Servem no máximo como
  "embrulho" opcional em volta da mesma pasta de skills. Não devem ser o mecanismo principal.
- **Hooks** existem em quase todas, mas com configurações diferentes. Não usar como base do Harness (a SPEC já proíbe
  hooks globais, e está certa).

---

## 3. As opções que você levantou, avaliadas

| Opção | Funciona? | Prós | Contras | Veredito |
|---|---|---|---|---|
| **A. Global "mágico"** (instala uma vez e vale para qualquer ferramenta e repo) | Parcial | Zero trabalho por repo | Regras não têm lugar global comum; Claude e Antigravity precisam de apontador | **Vale para as skills, não para as regras** |
| **B. Uma instalação por ferramenta** (Claude, Codex, OpenCode, Cursor…) | Sim | Simples de entender | N cópias da mesma skill, que divergem com o tempo | **Não**: vira manutenção manual |
| **C. Só por repositório** (como a SPEC atual) | Sim | Versionado no Git, reproduzível | Precisa rodar setup em cada repo; skills genéricas duplicadas em 20 repos | **Só para o que é do projeto** |
| **D. Híbrido: 2 camadas + tabela de adaptadores** | Sim | Uma fonte, zero duplicação, regras por projeto | Um pouco mais de desenho inicial | ✅ **Recomendado** |

### Modelo recomendado (D)

```
CAMADA 1 — MÁQUINA (uma vez por computador)            "o que você leva para todo lugar"
  ~/.agents/skills/                       ← pasta canônica (padrão aberto)
      setup-harness/                        instaladora / verificadora
      tdd-workflow/  verification-loop/     skills de trabalho genéricas (ECC, pinadas)
      .harness-manifest.json                versão, hashes, de onde veio
  Apontadores (só para quem não lê ~/.agents/skills):
      ~/.claude/skills          → Claude Code     (já existe nesta máquina, como junction)
      ~/.gemini/config/skills   → Antigravity
      (outras: uma linha na tabela de adaptadores)

CAMADA 2 — REPOSITÓRIO (setup-harness, uma vez por repo)  "o que é deste projeto"
  AGENTS.md                ← regras do projeto (criado se não existir; preservado se existir)
  CLAUDE.md                ← só "@AGENTS.md" (se o projeto usar Claude Code e ainda não tiver um)
  .agents/skills/<skills específicas do projeto>   (opcional; ex.: regras de CAD da plataforma)
  .claude/skills/          ← espelho só se houver skills de projeto e o projeto usar Claude
  .harness/manifest.json   ← o que o Harness instalou aqui, com hashes (para remover exato)
```

**Por que as skills genéricas vão para a máquina e não para cada repo:**
- skills só carregam quando o assunto aparece (cerca de 100 tokens de "cartão de visita"; o corpo só entra quando
  é usada) [V]. Ficar global custa praticamente nada nos repos onde não são usadas;
- atualizar uma vez atualiza tudo, sem 20 PRs;
- o repositório continua dono só do que é dele.

**Quando faz sentido copiar uma skill para dentro do repo:** quando outra pessoa ou outra máquina precisa do mesmo
comportamento só clonando o projeto, ou quando o projeto precisa de uma versão congelada. É uma exceção, decidida
no plano, não o padrão.

---

## 4. A `setup-harness`: repositório novo vs. existente

Sua ideia de usar uma skill de setup está correta, e a SPEC já a adota. O ajuste é que ela fique **no perfil**, não
copiada para o repo antes, porque assim funciona igual em repo vazio e em repo antigo. Para repo novo, o seu fluxo
("crio o diretório, rodo o setup, depois começo a codar") funciona do mesmo jeito.

**Sequência canônica, igual em qualquer ferramenta e qualquer repo:**

| # | Passo | Repo novo | Repo existente (plataforma, Nexus Quant, Resiplac Core, Video Motion…) |
|---|---|---|---|
| 0 | **Máquina pronta?** Camada 1 instalada e verificada | igual | igual |
| 1 | **Diagnosticar** (só lê): é Git? tem `AGENTS.md`/`CLAUDE.md`? tem skills? quais ferramentas o projeto usa? | quase tudo vazio | detecta contrato e skills existentes, branch e regras de cópia isolada |
| 2 | **Planejar**: lista exata de arquivos a criar e o que será preservado | cria `AGENTS.md` a partir do template | **preserva** o `AGENTS.md`; no máximo propõe um bloco mínimo para o dono aprovar |
| 3 | **Aprovar**: você diz sim ao plano | | |
| 4 | **Aplicar**: cria só os arquivos do plano | direto | **em branch/PR**, conforme as regras do projeto |
| 5 | **Verificar arquivos** (hash) | | |
| 6 | **Verificar descoberta**: cada ferramenta lista as skills? (a prova de verdade) | | |
| 7 | **Registrar**: manifesto + recibo | | |
| — | **Remover** = passos 1–7 ao contrário, só o que o manifesto prova que é do Harness | | |

O passo 6 é o que hoje falta tornar rotina. Copiar arquivo não prova nada; prova é a ferramenta listar a skill e
usá-la numa tarefa.

---

## 5. Matriz cruzada: SPEC atual vs. achados

| # | Ponto da SPEC | Situação | Achado | Ação proposta |
|---|---|---|---|---|
| 1 | Copiar arquivos; sem MCP, Node ou daemon | ✅ Correto | Bate com o padrão de mercado | Manter |
| 2 | `setup-harness` no perfil pessoal, invocação explícita | ✅ Correto | É exatamente o uso previsto pelo padrão | Manter |
| 3 | Preservar contrato existente (`--preserve-contract`) | ✅ Correto | Essencial para seus repos antigos | Manter; tornar o **padrão** quando o `AGENTS.md` existe |
| 4 | Skills de trabalho **copiadas em cada repo** | ⚠️ Revisar | Duplicação; o padrão permite global | Mover as genéricas para a Camada 1; repo só recebe as específicas |
| 5 | Suporte por cliente com destinos fixos (`--client codex`) | ⚠️ Revisar | Escala mal para 8+ ferramentas | Trocar por **tabela de adaptadores** (dados, não código por ferramenta) |
| 6 | Claude Code só no R3 | ⚠️ Revisar | Distribuir skills para o Claude é barato (`~/.claude/skills` + `CLAUDE.md` com `@AGENTS.md`) | Trazer a **distribuição** do Claude para o R1; deixar só o **benchmark** do Claude no R3 |
| 7 | Skill instalada aponta para o checkout local do Harness | ❌ Frágil | Quebra se o checkout mudar de branch (no `main` não há `project-*`) [V] | Merge do PR #4; o setup deve usar uma versão do Harness fixada |
| 8 | Fonte ECC em `.poc/ecc-pinned` (pasta ignorada pelo Git) | ❌ Frágil | Só existe nesta máquina [V] | Versionar as 2 `SKILL.md` + LICENSE (MIT) no próprio repo do Harness, com hash |
| 9 | Descritor da skill diz `client: codex`, também visto pelo Claude | ⚠️ Bug latente | Pela junction, o Claude lê a skill configurada para Codex [V] | Resolve-se com o item 5: a skill detecta a ferramenta em uso, sem descritor fixo |
| 10 | Benchmark A (sem Harness) × B (com Harness) | ✅ Desenho bom | Pré-registro, oráculo externo, `null` ≠ 0 e veredito INCONCLUSIVO estão certos | Manter |
| 11 | Isolamento do braço A | ❌ Falta | Sem isolar, A carrega `~/.agents/skills`, `~/.codex/AGENTS.md` e `~/.claude` | A roda com perfil limpo (`CODEX_HOME` / `CLAUDE_CONFIG_DIR` vazios, ou `claude --bare`) e registra as skills carregadas |
| 12 | Repetições ("só para variância") | ⚠️ Insuficiente | Agentes variam a cada execução; 1 execução por braço não separa ganho de ruído | k=3 por tarefa por braço, como faz o próprio skill-creator da Anthropic |
| 13 | Escolha das tarefas | ⚠️ Falta critério | Em estudos com tarefas reais, 39 de 49 skills tiveram efeito zero, muitas porque as tarefas eram fáceis demais [V] | Escolher tarefas que o baseline erra às vezes (30–70%) |
| 14 | Métricas | ⚠️ Incompletas | Skills de TDD e verificação aparecem mais em retrabalho e regressão que em taxa de acerto | Somar: teste escrito antes? verificação rodada antes do "pronto"? regressões ocultas? A skill disparou? |
| 15 | Runner `harness_eval.py` | ❌ Bugs | Tokens começam em **0, não `null`** (linhas 342–343) [V]; o Claude roda com `json` e perde a trajetória; o Codex descarta tokens de cache e de raciocínio | Corrigir antes de qualquer execução: Claude com `stream-json`, Codex com todos os campos, versão e modelo registrados |
| 16 | Bloco financeiro com 7 campos | ⚠️ Excesso | Em assinatura, custo é estimativa | Reduzir a `cost_source` + `cost_usd_estimado` + `observado` |
| 17 | Harbor como spike delimitado | ✅ Correto | Suporta Codex, Claude, OpenCode, Cursor e Gemini, e injeta skills [V]; exige Docker; no Windows Home, só via Docker Desktop + WSL2 [V] | Spike de 1 dia: 1 tarefa, primeiro com `oracle` (custo zero), depois Codex A/B |
| 18 | JEV no R4, desligado por padrão | ✅ Correto | Ver seção 6 | Manter; alinhar `JEV_DECISAO.md` (ainda fala de MCP) com o caminho HTTP |
| 19 | Documentação | ❌ Fragmentada | 30+ documentos; README com avisos históricos sobrepostos | Um documento canônico de instalação + a tabela de adaptadores; o resto vira histórico |

---

## 6. Modelos de decisão (JEV) — o que é fato e o que é promessa

**O que é:** um modelo que não escreve texto; recebe uma situação e perguntas fechadas ("qual destas opções?",
"sim/não?", "nota de 0 a 1") e devolve probabilidades. É rápido (~0,4 s) e muito barato (cobra só a entrada) [V].

**Evidência hoje:**
- o benchmark do fabricante mostra o JEV empatado com modelos grandes em 4 fluxos, com custo ~75× menor [V3, do
  fabricante]. Mas o "gabarito" foi a média de dois LLMs, e não existe reprodução independente [V3];
- estudos independentes de 2026 sobre roteadores de modelos mostram que muitos **não superam de forma confiável o
  melhor modelo único** [V];
- seu piloto: 3 classificações certas nas duas condições. Funciona tecnicamente, mas não prova ganho.

**Onde faz sentido no Harness:** decisões **estreitas, frequentes e baratas de errar**, sempre com plano B quando a
confiança for baixa:
- classificar uma tarefa por tipo e risco para escolher skill ou nível de esforço;
- triagem de diff ou log ("precisa de revisão humana?");
- portão de risco antes de ação sensível, como **segunda opinião**, nunca como autoridade.

**Onde não faz sentido:** substituir o raciocínio do agente, ou economizar centavos numa tarefa que custa reais em
tokens do agente. No seu volume de uso pessoal, a economia é irrelevante; o valor possível é **velocidade e
consistência** de decisões de triagem.

**Recomendação:** a SPEC está certa em deixar o JEV desligado até o R2 existir. O R2 é o que vai permitir medir se
uma triagem com JEV melhora alguma coisa. Quando voltar, testar contra gabarito feito por **humano**, não por LLM.

---

## 7. O que a pesquisa diz sobre "skills que o YouTube recomenda"

Seu ceticismo tem respaldo:
- **SkillsBench (2026):** skills curadas deram +16 pontos percentuais em média; skills geradas pelo próprio modelo
  deram −1,3; 2–3 skills focadas funcionam melhor que 4+ [V];
- **SWE-Skills-Bench (2026, repositórios reais):** 39 de 49 skills tiveram **efeito zero**, 7 ajudaram (até +30%),
  3 **atrapalharam** (até −10%), e o consumo de tokens variou de −78% a +451% [V].

Conclusão: **não instalar por fama**. É exatamente por isso que o R2 (benchmark) é obrigatório no seu plano. Ele é a
peça que transforma "o youtuber disse" em "medimos no nosso código".

---

## 8. Ordem de execução proposta

| Etapa | O quê | Por quê |
|---|---|---|
| 1 | Revisar e fazer o merge do PR #4 | Elimina a dependência de branch (item 7) |
| 2 | Atualizar a SPEC: modelo de 2 camadas, tabela de adaptadores, sequência canônica, itens 11–16 | Documentação canônica antes do código |
| 3 | Implementar Camada 1: instalar e verificar as skills na máquina + apontadores para Claude e Antigravity | Vale para todos os repos de uma vez |
| 4 | Ajustar a `setup-harness` para a Camada 2 (repo novo e existente, multi-ferramenta) | Seu fluxo diário |
| 5 | Instalar na plataforma metalúrgica via PR, depois da suíte verde | Primeiro uso real e permanente |
| 6 | Corrigir o runner e isolar o braço A; spike Harbor; benchmark com 2 tarefas, k=3 | R2: provar ou descartar o ganho |
| 7 | Demais repos (Nexus Quant, Resiplac Core, Video Motion…) | Repetir a etapa 4 |
| 8 | JEV (R4) e demais ferramentas (R5–R6), só com ganho medido | |

---

## 9. Decisões que preciso de você

1. **Skills genéricas na máquina (recomendado) ou em cada repo?**
2. **Quais ferramentas entram no R1?** Sugestão: Codex + Claude Code (as que você usa), com Cursor, OpenCode e
   Antigravity apenas pela tabela de adaptadores, verificadas quando você for usá-las.
3. **Docker Desktop + WSL2 nesta máquina para o spike do Harbor:** pode instalar quando chegarmos lá?

---

### Fontes principais

Claude Code skills/memória: code.claude.com/docs/en/skills, /memory, /headless, /monitoring-usage · Codex:
learn.chatgpt.com/docs/build-skills, /agent-configuration/agents-md, /non-interactive-mode ·
OpenCode: opencode.ai/docs/skills · Gemini CLI: geminicli.com/docs/cli/skills · Antigravity: antigravity.google/docs/skills ·
Cursor: cursor.com/docs/context/skills · Copilot: docs.github.com (about-agent-skills) · Padrão: agentskills.io/specification,
agents.md · Instalador multi-ferramenta: github.com/vercel-labs/skills · Harbor: github.com/harbor-framework/harbor,
docs.harborframework.com · SkillsBench: arxiv.org/abs/2602.12670 · SWE-Skills-Bench: arxiv.org/abs/2603.15401 ·
LLMRouterBench: arxiv.org/abs/2601.07206 · JEV: openrouter.ai/docs/guides/community/jev · OpenAI, avaliação de skills:
developers.openai.com/blog/eval-skills.
