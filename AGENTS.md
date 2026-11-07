# AGENTS.md — Harness Engineering

Contrato único para qualquer agente (Codex, Claude Code via `CLAUDE.md`, Cursor, OpenCode…) neste repositório.

## O que ler (e só isso)
1. [docs/ESTADO.md](docs/ESTADO.md): o que funciona hoje e a próxima entrega.
2. [docs/SPEC.md](docs/SPEC.md): regras, arquitetura, gates e backlog. **Normativa.**
3. [docs/MANUAL.md](docs/MANUAL.md): o fluxo que o usuário segue. Mantenha-o coerente com o código.

**Não leia `docs/historico/`** salvo quando uma tarefa pedir um fato específico de lá. É arquivo morto, com
afirmações superadas.

## Regras de trabalho
1. Antes de editar: `git status --short`, branch, HEAD, remoto e PR. Divergência ou alteração desconhecida →
   pare e relate (`BLOCKED`). Nunca use `reset --hard`, force-push ou limpeza destrutiva.
2. Reuso primeiro: recurso nativo, padrão aberto, API/CLI oficial e só então código novo mínimo. Sem novo runtime,
   MCP, Node ou daemon.
3. Uma entrega de escopo fechado por vez (ID do backlog da SPEC §10), com testes positivos e negativos e a suíte
   offline: `python -W error -m unittest discover -s tests` (com `JEV_REAL_INTEGRATION=0`).
4. Status sempre com nível de evidência (`PASS`, `FAIL`, `BLOCKED_*`, `NOT_RUN`, `INCONCLUSIVE`). Ausente é `null`,
   nunca `0`. Arquivo copiado não prova que a skill foi usada.
5. Ao concluir: atualize `docs/ESTADO.md` (uma linha na tabela + pendências). **Não crie relatórios novos em `docs/`**;
   evidência bruta vai para `docs/evidence/` (JSON) ou `.poc/` (ignorado).
6. Exigem autorização explícita do usuário: escrever em outro repositório ou na home, push, merge, deploy, chamadas
   pagas, instalar dependências ou alterar configuração global.

## Pedidos comuns do usuário
- **"Instale (ou atualize) o Harness neste computador"** → MANUAL §2: `scripts/harness_release.py install --tag
  <versão>` (plano), mostre o plano, aplique com `--apply` após o "sim" e confira com `harness_release.py status` e
  `harnessctl.py machine-discover`. Instale **só versões marcadas (tags)**, nunca de uma pasta de desenvolvimento ou
  worktree: a `setup-harness` guarda o caminho de quem instalou, e a versão fica em `~/.harness-engineering/<tag>`.
  `machine-install` direto e `setup-skill-*` não são o caminho normal.
- **"Configure o Harness no repositório X"** → use a skill `setup-harness` e a sequência canônica da SPEC §4.
