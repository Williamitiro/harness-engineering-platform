# Estado do Harness Engineering

**Atualizado em 07/11/2026** (§7: modelo operacional). Este é o único lugar com status. Ao concluir uma entrega, atualize a tabela §1 e as
pendências §2. Não crie relatórios novos.

Branch de trabalho: `codex/he-jev-007a` ([PR #4](https://github.com/Williamitiro/harness-engineering-platform/pull/4),
Draft, CI verde em `1e9ca9c`, **sem revisão e sem merge**). O `main` ainda não contém nada abaixo de HE-OP.

## 1. O que existe e com que prova

| Capacidade | Status | Prova (nível) | Onde |
|---|---|---|---|
| Docs canônicos (README, MANUAL, SPEC, ESTADO) | ✅ HE-DOC-01 | revisão | este conjunto |
| Skills ECC versionadas no repositório (fonte padrão do attach) | ✅ HE-R1-01 | 10 testes offline + attach/remove real via CLI | `vendor/ecc/`; `tests/test_vendored_source.py` |
| `harnessctl project-doctor/plan/attach/verify/remove`: **pacote 2** (só regras do projeto, sem cópia de skills) | ✅ HE-R1-03, serve Claude Code e Codex | 15 testes offline; ensaio: plan real na plataforma (0 escritas), repo novo e clone da plataforma com remoção exata | `scripts/harnessctl.py`; `tests/test_repo_layer.py`; `evidence/HE_R1_03_REPO_LAYER.json` |
| Pacote 1 (antigo: skills copiadas no repo, `--preserve-contract`) | ⚠️ legado: ainda verifica e remove; `project-attach` responde `LEGACY_ATTACHED` com instrução de migração | testes offline | `tests/test_project_lifecycle.py` |
| `setup-harness` nova (sem `client` fixo; plano → "sim" → aplicar → verificar; "verificar" e "remover"), dentro do pacote da máquina, com migração do bootstrap antigo e do pacote da máquina antigo | ✅ HE-R1-04 + 04b; **ativada nesta máquina**. Chat novo: **Claude Code PASS**; **Codex PASS** na 3ª execução, depois de corrigir elevação no sandbox e dono do `.git` | 15 testes offline; migração real; `project-verify` OK confirmado à parte nas duas pastas de teste; o Codex usou a `verification-loop` por conta própria depois do setup (`BEHAVIOR_OBSERVED`, 1 execução) | `skills/setup-harness/`; `tests/test_setup_harness_v2.py`; `evidence/HE_R1_04_SETUP_HARNESS.json` |
| `setup-skill-plan/install/verify/remove` (bootstrap antigo) | ⚠️ obsoleto: ainda verifica e remove as versões antigas aprovadas; `machine-install` migra | testes offline | — |
| `setup-harness` instalada nesta máquina | ✅ em `~/.agents/skills`; o Claude Code a enxerga pela junction `~/.claude/skills → ~/.agents/skills` | descoberta nativa no Codex 0.166 (`DISCOVERED`) | `evidence/HE_OP_02B_ATIVACAO_DESCOBERTA.json` |
| Ensaio real na plataforma metalúrgica | ✅ patch com QA específico; ❌ suíte global com 2 falhas preexistentes | `BEHAVIOR_OBSERVED` na mesma sessão; turno novo `NOT_RUN` | `evidence/HE_OP_03_PLATAFORMA_METALURGICA.json`; [PR #216](https://github.com/Williamitiro/plataforma-metalurgica/pull/216) |
| Instalação permanente na plataforma | ✅ HE-R1-05 em PR, **sem merge**: `CLAUDE.md` + manifesto, `AGENTS.md` da plataforma preservado | `project-verify` OK; chat novo: Claude Code e Codex citam a regra de branch da plataforma e veem as 2 skills (`DISCOVERED`); suíte da plataforma 2040 passed, 16 falhas de caminho longo que passam com `--basetemp` curto; tarefa real com as skills `NOT_RUN` | `evidence/HE_R1_05_PLATAFORMA.json`; [PR #229](https://github.com/Williamitiro/plataforma-metalurgica/pull/229) |
| Camada 1 (máquina) para Claude Code + Codex: `machine-plan/install/verify/remove/discover` + `config/adapters.json` | ✅ HE-R1-02 (só as 2 skills ECC; a `setup-harness` entra no HE-R1-04) | 13 testes offline; **instalada nesta máquina**; `DISCOVERED` no Codex (`skills/list`, 0 turnos) e no Claude Code (sessão recebeu as skills) | `evidence/HE_R1_02_MACHINE_DISCOVERY.json`; `tests/test_machine_layer.py` |
| Benchmark A/B (R2) | ❌ `NOT_RUN` | — | `scripts/harness_eval.py` existe, mas com bugs (§3) |
| Linha de base de qualidade no uso real (HE-R2) | ✅ medida no histórico da plataforma, sem chamada de modelo: 238 PRs; 24 com revisão independente contada; **20 defeitos confirmados**, 1,05 por PR revisado com código; tokens do Claude em 171 de 231 PRs (mediana 36 mil de saída); Codex 0 (só revisa, na `main`). Lote isolado de 21 execuções: 8 rodadas, **inválidas** (D51 da plataforma e Python bloqueado no sandbox do Codex) | 9 testes offline; contagem conferida contra as tabelas dos PRs #244, #245, #247; revisões sem tabela (#163, #166, #167, #82) ficam `null` | `scripts/quality_baseline.py`; `evidence/HE_R2_BASELINE_QUALIDADE.json`; `benchmarks/r2/` |
| JEV via HTTPS (`jev_http.py`) | ✅ código e testes; smoke de 1 chamada observado | relatado pelo operador | `scripts/jev_http.py` |
| Piloto JEV A×J (3 classificações) | ⚠️ "COMPLETED, 3/3 nas duas condições" relatado pelo operador; o recibo no repo é da tentativa anterior, `ABORTED` | sem recibo do sucesso | `evidence/HE_JEV_007B_PILOT.json` |
| Isolamento G1 | ⚠️ MXC nativo do Codex: canários negados (observado); host Windows: reprovado | sem atestação externa | `evidence/HE_JEV_007A_*.json` |
| Claude Code em benchmark | ❌ nunca homologado | — | — |

## 2. Pendências, em ordem

1. **Revisar e fazer o merge do PR #4.** A `setup-harness` instalada aponta para `C:\dev\harness-engineering\scripts\harnessctl.py`;
   se aquele checkout sair desta branch, ela quebra.
2. **Plataforma: revisar e fazer o merge do [PR #229](https://github.com/Williamitiro/plataforma-metalurgica/pull/229)**
   (HE-R1-05). A correção de CRLF já entrou na `main` da plataforma (#224). Achado: com pasta temporária de caminho
   longo, 16 testes da plataforma falham no Windows; com `--basetemp` curto, passam.
3. **Checkout canônico em *detached*:** `C:\dev\harness-engineering` fica na ponta do PR #5, em *detached* (é de
   onde a camada do computador foi instalada; `machine-verify` OK em 05/11). Depois do merge, `git switch main` e `git pull` nessa pasta. Para desfazer agora, em `C:\dev\harness-engineering`: `machine-remove --apply`,
   depois `git switch codex/he-jev-007a` e `setup-skill-install --client codex --apply` (volta ao fluxo antigo).
4. **Primeira tarefa real na plataforma com as skills**, com revisão externa (critério de aceite do HE-R1-05).
5. **HE-R2: medir no uso real.** Kit na plataforma em [PR #252](https://github.com/Williamitiro/plataforma-metalurgica/pull/252) (3 skills: `karpathy-guidelines`, `search-first`, `systematic-debugging`; 2 regras de escopo; suíte 2222 passed). Revisão independente APROVADO COM RESSALVAS; os 8 achados foram corrigidos em 15141eb, e o merge entrou em 05/11/2026 (`be0a3b4`). A partir daí, trabalhar normalmente e rodar
   `scripts/quality_baseline.py` a cada lote de PRs, comparando com a linha de base. Defeito só conta se a revisão
   independente o publicar em tabela citando o PR de origem. Antes: decidir a regra D51 (o Codex recusa tarefa nova) e
   o Python no sandbox do Codex. O lote isolado (`scripts/r2_bench.py`) fica só para dúvidas pontuais.
6. **Alinhar SPEC e ESTADO sobre o R2.** A SPEC §6 define o R2 como A/B isolado (≥2 tarefas, k=3); o item 5 mede no
   uso real, antes × depois, sem grupo de controle. Decidir qual vale para "V1 pronto" e corrigir o outro documento.
7. **Antes do primeiro lote do R2:** (a) aumentar a cobertura de revisão independente (hoje 24 de 238 PRs); (b) fixar
   no `quality_baseline.py`, antes de olhar os dados, a métrica, a janela e o limite que contam como ganho.
8. **Depois do R2: ciclo de melhoria contínua** (observar → hipótese com evidência → teste candidata × atual →
   aprovação humana → nova linha de base). O agente analista só propõe; não altera gabarito, testes nem regras de
   segurança. Começar só com ~100 PRs revisados na linha de base. Sem nova plataforma: `quality_baseline.py` já cobre
   ETL e correlação; DuckDB só se a análise descer a eventos por chamada de ferramenta. LangSmith e Phoenix ficam como
   referência (Phoenix: Elastic License 2.0, exige servidor). Leitura: Self-Harness
   ([arXiv 2606.09498](https://arxiv.org/abs/2606.09498)) e Meta-Harness ([arXiv 2603.28052](https://arxiv.org/abs/2603.28052)).

## 3. Problemas conhecidos (abertos)

| Problema | Impacto | Corrigido em |
|---|---|---|
| `tdd-workflow` manda rodar `node $ECC_ROOT/scripts/setup-package-manager.js` (script não incluído) e as duas skills assumem projeto JavaScript (npm, tsc); os exemplos são em bash | em projeto Python ou sem Node, o agente precisa ignorar esses passos e usar o runner do projeto; rendimento menor | decidir no R2 (medir) se vale uma versão adaptada, como mudança revisada |
| O checkout desta worktree tinha `skills/` com CRLF (autocrlf), o principal com LF | hashes divergentes entre checkouts | `skills/** -text` (HE-R1-04) |
| Sandbox do Codex no Windows nega executar o Python do perfil ("Acesso negado") e um `git init` feito dentro dele deixa o `.git` com outro dono | sem elevação, o `$setup-harness` não funciona no Codex | ✅ HE-R1-04b: a skill roda `harnessctl` e `git init` com permissão elevada; `BLOCKED_GIT_OWNERSHIP` explica o caso |
| No Codex, cada execução do setup consumiu 150–275 mil tokens de entrada (mais de 90% em cache) | custo de contexto alto para uma tarefa simples | medir no R2 |
| Projetos com o pacote 1 têm cópia das skills ECC no repositório **e** a cópia da máquina | o Codex lista as duas (escopos `repo` e `user`) | migrar: `project-remove --apply` e depois `project-attach --apply` (nenhum projeto real está no pacote 1 hoje) |
| `CLAUDE.md` já existente não é lido, então o Harness não sabe se ele importa o `AGENTS.md` | o plano avisa (`PRESERVE_CHECK_IMPORT`); a linha `@AGENTS.md` precisa ser posta à mão | a `setup-harness` (HE-R1-04) orienta o usuário |
| Claude Code 2.1.268 desta máquina não lê `AGENTS.md` sozinho (só a partir da 2.1.277) | em projeto sem `CLAUDE.md`, o Claude não vê as regras | resolvido pelo pacote 2, que cria `CLAUDE.md` com `@AGENTS.md` |
| `~/.agents/skills` nesta máquina é um repositório Git do usuário | as 2 pastas e o recibo aparecem como arquivos não rastreados ali; o Harness não faz commit nem altera esse Git | decisão do usuário (commitar, ignorar ou deixar) |
| `harness_eval.py` começa tokens em `0` (linhas 342–343), o Claude roda com `json` e perde a trajetória, o Codex descarta tokens de cache e de raciocínio | métricas erradas | HE-R2-01 |
| O braço A do benchmark carregaria as skills globais | resultado falso de "empate" | HE-R2-02 |
| Gabarito JEV no mesmo repositório, 30 casos visíveis, sem anotador independente | não serve para benchmark real | R4 |
| Sem corte financeiro independente (limites são lógicos) | risco de gasto | antes de qualquer lote pago |
| Linha de base com 24 PRs revisados (1,05 defeito por PR) | queda de 30% nos defeitos só aparece com ~140 PRs revisados por período (estimativa Poisson, 80% de poder, α=5%; mais se os dados variarem muito); antes × depois sem controle mistura efeito da skill com troca de modelo, tipo de tarefa e revisor | §2 itens 6 e 7 |
| Fontes divergem se o `usage` do `turn.completed` no Codex é por turno ou acumulado na sessão | somar turnos pode contar tokens em dobro | conferir no HE-R2-01 |

## 4. Lições que viraram regra

Cada linha é um erro que aconteceu e a regra que ele gerou (detalhes em `historico/`).

| Aconteceu | Regra |
|---|---|
| Baseline A leu a solução no Git pai (`git show HEAD:…`) | workspace do agente sem `.git` nem histórico; apagar arquivos do HEAD não descontamina |
| "JEV 100% × 73,3%" calculado sobre previsões escritas à mão | separar tarefas cegas e gabarito; sintético é rotulado e nunca vira benchmark |
| Canário intacto chamado de "G1 PASS" | G1 = canários **negativos** por execução |
| `VERIFIED` e hash local aceitos como prova; flags de autodeclaração | sem atestador externo não há `VERIFIED`; flag não libera rede nem cobrança |
| Mock reproduzia o contrato MCP errado e o teste passava | testar contra o schema upstream pinado |
| `--clean` apagava pasta arbitrária | proibida a remoção automática; só remover o que o manifesto prova |
| Tokens e custo estimados (`len//4`, `0.0` em erro) | não medido = `null`; parcial nunca é total |
| Chave OpenRouter guardada como `TYPESAFE_API_KEY` | uma variável por provedor; destino explícito |
| `JEV_ERROR` genérico levou a dias de diagnóstico Node/MCP | códigos de erro fixos; diagnóstico gratuito antes de repetir o pago; preferir API direta (HTTP resolveu) |
| Testes verdes no local, CI vermelho | o estado oficial é o CI do HEAD; testes não dependem de binários locais |
| Skill presente nunca invocada (Antigravity) | provar cada nível: presente → descoberta → invocada → comportamento → resultado |
| 40+ documentos com status contraditórios | um ESTADO, uma SPEC, um MANUAL; relatórios novos são proibidos |
| Duas tarefas agendadas pararam em 3–4 s, no meio do trabalho, e o app marcou "succeeded" | rotina termina com uma linha verificável; status do app não é resultado (SPEC §10.5) |
| Uma arquitetura tratou o Hermes como secretário pessoal; no Core, o canal é empresarial (`WORK`) | antes de propor arquitetura, ler escopo, identidade e permissão no estado do próprio sistema |
| Modelo do OpenAI Dots citado a partir de fonte secundária | fato de produto vem da documentação oficial; se não houver, marcar como não confirmado |

## 5. Linha do tempo (resumo)

| Data | Marco | Resultado |
|---|---|---|
| 01/11 | A0: ciclo de arquivos das skills ECC, offline | PASS (estrutural) |
| 01/11 | HE-AG-001: Antigravity/Gemini A/B/C | parcial; skills nunca invocadas → runtime legado |
| 02/11 | A1: Codex A×C, "G1 PASS" | **contaminado**, invalidado pela errata |
| 02/11 | HE-JEV-001…006: coletor, avaliador, MCP, Infisical, canários, smoke | auditorias corrigiram falsos PASS; smoke de 1 chamada observado |
| 02/11 | HE-JEV-007A/B: G1 no MXC nativo; piloto | 007A observado; 007B `ABORTED`; JEV muda para HTTPS direto |
| 02/11 | SPEC V1 + dossiê de 12 repositórios | normativa até 03/11 (agora em `historico/`) |
| 02/11–03/11 | HE-OP-01/02/02B/03: lifecycle de projeto, bootstrap, `--preserve-contract`, ensaio na plataforma | ver §1 |
| 03/11 | HE-DOC-01: docs consolidados em 4; SPEC V2 (2 camadas, Claude Code no R1, correções do benchmark) | este conjunto |
| 05–07/11 | Modelo operacional: pesquisa de agentes pessoais, revisão cruzada Claude × Codex | SPEC §10; §7 abaixo |

## 6. Comandos que funcionam hoje

```bash
python -W error -m unittest discover -s tests
```

```bash
python scripts/harnessctl.py project-plan --repo C:/caminho/projeto
```

```bash
python scripts/harnessctl.py project-attach --repo C:/caminho/projeto --apply
```

```bash
python scripts/harnessctl.py project-verify --repo C:/caminho/projeto
```

```bash
python scripts/harnessctl.py project-remove --repo C:/caminho/projeto --apply
```

```bash
python scripts/harnessctl.py machine-plan
```

```bash
python scripts/harnessctl.py machine-install --apply
```

```bash
python scripts/harnessctl.py machine-verify
```

```bash
python scripts/harnessctl.py machine-discover
```

```bash
python scripts/harnessctl.py machine-remove --apply
```

JEV (chamada paga, exige autorização): `infisical run --env=dev -- python scripts/jev_http.py --one-call`.
Legados que **não** devem ser usados: `jev_live_smoke.py`, `run_jev_live_smoke.ps1`, `jev_startup_triage.py`,
`apply_direct_jev.py`, `jev_collector.py --mode live` e `prepare_blind_sandbox.py --clean`.

## 7. Modelo operacional (SPEC §10)

Conferido em 07/11/2026, somente leitura, nesta máquina e nos repositórios citados.

| Item | Status | Prova (nível) | Onde |
|---|---|---|---|
| Central `C:\dev\central-inteligencia` | `NOT_RUN`: a pasta não existe | — | HE-OM-01 |
| Thread coordenadora | `NOT_RUN` | — | HE-OM-03 |
| Escopo da máquina: skills | 7 skills em `~/.agents/skills` (Git próprio), lidas pelo Claude Code via `~/.claude/skills`: `coordenacao-claude-codex`, `git-lane-checkpoint`, `resiplac-vault-capture-global`, `reverse-engineer-anything`, `setup-harness`, `tdd-workflow`, `verification-loop` | listagem da pasta; uma sessão aberta no harness-engineering recebeu a skill da Vault (`DISCOVERED`) | `~/.agents/skills/README.md` |
| Escopo da máquina: MCPs de usuário | `gemini-notebook`, `rea`, `fish-audio` | `~/.claude.json`; carregados nesta sessão | — |
| Conectores Gmail/Agenda no Claude Code | `NOT_RUN`: não conferido em `/mcp` | — | HE-OM-02 |
| `~/.claude/CLAUDE.md` | 1 regra (skills estacionadas em `~/.claude/skills-off`) | leitura | — |
| Tarefas agendadas do desktop | 13 definições, 21 execuções, todas "succeeded"; 2 pararam em 3–4 s, no meio da tarefa (13/10, abertura e linha F1 do Nexus) | `list_task_runs` + transcrição das duas | HE-OM-04 |
| Hermes: agenda pelo WhatsApp (Entrega F do Core) | `INCONCLUSIVE`: duas negativas após confirmação em 02/11; jornada pendente | estado do Core | `resiplac-core/docs/CURRENT_STATE.yaml` (fonte da verdade) |

**Achados no Core (função real `resolveHermesWhatsappSourcePolicy`, executada localmente com `tsx` sobre o checkout
`ba7c090`, sem rede e sem produção):**

| Mensagem de teste | Rota | Leitura |
|---|---|---|
| "Agendar Alinhamento Operacional amanhã às 10h no Google Calendar" | `erp_operational` | "Operacional" no título manda para o ERP, mesmo citando o Google (`ERP_CALENDAR_PATTERN`) |
| "Agende no meu Google Calendar: Alinhamento Técnico amanhã às 10h" | `clarify` | a regra reconhece "agenda", mas não "agende" nem "Google Calendar" |
| "Crie na minha agenda pessoal: Alinhamento Técnico amanhã às 10h" | `personal_calendar` | sugere ao modelo só `personal.agenda.list`; `create`, `update` e `cancel` existem no serviço, mas não aparecem como candidatas (sugestão consultiva, `advisory_only`) |

O caminho de escrita está correto: reserva da operação, busca no Google pela chave de idempotência antes de inserir,
recibo e auditoria (`personal-agenda-service.ts`). Cada mensagem grava `CAPABILITY_ROUTER_SHADOW_DECISION` com a rota
e as candidatas, o que permite diagnosticar as tentativas de 02/11 com consulta só de leitura. A causa da segunda
negativa continua `INCONCLUSIVE`; nova homologação ao vivo: `NOT_RUN`.

**Pendências do modelo operacional, em ordem:**

1. HE-OM-03: abrir a thread coordenadora; primeiro entregável = diagnóstico "onde estamos" + fila de lanes.
2. HE-OM-01 e HE-OM-02: criar a Central e registrar o inventário do escopo da máquina.
3. Core, Entrega F (lane no `resiplac-core`, com revisão do Codex): diagnóstico só de leitura das tentativas de 02/11
   → conjunto fixo de frases de agenda como teste offline da rota → corrigir a causa comprovada → roteiro ao vivo do
   runbook (seção 7) → só então comparar modelos.
4. HE-OM-04: aplicar a regra de linha final verificável nas próximas rotinas agendadas.
5. Definir o destino de conhecimento **pessoal**, separado da Resiplac-Vault, antes de qualquer captura pessoal.
