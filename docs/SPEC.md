# Harness Engineering — SPEC canônica (V2)

**Vigente desde 03/11/2026.** Substitui `HARNESS_SPEC_CANONICA_USO_DIARIO_E_BENCHMARK_V1.md` e os demais documentos,
agora em [`historico/`](historico/). Uso para pessoas: [MANUAL](MANUAL.md). O que existe hoje: [ESTADO](ESTADO.md).

Regra de leitura: esta SPEC diz **o que deve existir e como aceitar**. Ela não afirma que algo já funciona. O que
funciona está no ESTADO, com evidência. Em caso de conflito, **código e testes executados prevalecem sobre texto**, e
o ESTADO deve ser corrigido.

---

## 1. Missão e limites

**Missão:** programar em 10–20 repositórios com Claude Code e Codex usando um kit pequeno de regras e skills, e
**medir** se esse kit melhora qualidade, tempo e custo.

**O MVP (V1) tem quatro capacidades, nesta ordem:**
1. instalar, verificar e remover o kit no computador e em cada repositório, sem apagar nada alheio;
2. trabalhar com os agentes **nativos** (Claude Code primeiro, depois Codex);
3. benchmark A/B real (sem kit × com kit) com verificador independente;
4. registro de qualidade, tempo, tokens e custo, com a origem de cada número.

**Não é objetivo:** criar um runtime ou agente próprio, um servidor MCP ou daemon, hooks globais, instalar os 12
upstreams do dossiê, ou tratar classificação JEV como benchmark de programação.

## 2. Princípios (valem para qualquer mudança)

1. **Reuso primeiro:** recurso nativo → padrão aberto → API/CLI oficial → código novo mínimo. Usar MCP só se o agente
   precisar invocar a ferramenta durante o trabalho.
2. **Evidência tem nível:** documentação < teste offline < ensaio real < benchmark. Status sempre explícito:
   `PASS`, `FAIL`, `BLOCKED_*`, `NOT_RUN`, `INCONCLUSIVE`. Para skills, a cadeia é
   `FILE_PRESENT → DISCOVERED → INVOKED → BEHAVIOR_OBSERVED → OUTCOME_VERIFIED`, com prova própria em cada nível.
   Arquivo copiado **não** prova que a skill foi usada. Dado sintético é rotulado `SYNTHETIC_*` e nunca vira
   benchmark. Hash local prova integridade, não autenticidade.
3. **Ausente é `null`, nunca `0`.** Custo parcial nunca é apresentado como total.
4. **Uma hipótese por falha.** Se um teste falha, classificar (contrato, integração ou infraestrutura) e corrigir a
   menor peça. Não trocar de abordagem por tentativa e erro (lição JEV/Node, ver ESTADO §4).
5. **Escopo fechado:** uma entrega por vez, com testes positivos e negativos e suíte offline verde.
6. **Autorização explícita** para: escrever fora deste repositório, push, merge, deploy, chamadas pagas, instalar
   dependências, alterar configurações globais.

## 3. Arquitetura: duas camadas e uma tabela de adaptadores

```
FONTE (versionada)          C:\dev\harness-engineering
  skills/<nome>/SKILL.md      skills próprias do Harness (setup-harness)
  vendor/ecc/                 cópia byte a byte do ECC pinado: 2 SKILL.md + LICENSE + SOURCE.json (sem conversão de fim de linha)
  templates/                  AGENTS.md e CLAUDE.md iniciais para repositórios novos
  config/adapters.json        onde cada ferramenta procura skills e regras
  scripts/harnessctl.py       o único instalador

CAMADA 1 — MÁQUINA           uma vez por computador; vale para todos os repositórios
  ~/.agents/skills/<nome>/            pasta canônica (padrão Agent Skills)
  ~/.agents/skills/.harness-machine.json   versão, hashes e origem
  apontadores, conforme adapters.json:
    Claude Code → ~/.claude/skills/<nome>   (link por skill; cópia se o link não for detectado)
    Antigravity → ~/.gemini/config/skills/<nome>   (R3+)

CAMADA 2 — REPOSITÓRIO       uma vez por projeto; só o que é do projeto
  AGENTS.md                  regras do projeto: criado se ausente, PRESERVADO se existe
  CLAUDE.md                  criado com "@AGENTS.md" se ausente; se existe, propor a linha "@AGENTS.md" (com aprovação)
  .agents/skills/<proj>/     somente skills específicas do projeto (opcional)
  .claude/skills/<proj>/     espelho dessas skills, se o projeto usa Claude Code
  .harness/manifest.json     recibo: arquivos e hashes do Harness, política de contrato, versão
```

