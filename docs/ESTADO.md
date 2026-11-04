# Estado do Harness Engineering

**Atualizado em 03/11/2026.** Este é o único lugar com status. Ao concluir uma entrega, atualize a tabela §1 e as
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
| `setup-harness` nova (sem `client` fixo; plano → "sim" → aplicar → verificar; "verificar" e "remover"), dentro do pacote da máquina, com migração do bootstrap antigo e do pacote da máquina antigo | ✅ HE-R1-04 código; ⏳ **ativação na home real pendente** (ver §2) | 12 testes offline; migração ensaiada com os bytes reais instalados | `skills/setup-harness/`; `tests/test_setup_harness_v2.py`; `evidence/HE_R1_04_SETUP_HARNESS.json` |
| `setup-skill-plan/install/verify/remove` (bootstrap antigo) | ⚠️ obsoleto: ainda verifica e remove as versões antigas aprovadas; `machine-install` migra | testes offline | — |
| `setup-harness` instalada nesta máquina | ✅ em `~/.agents/skills`; o Claude Code a enxerga pela junction `~/.claude/skills → ~/.agents/skills` | descoberta nativa no Codex 0.166 (`DISCOVERED`) | `evidence/HE_OP_02B_ATIVACAO_DESCOBERTA.json` |
| Ensaio real na plataforma metalúrgica | ✅ patch com QA específico; ❌ suíte global com 2 falhas preexistentes | `BEHAVIOR_OBSERVED` na mesma sessão; turno novo `NOT_RUN` | `evidence/HE_OP_03_PLATAFORMA_METALURGICA.json`; [PR #216](https://github.com/Williamitiro/plataforma-metalurgica/pull/216) |
| Instalação permanente na plataforma | ❌ não feita | — | o pacote foi removido após o ensaio |
| Camada 1 (máquina) para Claude Code + Codex: `machine-plan/install/verify/remove/discover` + `config/adapters.json` | ✅ HE-R1-02 (só as 2 skills ECC; a `setup-harness` entra no HE-R1-04) | 13 testes offline; **instalada nesta máquina**; `DISCOVERED` no Codex (`skills/list`, 0 turnos) e no Claude Code (sessão recebeu as skills) | `evidence/HE_R1_02_MACHINE_DISCOVERY.json`; `tests/test_machine_layer.py` |
| Benchmark A/B (R2) | ❌ `NOT_RUN` | — | `scripts/harness_eval.py` existe, mas com bugs (§3) |
| JEV via HTTPS (`jev_http.py`) | ✅ código e testes; smoke de 1 chamada observado | relatado pelo operador | `scripts/jev_http.py` |
| Piloto JEV A×J (3 classificações) | ⚠️ "COMPLETED, 3/3 nas duas condições" relatado pelo operador; o recibo no repo é da tentativa anterior, `ABORTED` | sem recibo do sucesso | `evidence/HE_JEV_007B_PILOT.json` |
| Isolamento G1 | ⚠️ MXC nativo do Codex: canários negados (observado); host Windows: reprovado | sem atestação externa | `evidence/HE_JEV_007A_*.json` |
| Claude Code em benchmark | ❌ nunca homologado | — | — |

## 2. Pendências, em ordem

1. **Revisar e fazer o merge do PR #4.** A `setup-harness` instalada aponta para `C:\dev\harness-engineering\scripts\harnessctl.py`;
   se aquele checkout sair desta branch, ela quebra.
2. **Plataforma: suíte global verde**, em PR próprio na plataforma. Ordem de serviço pronta para colar na thread:
   [historico/2026-11-03_OS_PLATAFORMA_SUITE_VERDE.md](historico/2026-11-03_OS_PLATAFORMA_SUITE_VERDE.md).
3. **Ativar a `setup-harness` nova nesta máquina.** Ela precisa ser instalada a partir de
   `C:\dev\harness-engineering` (o descritor aponta para o `harnessctl` de quem instala), e esse checkout ainda não
   tem o código novo. Depois do merge dos PRs #4 e #5 (ou com o checkout nessa versão): `machine-install --apply`
   (migra sozinho) e o teste em chat novo, `/setup-harness` no Claude Code e `$setup-harness` no Codex.
4. **HE-R1-05:** instalação permanente na plataforma, via PR. HE-R1-01 a HE-R1-04 concluídos no código.
4. **HE-R2-01 → HE-R2-03:** benchmark.

## 3. Problemas conhecidos (abertos)

| Problema | Impacto | Corrigido em |
|---|---|---|
| `tdd-workflow` manda rodar `node $ECC_ROOT/scripts/setup-package-manager.js` (script não incluído) e as duas skills assumem projeto JavaScript (npm, tsc); os exemplos são em bash | em projeto Python ou sem Node, o agente precisa ignorar esses passos e usar o runner do projeto; rendimento menor | decidir no R2 (medir) se vale uma versão adaptada, como mudança revisada |
| A `setup-harness` **instalada hoje** ainda é a antiga (descritor com `client: codex` e `ecc_source` em `.poc`); o Claude Code lê a versão de Codex | resolvido no código (HE-R1-04): `machine-install` migra | ativação pendente (§2 item 3) |
| O checkout desta worktree tinha `skills/` com CRLF (autocrlf), o principal com LF | hashes divergentes entre checkouts | `skills/** -text` (HE-R1-04) |
| Projetos com o pacote 1 têm cópia das skills ECC no repositório **e** a cópia da máquina | o Codex lista as duas (escopos `repo` e `user`) | migrar: `project-remove --apply` e depois `project-attach --apply` (nenhum projeto real está no pacote 1 hoje) |
| `CLAUDE.md` já existente não é lido, então o Harness não sabe se ele importa o `AGENTS.md` | o plano avisa (`PRESERVE_CHECK_IMPORT`); a linha `@AGENTS.md` precisa ser posta à mão | a `setup-harness` (HE-R1-04) orienta o usuário |
| Claude Code 2.1.268 desta máquina não lê `AGENTS.md` sozinho (só a partir da 2.1.277) | em projeto sem `CLAUDE.md`, o Claude não vê as regras | resolvido pelo pacote 2, que cria `CLAUDE.md` com `@AGENTS.md` |
| `~/.agents/skills` nesta máquina é um repositório Git do usuário | as 2 pastas e o recibo aparecem como arquivos não rastreados ali; o Harness não faz commit nem altera esse Git | decisão do usuário (commitar, ignorar ou deixar) |
| `harness_eval.py` começa tokens em `0` (linhas 342–343), o Claude roda com `json` e perde a trajetória, o Codex descarta tokens de cache e de raciocínio | métricas erradas | HE-R2-01 |
| O braço A do benchmark carregaria as skills globais | resultado falso de "empate" | HE-R2-02 |
| Gabarito JEV no mesmo repositório, 30 casos visíveis, sem anotador independente | não serve para benchmark real | R4 |
| Sem corte financeiro independente (limites são lógicos) | risco de gasto | antes de qualquer lote pago |

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
