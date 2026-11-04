# HE-OP-02B — skill pessoal setup-harness

Implementação autorizada pelo pedido de concluir o fluxo de setup, após HE-OP-02 (`bac90f4`). Mesma branch `codex/he-jev-007a`, PR #4 Draft. Não foi instalado nada na home real do operador nem em projetos consumidores.

## Entrega e uso

Skill versionada em `skills/setup-harness/SKILL.md`, com política Codex de invocação explícita em `agents/openai.yaml`. Usa o CLI central, não inclui runtime nem scripts do Harness no projeto. Formato conferido com [OpenAI Docs: Build skills](https://learn.chatgpt.com/docs/build-skills) e com a skill `skill-creator`; `quick_validate.py` aprovado. A política explícita segue o acionamento deliberado da SPEC §2.1. A instrução preserva autorização já dada para o repo/arquivos exatos, exige plano antes da cópia e não autoriza modelos, benchmark, Git remoto, hooks ou serviços.

Comandos para o operador (a instalação pessoal modifica somente o diretório declarado e exige aprovação):

```powershell
python C:/dev/harness-engineering/scripts/harnessctl.py setup-skill-plan --client codex
python C:/dev/harness-engineering/scripts/harnessctl.py setup-skill-install --client codex --apply
python C:/dev/harness-engineering/scripts/harnessctl.py setup-skill-verify --client codex
# Na sessão nativa após instalação e descoberta: $setup-harness
python C:/dev/harness-engineering/scripts/harnessctl.py setup-skill-remove --client codex
python C:/dev/harness-engineering/scripts/harnessctl.py setup-skill-remove --client codex --apply
```

Sem `--home`, o CLI usa a home do usuário atual. `--home CAMINHO` permite teste/instalação em home explicitamente escolhida. Codex recebe `.agents/skills/setup-harness/`; Claude recebe `.claude/skills/setup-harness/`. O diretório contém skill, descritor `harness-location.json`, registro `.harness-bootstrap.json` e, para Codex, `agents/openai.yaml`. O descritor informa caminho absoluto do CLI central, sugestão de ECC existente (`.poc/ecc-pinned`) e cliente. Não é copiado nenhum token, ambiente, gabarito ou runner.

Plan é somente-leitura. Install exige `--apply`, usa criação exclusiva e rollback compartilhados com HE-OP-02. Diretório `setup-harness` já existente sem registro válido bloqueia, mesmo com bytes iguais. Reaplicação verifica hashes e é idempotente. Verify/remove validam os paths exatos e hashes antes de agir; arquivo ou descritor alterado bloqueia remoção, sem sobrescrita. Diretórios e skills pessoais de terceiros são preservados. Sem `--apply`, remove só apresenta a prévia.

A variante pessoal Claude pode ser distribuída e verificada como arquivo, mas informa `BLOCKED_CLIENT_R3` ao pedir lifecycle de projeto: não habilita paridade Claude nem usa pacote Codex como fallback. Essa limitação é explícita no descritor (`project_client_supported=false`) e no corpo da skill.

## Evidências

- RED inicial: testes do instalador falharam por ausência das funções.
- `python -W error -m unittest discover -s tests -p test_setup_skill.py -v`: **8 testes**, OK, sem skips, 0,276 s. Instalar/verificar/reaplicar/remover para ambos os clientes em home sintética; colisões, alteração de descritor/skill, symlink de ancestral, falha parcial, ausência de `--apply` e preservação de skill alheia.
- Revalidação HE-OP-02: **10 testes**, OK, 10,088 s; lifecycle legado: **14 testes**, OK, 9,612 s.
- Suíte completa: **148 testes**, OK, **2 skips opt-in** (146 passaram), 22,578 s, `JEV_REAL_INTEGRATION=0`. Log local `.poc/he-op-02b-offline.log`. Skips locais: integração de pacote upstream e integração nativa MXC.
- `python .../skill-creator/scripts/quick_validate.py skills/setup-harness`: `Skill is valid!`; compilação de CLI/testes e `git diff --check` aprovados.
- Smoke ponta a ponta por subprocessos CLI, com ECC real pinado: instalar/verificar bootstrap de ambos os clientes em home sintética; obter descritor Codex; doctor/plan/attach/verify/remove em repo Git novo; remover ambos os bootstraps. **Rollback exato do projeto e da home sintética**. Recibo `.poc/he-op-02b-smoke.json`.
- Sondagens Git de fonte e destino agora compartilham ambiente mínimo, sem chaves/GIT overrides, hooks, fsmonitor, optional locks ou inspeção de submódulos. A guarda de ancestrais da fonte foi reaproveitada para os SKILL.md concretos.

## Critérios e pendências reais

**Código e testes offline de HE-OP-02/02B concluídos.** Não confundir o smoke do CLI com invocação da skill por um modelo. Não houve instalação pessoal aprovada na home real nem sessão Codex carregando `$setup-harness` em repo vazio; portanto descoberta/invocação/comportamento nativo continuam **NOT_RUN**. O gate completo HE-OP-02B exige essa prova, conforme SPEC §2.1. O CLI direto continua utilizável independentemente dela.

Para fechar R1 faltam essa validação nativa após opt-in e HE-OP-03 (projeto escolhido, mudança real e QA externo). R2 continua integralmente pendente: A/B real, custos/cotas/tempo/tokens, tentativas e decisão Harbor. Não foram executados modelos pagos ou benchmarks; métricas de modelo e custo não foram inventadas. Nenhuma configuração global/hook, clone ou instalação de upstream foi feito por inferência. CI do HEAD publicado é conferido no relatório de entrega.

Limitações de ownership, concorrência e quedas abruptas são as registradas no relatório HE-OP-02. A localização central é pinada na instalação; se o Harness ou a skill central mudar, hashes divergentes bloqueiam. Não há migração/autoatualização implícita. Rollback pessoal é `setup-skill-remove --apply` quando a verificação passa; se alterado, preservar e revisar, sem remoção ampla.