**Por que as skills genéricas ficam na máquina:** o padrão Agent Skills carrega cerca de 100 tokens por skill até que
ela seja usada, então manter global custa pouco. Uma atualização vale para todos os repositórios, e o repositório
fica dono só do que é dele. **Exceção:** copiar uma skill genérica para dentro do repositório (*vendoring*) apenas
quando o projeto precisar dela congelada ou compartilhada só pelo clone. A decisão é tomada no plano, nunca por
padrão.

**Tabela de adaptadores** (`config/adapters.json`, verificada em 03/11/2026 na documentação oficial):

| Ferramenta | Skills (máquina) | Skills (repositório) | Regras | Release |
|---|---|---|---|---|
| Claude Code | `~/.claude/skills` | `.claude/skills` | `CLAUDE.md` (com `@AGENTS.md`) | **R1** |
| Codex | `~/.agents/skills` | `.agents/skills` | `AGENTS.md` | **R1** |
| Cursor, OpenCode, Copilot | `~/.agents/skills` | `.agents/skills` | `AGENTS.md` | sem trabalho extra; verificar ao adotar |
| Gemini CLI | `~/.agents/skills` (alias) | `.agents/skills` | `GEMINI.md` ou `AGENTS.md` configurado | idem |
| Antigravity | `~/.gemini/config/skills` | `.agents/skills` | `AGENTS.md` | R3+ (precisa de apontador) |
| Outras | conforme a documentação delas | | `AGENTS.md` | uma entrada nova na tabela |

Adicionar uma ferramenta = **uma entrada na tabela + teste de descoberta**, sem código novo por ferramenta. Plugins e
hooks de cada ferramenta não são portáveis e não fazem parte do núcleo.

## 4. Sequência canônica (igual para toda ferramenta e todo repositório)

Toda operação do `harnessctl` e da skill `setup-harness` segue estes passos e só avança se o anterior passou:

| # | Passo | Escreve? | Saída obrigatória |
|---|---|---|---|
| 1 | **Diagnosticar** (`doctor`) | não | caso detectado (`NEW_REPO`, `EXISTING_REPO`, `ATTACHED`), contratos, skills e colisões |
| 2 | **Planejar** (`plan`) | não | lista exata de arquivos a criar e a preservar |
| 3 | **Aprovar** | — | "sim" do operador para **esse** plano e **esse** destino |
| 4 | **Aplicar** (`attach`/`install --apply`) | sim | criação exclusiva; falha parcial desfaz só o que criou |
| 5 | **Verificar arquivos** (`verify`) | não | hashes conferem com o manifesto |
| 6 | **Verificar descoberta** | não | cada ferramenta-alvo lista as skills (comando nativo, sem turno de modelo quando possível) |
| 7 | **Registrar** | sim | manifesto + recibo com versão, hashes e resultado da descoberta |
| ↩ | **Remover** (`remove`) | sim | prévia sem `--apply`; remove só o que o manifesto prova e que está inalterado |

**Repositório existente:** respeitar as regras locais de branch e cópia isolada e entregar por PR. O contrato
existente nunca é lido para concatenar, sobrescrito ou reivindicado. Preservar é o **padrão** quando `AGENTS.md`
existe (hoje isso exige a flag `--preserve-contract`). Skills de terceiros, links simbólicos e qualquer outra colisão
bloqueiam (`BLOCKED_COLLISION`).

**Repositório novo:** `git init` só com a confirmação do operador; depois, mesma sequência.

## 5. Releases e gates

| Release | Entrega | Gate de saída |
|---|---|---|
| **R0** Fundação | docs canônicos (este conjunto), CI offline | README → MANUAL/SPEC/ESTADO; CI verde |
| **R1** Uso diário | camada 1 + camada 2 para **Claude Code e Codex**; fonte ECC versionada no repo; `setup-harness` multi-ferramenta | repo novo e repo existente: passos 1–7 e remoção exata; descoberta observada nas duas ferramentas; 1 tarefa real com QA externo em cada uma |
| **R2** Benchmark | runner A/B, telemetria, relatório; decisão sobre o Harbor | ≥2 tarefas reais, k=3 por braço, braço A isolado; relatório GANHO/EMPATE/REGRESSÃO/INCONCLUSIVO |
| **R3** Mais ferramentas | Antigravity e outras via tabela; comparação Claude × Codex | descoberta + tarefa real por ferramenta, ou `BLOCKED_*` factual |
| **R4** JEV | triagem opt-in no supervisor | ganho medido contra gabarito **humano**; desligado por padrão |
| **R5–R6** Extras | Cloudflare, EGM, Warp, Superpowers, GStack… | um módulo por PR, só se o benchmark mostrar ganho |

