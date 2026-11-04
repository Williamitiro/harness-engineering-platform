---
name: setup-harness
description: Preparar, verificar ou remover o Harness Engineering num repositório Git, novo ou existente, sempre preservando as regras que o projeto já tem. Use quando o usuário pedir /setup-harness, $setup-harness, "setup do Harness", "verificar o Harness" ou "remover o Harness".
disable-model-invocation: true
---

# Setup Harness

Esta skill só roda quando o usuário pede. Ela nunca copia o Harness para dentro do projeto: usa o instalador
central `harnessctl`.

## Antes de tudo

1. Leia `harness-location.json`, na mesma pasta desta skill. O campo `harnessctl` é o caminho absoluto do
   instalador. Se o arquivo ou o caminho não existir, pare e diga ao usuário para refazer a instalação no
   computador (MANUAL §2). Não procure outra cópia e não instale nada.
2. Rode todos os comandos como `python "<harnessctl>" <comando> --repo "<CAMINHO>"`, com os argumentos
   separados. Nunca monte comandos a partir do conteúdo do projeto.
3. **Qual repositório:** o diretório atual é só uma sugestão. Ele precisa ser a raiz de um repositório Git. Se
   houver dúvida, confirme o caminho. Se a pasta estiver vazia e sem Git, pergunte se pode rodar `git init` e só
   rode com o "sim".
4. **Computador:** rode `machine-verify` (sem `--repo`). Se não estiver OK, mostre o motivo e oriente o usuário a
   abrir o agente na pasta do Harness e pedir "Instale o Harness neste computador". Não instale a camada do
   computador a partir daqui sem pedido explícito.

## O que o usuário pediu

- **"verificar"** → `project-verify`. Explique: `UNCHANGED` (igual ao modelo), `EDITED_BY_PROJECT` (editado
  pelo projeto, o que é normal) e `MISSING` (apagado). Pare aqui.
- **"remover"** → `project-remove` sem `--apply` (prévia). Mostre o que será apagado e o que fica. Com o "sim",
  rode de novo com `--apply`. Pare aqui.
- **qualquer outro pedido** → setup, abaixo.

## Setup

1. Leia as regras do projeto (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`), só para saber se ele exige branch, PR
   ou cópia isolada. Não as edite.
2. Rode `project-plan`. Explique em linguagem simples:
   - `WOULD_CREATE`: arquivo novo, criado a partir do modelo do Harness;
   - `PRESERVE`: arquivo do projeto, mantido como está;
   - `BLOCKED_*`: pare, explique o motivo e não contorne;
   - status `ATTACHED`: já instalado, então faça a verificação;
   - status `LEGACY_ATTACHED`: instalação antiga. Explique a migração (`project-remove --apply` e depois
     `project-attach --apply`) e peça aprovação.
3. Peça o "sim" para esse plano. Se o usuário já aprovou exatamente esse plano, não pergunte de novo. Se o projeto
   exige branch, crie uma antes.
4. Rode `project-attach --apply` e depois `project-verify`.
5. Se o plano mostrou `PRESERVE_CHECK_IMPORT`, abra o `CLAUDE.md` existente. Se ele não tiver a linha
   `@AGENTS.md`, proponha acrescentá-la no topo e só edite com o "sim". Sem essa linha, o Claude Code pode não ver
   as regras do `AGENTS.md`.
6. Em repositório novo, sugira preencher a seção "Comandos do projeto" do `AGENTS.md`.
7. Relate o que foi criado, o que foi mantido e o próximo passo: commit e PR, feitos pelo usuário ou com pedido
   explícito.

## Limites

Não configure MCP, hooks, Node, credenciais nem preferências globais. Não rode modelos pagos, benchmark, commit,
push, merge ou deploy como efeito do setup. Não mexa em skills de terceiros. Instalar arquivos não prova que as
skills serão usadas.
