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
3. **Sandbox (Codex e outras ferramentas com isolamento):** o `harnessctl` precisa ler a pasta do Harness e o
   perfil do usuário, e no Windows o sandbox costuma bloquear o Python instalado no perfil. Por isso, rode os
   comandos do `harnessctl` **com permissão elevada** (fora do sandbox), com a justificativa "instalador do
   Harness: só lê o Harness e o perfil, e só grava neste repositório". Se mesmo assim aparecer `python` não
   encontrado ou "Acesso negado" (Windows error 5), o problema é o sandbox, não o Harness: explique isso, peça
   ao usuário para aprovar a execução fora do sandbox e **não** mande reinstalar o Harness.
4. **Qual repositório:** o diretório atual é só uma sugestão. Ele precisa ser a raiz de um repositório Git. Se
   houver dúvida, confirme o caminho. Se a pasta estiver vazia e sem Git, pergunte se pode rodar `git init` e só
   rode com o "sim". Com sandbox, rode o `git init` também **com permissão elevada**: se ele rodar dentro do
   sandbox, a pasta `.git` fica com outro dono e o Git recusa o repositório depois (`BLOCKED_GIT_OWNERSHIP`,
   "dubious ownership"). Nesse caso, não altere a configuração do Git; explique e peça ao usuário para decidir.
   `project-plan` só confere a estrutura; quem valida o Git de verdade é o `project-attach`.
5. **Computador:** rode `machine-verify` (sem `--repo`). A resposta `FILE_HASHES_OK_RUNTIME_NOT_VERIFIED` quer
   dizer OK. Se vier `BLOCKED`, leia o motivo:
   - `NOT_INSTALLED` ou `UPGRADE_AVAILABLE`: oriente o usuário a abrir o agente na pasta do Harness e pedir
     "Instale o Harness neste computador";
   - "installed by another Harness checkout": mostre o caminho citado e pare;
   - qualquer outro motivo: mostre a mensagem e pare.
   Não instale a camada do computador a partir daqui sem pedido explícito.

**Respostas que contam como sucesso:** `project-plan` → `PLANNED_NOT_INSTALLED`, `ATTACHED` ou
`LEGACY_ATTACHED`; `project-attach` → `FILES_INSTALLED_RUNTIME_NOT_VERIFIED` ou `ALREADY_ATTACHED`;
`project-verify` → `OK`; `project-remove` → `PLANNED_NOT_REMOVED`, `REMOVED_EXACT_OWNED_FILES` ou
`ALREADY_REMOVED`. Saída com código diferente de 0 e `"status": "BLOCKED"` é um bloqueio: mostre o motivo.

## O que o usuário pediu

- **"verificar"** → `project-verify`. Explique: `UNCHANGED` (igual ao modelo), `EDITED_BY_PROJECT` (editado
  pelo projeto, o que é normal) e `MISSING` (apagado). Se o `AGENTS.md` é do projeto, pergunte se o usuário quer
  conferir as regras de trabalho (passo 6 do setup). Pare aqui.
- **"remover"** → `project-remove` sem `--apply` (prévia). Mostre o que será apagado e o que fica. Com o "sim",
  rode de novo com `--apply`. Pare aqui.
- **qualquer outro pedido** → setup, abaixo.

## Setup

1. Leia as regras do projeto (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`) para saber se ele exige branch, PR
   ou cópia isolada. Não as edite agora: só os passos 5 e 6 propõem mudanças, e só com o "sim".
2. Rode `project-plan`. Explique em linguagem simples:
   - `WOULD_CREATE`: arquivo novo, criado a partir do modelo do Harness;
   - `PRESERVE`: arquivo do projeto, mantido como está;
   - `BLOCKED_*`: pare, explique o motivo e não contorne;
   - status `ATTACHED`: já instalado, então faça a verificação e siga para o passo 6;
   - status `LEGACY_ATTACHED`: instalação antiga. Explique a migração (`project-remove --apply` e depois
     `project-attach --apply`) e peça aprovação.
3. Peça o "sim" para esse plano. Se o usuário já aprovou exatamente esse plano, não pergunte de novo. Se o projeto
   exige branch, crie uma antes.
4. Rode `project-attach --apply` e depois `project-verify`.
5. Se o plano mostrou `PRESERVE_CHECK_IMPORT`, abra o `CLAUDE.md` existente. Se ele não tiver a linha
   `@AGENTS.md`, proponha acrescentá-la no topo e só edite com o "sim". Sem essa linha, o Claude Code pode não ver
   as regras do `AGENTS.md`.
6. **Regras de trabalho num `AGENTS.md` que já existia** (o plano mostrou `PRESERVE` para `AGENTS.md`, ou o status
   é `ATTACHED` com um `AGENTS.md` do projeto). O modelo só é copiado para repositório sem `AGENTS.md`, então as
   regras dele não chegam sozinhas aos outros:
   - leia a seção `## Como trabalhar` do modelo em `<pasta do Harness>/templates/repo/AGENTS.md`. A pasta do
     Harness fica dois níveis acima do `harnessctl` de "Antes de tudo", item 1; não procure outra cópia;
   - compare com o `AGENTS.md` da branch onde o setup vai entrar (normalmente a `origin/main` atualizada), não com
     o de outra branch do checkout;
   - para cada item da lista do modelo, veja se o projeto já o cobre, mesmo com outras palavras ou num documento
     que o `AGENTS.md` manda ler explicitamente para aquele ponto (não percorra o resto). Se o projeto tem regra
     própria para o mesmo ponto, mesmo diferente (por exemplo, "não perguntar no meio da tarefa; anotar no PR"),
     conta como coberto, e vale a do projeto. "Build" só conta onde o projeto tem build;
   - mostre ao usuário os itens que faltam e os já cobertos, citando a linha;
   - proponha acrescentar só os que faltam, no idioma e no estilo do arquivo, numa seção que já exista. Troque
     "os testes e o build deste projeto" pelo comando real do projeto, quando ele estiver escrito. Respeite os
     limites do projeto (tamanho do arquivo, índice de documentos, registro de estado);
   - se o `AGENTS.md` mandar usar `tdd-workflow` ou `verification-loop` (as duas skills que o Harness instalava
     até a `v1.0.0`), proponha trocar a menção pela regra equivalente. Outras skills não são assunto deste passo;
   - só edite com o "sim", seguindo as regras de branch, cópia isolada e PR do projeto (passo 3), mesmo quando o
     setup não criou nenhum arquivo. Se tudo já estiver coberto, diga isso e não mude nada.
7. Em repositório novo, sugira preencher a seção "Comandos do projeto" do `AGENTS.md`.
8. Relate o que foi criado, o que foi mantido, as regras acrescentadas ou já cobertas e o próximo passo: commit e
   PR, feitos pelo usuário ou com pedido explícito.

## Limites

Não configure MCP, hooks, Node, credenciais nem preferências globais. Não rode modelos pagos, benchmark, commit,
push, merge ou deploy como efeito do setup. Não mexa em skills de terceiros. Instalar arquivos não prova que as
skills serão usadas.