**"Harness V1 pronto" = R1 + R2 com os gates acima.** Sem R2, o kit é um palpite.

## 6. Benchmark (R2)

**Pergunta 1:** o kit melhora o mesmo agente? (A = sem kit, B = com kit). **Pergunta 2:** qual agente resolve melhor
as mesmas tarefas? Essa vem depois e é relatada separadamente.

**Desenho mínimo:**
- **Tarefas:** 2 para o ensaio de ponta a ponta, depois 8–12 pré-registradas (bug, feature pequena, teste,
  refatoração, segurança). Escolher tarefas que o baseline **erra às vezes** (cerca de 30–70%); tarefa que os dois
  braços sempre acertam não mede nada.
- **Cópias idênticas e descartáveis**, sem `.git` nem histórico que contenha a solução, sem gabarito, sem tokens.
  Verificador fora do sandbox. Gabarito e tarefas cegas em pastas separadas; o agente nunca vê o gabarito.
- **Isolamento (gate G1):** contenção real de arquivos, credenciais, Git pai, gabarito e rede, comprovada por
  **canários negativos** por execução. Canário intacto prova só que o canário está intacto. Host Windows direto foi
  reprovado (vazou); o melhor resultado observado até agora é o MXC nativo do Codex, sem atestação externa.
- **Braço A isolado (obrigatório):** sem as skills da camada 1 (perfil limpo: `CODEX_HOME` / `CLAUDE_CONFIG_DIR`
  vazios ou `claude --bare`). Registrar a lista de skills carregadas em cada execução como prova.
- **Repetição:** k=3 por tarefa por braço; ordem alternada; modelo e esforço fixados e registrados.
- **Métricas primárias:** aceite pelo verificador, regressões, tempo por tarefa aceita.
- **Métricas das skills:** a skill disparou? O teste foi escrito antes do código? A verificação rodou antes do
  "pronto"? Skill que não dispara é uma falha à parte, não "efeito zero".
- **Secundárias:** tokens (entrada, cache, saída, raciocínio), chamadas de ferramenta, retrabalho.
- **Custo:** `cost_source` (`api_billed` | `subscription_estimate` | `unknown`), `cost_usd` (`null` se não
  observado), `observed` (bool). Assinatura não vira preço por chamada.
- **Veredito:** adotar só se não piorar nenhum critério funcional e melhorar uma métrica pré-registrada. Se os dois
  braços passam em tudo ou os custos são desconhecidos: **INCONCLUSIVO**.

**Telemetria nativa a usar:** Claude Code `-p --output-format stream-json --verbose` (eventos, `usage`,
`total_cost_usd` estimado); Codex `exec --json` (`turn.completed.usage` com `input_tokens`, `cached_input_tokens`,
`output_tokens`, `reasoning_output_tokens`; sem custo). OpenTelemetry é opcional.

**Harbor (spike de no máximo 1 dia):** já integra Claude Code e Codex e injeta skills por tarefa; exige Docker. Nesta
máquina (Windows Home), só via Docker Desktop + WSL2, mediante autorização. Ordem: 1 tarefa com o agente `oracle`
(custo zero), depois Codex A/B. Funcionou → `HARBOR_USE`; senão → `DEFER_HARBOR` e usar o runner próprio
(`scripts/harness_eval.py`).

**Expectativa honesta:** estudos de 2026 com repositórios reais mostram efeito zero para a maioria das skills, e
algumas pioram o resultado. "Empate com menos retrabalho" é um resultado plausível e válido.

## 7. JEV e modelos de decisão (R4)

- **O que é:** um modelo remoto (OpenRouter Decisions API, alfa) que responde perguntas fechadas com probabilidades.
  Não escreve código e não escolhe sozinho o modelo de programação.
- **Caminho único:** `scripts/jev_http.py`, HTTPS direto, executado no supervisor. MCP/Node (`jev-code`) é legado e
  não deve ser retomado.
