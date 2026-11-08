# Estado do Harness Engineering

**Atualizado em 07/11/2026.** Este é o único lugar com status. Ao concluir uma entrega, atualize a tabela §1 e as
pendências §2. Não crie relatórios novos.

**Tudo está no `main`** desde 07/11/2026: o merge do [PR #5](https://github.com/Williamitiro/harness-engineering-platform/pull/5)
(`baf91cd`) levou junto o [PR #4](https://github.com/Williamitiro/harness-engineering-platform/pull/4), e depois entrou o
[PR #6](https://github.com/Williamitiro/harness-engineering-platform/pull/6) (`7098393`, HE-R2-01 e CI) e o
[PR #10](https://github.com/Williamitiro/harness-engineering-platform/pull/10) (`9929a5d`, HE-R1-06, tag `v1.1.0`). **Este
computador roda a versão `v1.2.0`** (desde 08/11/2026; antes, `v1.1.0` e `v1.0.0`), instalada em `C:\Users\itiro\.harness-engineering\v1.2.0` por
`scripts/harness_release.py` (atalho `current`); a pasta `C:\dev\harness-engineering` é só de desenvolvimento e
trocar de branch nela não afeta o instalado.

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
| Instalação permanente na plataforma | ✅ HE-R1-05 **no `main` da plataforma desde 07/11/2026** (`be0435d`): `CLAUDE.md` + manifesto, `AGENTS.md` da plataforma preservado. Antes do merge: branch atualizada com a `main` (#287 e #288), suíte 2550 passed / 563 skipped / 0 failed, revisão independente APROVADO COM RESSALVAS (ressalva do glossário corrigida) | `project-verify` OK; chat novo: Claude Code e Codex citam a regra de branch da plataforma e veem as 2 skills (`DISCOVERED`); suíte da plataforma 2040 passed, 16 falhas de caminho longo que passam com `--basetemp` curto; tarefa real com as skills `NOT_RUN` | `evidence/HE_R1_05_PLATAFORMA.json`; [PR #229](https://github.com/Williamitiro/plataforma-metalurgica/pull/229) |
| Camada 1 (máquina) para Claude Code + Codex: `machine-plan/install/verify/remove/discover` + `config/adapters.json` | ✅ HE-R1-02 (só as 2 skills ECC; a `setup-harness` entra no HE-R1-04) | 13 testes offline; **instalada nesta máquina**; `DISCOVERED` no Codex (`skills/list`, 0 turnos) e no Claude Code (sessão recebeu as skills) | `evidence/HE_R1_02_MACHINE_DISCOVERY.json`; `tests/test_machine_layer.py` |
| Benchmark A/B (R2) | ❄️ congelado (HE-R1-06); nunca rodou (`NOT_RUN`) | — | `scripts/harness_eval.py` |
| Telemetria do runner (HE-R2-01): Claude em `stream-json --verbose` (trajetória, modelo, versão, skills, tokens com cache, custo estimado); Codex com os 5 campos de `usage`, último total (não a soma); `null` ≠ 0; `--model`/`--effort` fixados e registrados; versão do CLI no lugar do caminho do binário | ✅ código | 21 testes offline novos (parser + runner com subprocess simulado); semântica do `usage` do Codex lida no fonte `rust-v0.166.0` (`event_processor_with_jsonl_output.rs`). Execução real `NOT_RUN` | `scripts/native_telemetry.py`; `scripts/harness_eval.py`; `tests/test_native_telemetry.py`; `tests/test_harness_eval.py` |
| CI | ✅ 07/11: actions fixadas por SHA (checkout v7.0.1, setup-python v7.1.0), Python 3.12 fixado, suíte offline também em **Windows**, `compileall` de tudo, Dependabot mensal só para actions; integração npm do `jev-code` (legado) só sob demanda | verde no GitHub no PR #6, inclusive `unit (windows-latest)` (runs 42388089286 e 42388117073) | `.github/workflows/quality.yml`; `.github/dependabot.yml` |
| Linha de base de qualidade no uso real (HE-R2) | ✅ medida no histórico da plataforma, sem chamada de modelo: 238 PRs; 24 com revisão independente contada; **20 defeitos confirmados**, 1,05 por PR revisado com código; tokens do Claude em 171 de 231 PRs (mediana 36 mil de saída); Codex 0 (só revisa, na `main`). Lote isolado de 21 execuções: 8 rodadas, **inválidas** (D51 da plataforma e Python bloqueado no sandbox do Codex) | 9 testes offline; contagem conferida contra as tabelas dos PRs #244, #245, #247; revisões sem tabela (#163, #166, #167, #82) ficam `null` | `scripts/quality_baseline.py`; `evidence/HE_R2_BASELINE_QUALIDADE.json`; `benchmarks/r2/` |
| JEV via HTTPS (`jev_http.py`) | ✅ código e testes; smoke de 1 chamada observado | relatado pelo operador | `scripts/jev_http.py` |
| Piloto JEV A×J (3 classificações) | ⚠️ "COMPLETED, 3/3 nas duas condições" relatado pelo operador; o recibo no repo é da tentativa anterior, `ABORTED` | sem recibo do sucesso | `evidence/HE_JEV_007B_PILOT.json` |
| Isolamento G1 | ⚠️ MXC nativo do Codex: canários negados (observado); host Windows: reprovado | sem atestação externa | `evidence/HE_JEV_007A_*.json` |
| Claude Code em benchmark | ❌ nunca homologado | — | — |
| Repositórios ligados ao Harness (pacote 2) | ✅ **7 com o Harness no `main` desde 07/11/2026**: plataforma-metalurgica ([#229](https://github.com/Williamitiro/plataforma-metalurgica/pull/229)), [engenharia-reversa#2](https://github.com/Williamitiro/engenharia-reversa/pull/2), [negocios-com-evidencia#2](https://github.com/Williamitiro/negocios-com-evidencia/pull/2) (`AGENTS.md` criado do modelo), [nexus-engineering-control#73](https://github.com/Williamitiro/nexus-engineering-control/pull/73), [nexus-quant#509](https://github.com/Williamitiro/nexus-quant/pull/509), [resiplac-core#81](https://github.com/Williamitiro/resiplac-core/pull/81) e [video-motion#5](https://github.com/Williamitiro/video-motion/pull/5) (nesses dois, o `CLAUDE.md` existente ganhou só a linha `@AGENTS.md`) no `main`; [itiro-negocios-ideias#2](https://github.com/Williamitiro/itiro-negocios-ideias/pull/2) na branch do PR #1 (onde está o `AGENTS.md`), chega ao `main` com o #1. ⚠️ [cad#1](https://github.com/Williamitiro/cad/pull/1): no PR único do cad (Draft), **sem merge** (decisão do proprietário). Fora: `frontend-resiplac`, `modelo-de-negocio-resiplac` (alterações não commitadas) e `resiplac-institucional` (remoto fora do GitHub) | `project-verify` OK em cada cópia antes do PR; depois do merge, `.harness/manifest.json` e `@AGENTS.md` conferidos na branch de destino no remoto | `harnessctl project-attach` |
| Instalação por versão marcada (`harness_release.py install --tag … --apply` / `status`): extrai a tag sem `.git` em `~/.harness-engineering/<tag>`, troca a instalação (remove com o instalador antigo, instala e confere com o novo), aponta `current`; se a nova falhar, reinstala a anterior; sem `--apply` não grava nada | ✅ código; usada neste computador (`v1.0.0` e depois a troca para `v1.1.0`, `INSTALLED`) | 7 testes offline em home e repositório Git sintéticos: instalação nova, troca de versão com a antiga intacta, idempotência, prévia sem escrita, recusa de branch e de tag inexistente, recusa de pasta adulterada, volta automática à versão anterior | `scripts/harness_release.py`; `tests/test_harness_release.py`; MANUAL §2 |
| Kit simplificado (HE-R1-06): pacote da máquina só com `setup-harness`; atualizar a partir da `v1.0.0` tira `tdd-workflow` e `verification-loop` (se intactas); modelo `AGENTS.md` com 5 regras curtas no lugar de "use a skill X"; R2 congelado e V1 = R1 (SPEC §1, §2.7, §5) | ✅ **instalado neste computador** na `v1.1.0` em 07/11/2026: `harness_release.py install --apply` → `INSTALLED`; `status` → `machine_verify: FILE_HASHES_OK_RUNTIME_NOT_VERIFIED`; `machine-discover` → Codex `setup-harness` `DISCOVERED`; `tdd-workflow` e `verification-loop` saíram de `~/.agents/skills`, as outras skills do usuário ficaram. Claude Code: `MANUAL_CHECK_REQUIRED` (chat novo). Regras no `AGENTS.md` dos 7 repositórios ligados no `main` em 08/11 (§2 item 2) | 8 testes offline novos e os de atualização reescritos: pacote só com `setup-harness`, atualização da v1.0.0 e do pacote anterior, remoção do pacote antigo pelo código novo, skill antiga editada ou de versão desconhecida bloqueia sem escrever, recibo antigo sem o pin do ECC (ou novo com ele) bloqueia, skill do usuário com nome de skill retirada fica intacta, modelo `AGENTS.md` não cita skill retirada. Uso em 03–07/11 (`daily_report.py`, 110 sessões): `tdd-workflow` em 9, `verification-loop` em 11; skills do ambiente (`resiplac-*`, `nexus-*`, `git-lane-checkpoint`) somam mais | `scripts/harnessctl.py`; `templates/repo/AGENTS.md`; `tests/test_machine_layer.py`; `tests/test_setup_harness_v2.py` |
| `setup-harness` oferece as regras de trabalho que faltam num `AGENTS.md` já existente (HE-R1-07): passo 6 do setup e ao "verificar"; o agente compara com a seção "Como trabalhar" do modelo, mostra o que falta e o que já está coberto, e só edita com o "sim"; o instalador continua sem ler o projeto (SPEC §4) | ✅ **instalado na `v1.2.0`** em 08/11/2026 ([PR #13](https://github.com/Williamitiro/harness-engineering-platform/pull/13)): `INSTALLED`, `machine_verify` OK, Codex `DISCOVERED`. Ensaio só de leitura do passo 6 na plataforma-metalurgica: 5/5 cobertas, nada proposto, 7 ambiguidades corrigidas. Setup real com edição `NOT_RUN` | 1 teste offline novo (a skill aponta para o modelo, compara a cobertura e exige o "sim"; o modelo tem a seção "Como trabalhar"). Motivo: os 7 PRs de 07–08/11 foram feitos à mão porque o setup não oferecia as regras | `skills/setup-harness/SKILL.md`; `tests/test_setup_harness_v2.py` |
| Relatório diário de funcionamento | ✅ código | 9 testes offline; rodado nas sessões reais de 07/11 (9 sessões). Só contagens e nomes, nenhum texto de conversa. **Não é benchmark** | `scripts/daily_report.py`; `tests/test_daily_report.py`; MANUAL §4 |

## 2. Pendências, em ordem

1. **Pendentes da ligação:** o PR #1 do cad (frente única, com outros trabalhos) e o PR #1 do itiro-negocios-ideias
   são decisão do proprietário. `frontend-resiplac` e `modelo-de-negocio-resiplac`: ligar depois de resolver as
   alterações locais (`/setup-harness` no repositório). Checkouts principais que não estão no `main` só passam a ter
   o Harness quando a branch deles incorporar o `main` (os que estavam limpos no `main` foram atualizados em 07/11).
2. **Regras do HE-R1-06 nos repositórios ligados: ✅ no `main` dos 7 desde 08/11/2026**, cada um com revisão
   independente registrada no PR:
   [plataforma-metalurgica#294](https://github.com/Williamitiro/plataforma-metalurgica/pull/294) (`04d5515a`; branch
   atualizada com a `main`, índices regerados, suíte inteira 2853 passed / 564 skipped / 0 failed, D52),
   [engenharia-reversa#3](https://github.com/Williamitiro/engenharia-reversa/pull/3),
   [nexus-engineering-control#74](https://github.com/Williamitiro/nexus-engineering-control/pull/74) (com recibo em
   `docs/runs/`), [nexus-quant#514](https://github.com/Williamitiro/nexus-quant/pull/514) (revisão vale como a de
   integração de `shared_paths`), [resiplac-core#90](https://github.com/Williamitiro/resiplac-core/pull/90)
   (`scope_change` confirmado pelo proprietário), [video-motion#7](https://github.com/Williamitiro/video-motion/pull/7)
   e [negocios-com-evidencia#3](https://github.com/Williamitiro/negocios-com-evidencia/pull/3) (modelo novo e
   `.gitattributes` corrigido: a ligação de 07/11 tinha juntado duas linhas). Ficaram nos repositórios, fora do Harness:
   no nexus-engineering-control, `scripts/check_canonical.py` falha no `main` (anterior ao #74), então o
   `verify_local.sh` que a regra nova pede não chega a `PASS`; no nexus-quant, o `AGENTS.md` está a 16 bytes do limite
   de 6.000 e a ~6 bytes da meta de 70% do gate de contexto; no negocios-com-evidencia, o PR #1 (rascunho) mexe no
   `.gitattributes` e precisa de rebase.
3. **Rodar `scripts/daily_report.py` no fim de cada dia de trabalho** (MANUAL §4) e anotar aqui o que falhar
   (skill nunca usada, sessão terminando com teste falhando, erros de ferramenta recorrentes).
4. **Primeira tarefa real na plataforma com o Harness**, com revisão externa (critério de aceite do HE-R1-05).
5. **Revisão independente em todo PR com código** (hoje 24 de 238 PRs revisados na plataforma), com os recursos
   nativos: o Codex revisando no GitHub ou o `/code-review` do Claude Code. Exigir a revisão por proteção de branch no
   GitHub é configuração do repositório e precisa de autorização.
6. **Kit da plataforma (PR #252):** `karpathy-guidelines`, `search-first` e `systematic-debugging` ficam em
   `.claude/skills/` da plataforma como estão. Não viram globais, e a medição antes × depois não vale como prova.

**Congelados por HE-R1-06** (não retomar sem uma dúvida pontual e autorização; texto mantido como registro):

7. ❄️ **HE-R2: medir no uso real.** Kit na plataforma em [PR #252](https://github.com/Williamitiro/plataforma-metalurgica/pull/252) (3 skills: `karpathy-guidelines`, `search-first`, `systematic-debugging`; 2 regras de escopo; suíte 2222 passed). Revisão independente APROVADO COM RESSALVAS; os 8 achados foram corrigidos em 15141eb, e o merge entrou em 05/11/2026 (`be0a3b4`). A partir daí, trabalhar normalmente e rodar
   `scripts/quality_baseline.py` a cada lote de PRs, comparando com a linha de base. Defeito só conta se a revisão
   independente o publicar em tabela citando o PR de origem. Antes: decidir a regra D51 (o Codex recusa tarefa nova) e
   o Python no sandbox do Codex. O lote isolado (`scripts/r2_bench.py`) fica só para dúvidas pontuais.
8. ❄️ ~~Alinhar SPEC e ESTADO sobre o R2~~: resolvido por HE-R1-06, que tira o R2 do critério de "V1 pronto".
9. ❄️ **Antes do primeiro lote do R2:** (a) aumentar a cobertura de revisão independente (hoje 24 de 238 PRs); (b) fixar
   no `quality_baseline.py`, antes de olhar os dados, a métrica, a janela e o limite que contam como ganho.
10. ❄️ **Depois do R2: ciclo de melhoria contínua** (observar → hipótese com evidência → teste candidata × atual →
   aprovação humana → nova linha de base). O agente analista só propõe; não altera gabarito, testes nem regras de
   segurança. Começar só com ~100 PRs revisados na linha de base. Sem nova plataforma: `quality_baseline.py` já cobre
   ETL e correlação; DuckDB só se a análise descer a eventos por chamada de ferramenta. LangSmith e Phoenix ficam como
   referência (Phoenix: Elastic License 2.0, exige servidor). Leitura: Self-Harness
   ([arXiv 2606.09498](https://arxiv.org/abs/2606.09498)) e Meta-Harness ([arXiv 2603.28052](https://arxiv.org/abs/2603.28052)).

## 3. Problemas conhecidos (abertos)

| Problema | Impacto | Corrigido em |
|---|---|---|
| `tdd-workflow` manda rodar `node $ECC_ROOT/scripts/setup-package-manager.js` (script não incluído) e as duas skills assumem projeto JavaScript (npm, tsc); os exemplos são em bash | em projeto Python ou sem Node, o agente precisa ignorar esses passos e usar o runner do projeto; rendimento menor | ✅ HE-R1-06: as duas saíram do pacote da máquina; o modelo `AGENTS.md` manda rodar os comandos do projeto |
| O checkout desta worktree tinha `skills/` com CRLF (autocrlf), o principal com LF | hashes divergentes entre checkouts | `skills/** -text` (HE-R1-04) |
| Sandbox do Codex no Windows nega executar o Python do perfil ("Acesso negado") e um `git init` feito dentro dele deixa o `.git` com outro dono | sem elevação, o `$setup-harness` não funciona no Codex | ✅ HE-R1-04b: a skill roda `harnessctl` e `git init` com permissão elevada; `BLOCKED_GIT_OWNERSHIP` explica o caso |
| No Codex, cada execução do setup consumiu 150–275 mil tokens de entrada (mais de 90% em cache) | custo de contexto alto para uma tarefa simples | medir no R2 |
| Projetos com o pacote 1 têm cópia das skills ECC no repositório **e** a cópia da máquina | o Codex lista as duas (escopos `repo` e `user`) | migrar: `project-remove --apply` e depois `project-attach --apply` (nenhum projeto real está no pacote 1 hoje) |
| `CLAUDE.md` já existente não é lido, então o Harness não sabe se ele importa o `AGENTS.md` | o plano avisa (`PRESERVE_CHECK_IMPORT`); a linha `@AGENTS.md` precisa ser posta à mão | a `setup-harness` (HE-R1-04) orienta o usuário |
| Claude Code 2.1.268 desta máquina não lê `AGENTS.md` sozinho (só a partir da 2.1.277) | em projeto sem `CLAUDE.md`, o Claude não vê as regras | resolvido pelo pacote 2, que cria `CLAUDE.md` com `@AGENTS.md` |
| `~/.agents/skills` nesta máquina é um repositório Git do usuário | as 2 pastas e o recibo aparecem como arquivos não rastreados ali; o Harness não faz commit nem altera esse Git | decisão do usuário (commitar, ignorar ou deixar) |
| `harness_eval.py` começa tokens em `0` (linhas 342–343), o Claude roda com `json` e perde a trajetória, o Codex descarta tokens de cache e de raciocínio | métricas erradas | ✅ HE-R2-01 (07/11) |
| CLIs desta máquina atrás do upstream em 07/11: Claude Code 2.1.268 (npm: 2.1.319), Codex 0.166.0 (npm: 0.167.0) | o Claude local ainda não lê `AGENTS.md` sozinho (2.1.277+); benchmark deve fixar e registrar a versão usada | atualizar é mudança global: só com autorização; o runner já registra a versão |
| O braço A do benchmark carregaria as skills globais | resultado falso de "empate" | HE-R2-02 (❄️ congelado) |
| Gabarito JEV no mesmo repositório, 30 casos visíveis, sem anotador independente | não serve para benchmark real | R4 |
| Sem corte financeiro independente (limites são lógicos) | risco de gasto | antes de qualquer lote pago |
| Linha de base com 24 PRs revisados (1,05 defeito por PR) | queda de 30% nos defeitos só aparece com ~140 PRs revisados por período (estimativa Poisson, 80% de poder, α=5%; mais se os dados variarem muito); antes × depois sem controle mistura efeito da skill com troca de modelo, tipo de tarefa e revisor | é o motivo do congelamento do R2 (HE-R1-06) |
| Fontes divergiam se o `usage` do `turn.completed` no Codex é por turno ou acumulado na sessão | somar turnos contaria tokens em dobro | ✅ HE-R2-01: no fonte `rust-v0.166.0` é o total acumulado (`usage.total`) e o `exec` encerra após o 1º turno; `native_telemetry` e `r2_bench.parse_events` usam o último, e tudo `0` vira `null` |

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
| Kit de skills genéricas instalado para "medir no uso real" sem volume para detectar o efeito; `tdd-workflow` exigia um script Node ausente | regra antes de skill (SPEC §2.7); medir só o que o volume consegue mostrar |

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