- **Onde pode valer:** decisões estreitas, frequentes e com plano B (tipo e risco da tarefa → skill ou esforço;
  "precisa de revisão humana?"). Sempre consultivo.
- **Evidência atual:** só do fabricante, com gabarito gerado por LLM; roteadores em geral não superam de forma
  confiável o melhor modelo único. **Desligado até R2 existir.** Ao retomar: gabarito humano e fallback abaixo do
  limiar de confiança.
- **Regras herdadas do piloto (continuam valendo):** limiares de autoaceite com confiança ≥ 0,85 e margem ≥ 0,50;
  abaixo disso, cai no mesmo modelo nativo da condição A. Piloto pago: no máximo 3 casos, 0 retries, 180 s, saída
  fora do checkout. Chave: uma variável por provedor (`OPENROUTER_API_KEY`). Veredito: `APPROVE_ADVISORY_ONLY`,
  `REJECT` ou `INCONCLUSIVE`; quem decide a adoção é o usuário.

## 8. Catálogo de upstreams (destino de cada um)

| Upstream | Uso | Release |
|---|---|---|
| [ECC](https://github.com/affaan-m/ECC) | `tdd-workflow`, `verification-loop`, pinados por SHA `b38be6a7…` e hash, licença MIT | R1 |
| [Harbor](https://github.com/harbor-framework/harbor) | motor de benchmark, se o spike passar | R2 |
| [jev-code](https://github.com/FrancoisChastel/jev-code) | só referência; usamos HTTP direto | R4 |
| Cloudflare security-audit, Google EGM, Warp cloud-factory | um módulo por lacuna | R5 |
| Superpowers, GStack, wshobson/agents, Impeccable, claude-mem, Skills Manager | uma skill por déficit medido | R6 |

Antes de usar qualquer upstream: SHA, licença dos arquivos usados, conteúdo revisado (skills podem conter comandos e
downloads). Não instalar catálogos inteiros. Dossiê original: `historico/reference/`.

## 9. Segurança

- Segredos ficam no supervisor (Infisical); nunca entram em agentes, sandboxes, logs ou no Git.
- Processos de agente não herdam `OPENROUTER_API_KEY`, `TYPESAFE_API_KEY`, `NODE_OPTIONS` ou tokens.
- O instalador não lê o conteúdo de arquivos do projeto-alvo, não executa hooks ou filtros do Git e recusa links,
  junctions e hardlinks no destino.
- Sem hook global, MCP ou alteração de configuração global sem opt-in explícito.
- Limite conhecido: o manifesto não é assinatura criptográfica, e não há proteção contra escritor hostil concorrente
  nem garantia de transação após queda de energia.

## 10. Backlog (próximas entregas, em ordem)

| ID | Release | Entrega | Teste de aceite |
|---|---|---|---|
| HE-DOC-01 | R0 | este conjunto de docs; histórico arquivado | links válidos, CI verde |
| HE-R1-01 | R1 | versionar as 2 skills ECC + LICENSE em `skills/`, com hash; sem depender de `.poc/`; conferir dependências de bash/POSIX e `$CLAUDE_PLUGIN_ROOT` no Windows | instalação numa máquina sem `.poc`; skill legível e utilizável no Windows |
| HE-R1-02 | R1 | `config/adapters.json` + `machine-install/verify/remove` (Claude Code + Codex) | instalar/verificar/remover em home sintética; descoberta real nas duas ferramentas |
| HE-R1-03 | R1 | camada 2 multi-ferramenta: preservar contrato por padrão, `CLAUDE.md` com `@AGENTS.md`, sem copiar skills genéricas | repo novo e repo existente; remoção exata |
| HE-R1-04 | R1 | `setup-harness` reescrita: detecta a ferramenta (sem `client` fixo), subcomandos verificar/remover | descoberta + uso em chat novo no Claude Code e no Codex |
| HE-R1-05 | R1 | instalação permanente na plataforma metalúrgica (via PR) | tarefa real com QA externo |
| HE-R2-01 | R2 | corrigir o runner: `stream-json` no Claude, todos os campos no Codex, `null` ≠ 0, versão e modelo registrados | testes offline do parser |
| HE-R2-02 | R2 | braço A isolado + k=3 + métricas das skills | 2 tarefas, relatório |
| HE-R2-H | R2 | spike Harbor (com autorização para Docker) | `HARBOR_USE` ou `DEFER_HARBOR` |
| HE-R2-03 | R2 | lote 8–12 tarefas | veredito auditável → **V1 pronto** |
