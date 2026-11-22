---
name: setup-harness
description: Preparar, verificar ou remover o Harness Engineering num repositório Git, novo ou existente, e organizar a documentação dele (planta de documentos, tetos, limpeza), sempre preservando as regras que o projeto já tem. Use quando o usuário pedir /setup-harness, $setup-harness, "setup do Harness", "verificar o Harness" ou "remover o Harness".
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
`project-verify` → `OK` (com `docs.status` `PASS` ou `null`; `NOT_RUN` não é OK: relate o motivo);
`project-remove` → `PLANNED_NOT_REMOVED`, `REMOVED_EXACT_OWNED_FILES` ou
`ALREADY_REMOVED`. Saída com código diferente de 0 e `"status": "BLOCKED"` é um bloqueio: mostre o motivo. `project-verify` com
`DOCS_FAIL` (código 1) não é bloqueio: a lista `docs.problems` diz o que corrigir na etapa de documentos.
`NOT_ATTACHED` (código 1): o Harness não está ligado; ofereça o setup.

## O que o usuário pediu

- **"verificar"** → `project-verify`, que confere as duas coisas. Arquivos: `UNCHANGED` (igual ao modelo),
  `EDITED_BY_PROJECT` (editado pelo projeto, o que é normal) e `MISSING` (apagado). Documentos (`docs`): `PASS`;
  `FAIL` com a lista `problems`; `null` com `SEM_PLANTA` (o repositório ainda não tem planta: não é falha, nunca
  diga 0). Se o `AGENTS.md` é do projeto, pergunte se o usuário quer conferir as regras de trabalho (passo 6). Se
  os documentos deram `FAIL` ou `SEM_PLANTA`, ofereça a etapa de documentos (passo 7). Não mude nada sem o "sim".
  Pare aqui.
- **"remover"** → `project-remove` sem `--apply` (prévia). Mostre o que será apagado e o que fica. Com o "sim",
  rode de novo com `--apply`. Pare aqui.
- **qualquer outro pedido** → setup, abaixo.

## Setup

1. Leia as regras do projeto (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`) para saber se ele exige branch, PR
   ou cópia isolada. Não as edite agora: só os passos 5 a 8 propõem mudanças, e só com o "sim".
2. Rode `project-plan`. Explique em linguagem simples:
   - `WOULD_CREATE`: arquivo novo, criado a partir do modelo do Harness;
   - `PRESERVE`: arquivo do projeto, mantido como está;
   - `BLOCKED_*`: pare, explique o motivo e não contorne;
   - `docs_policy` diz o que acontece com a planta de documentos (`.harness/docs-policy.json`): `WOULD_CREATE`
     (repositório novo: nasce do modelo), `PRESERVE` (já existe: só conferir no passo 7) ou
     `PROPOSE_WITH_DOCS_PLAN` (repositório existente sem planta: o passo 7 propõe uma com as pastas que ele já usa);
   - status `ATTACHED`: já instalado, então faça a verificação e siga para os passos 6 a 8;
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
7. **Documentos** (depois do attach e do verify; também ao "verificar", com o "sim"). A planta é
   `.harness/docs-policy.json`; tetos padrão: `AGENTS.md` 8 KB, estado 5 KB, índice 10 KB. Três casos:
   - **Sem planta** (`docs.status` `null`, `SEM_PLANTA`): rode `docs-plan --repo "<CAMINHO>"` (só leitura) e
     proponha o arquivo com as pastas **que o repositório já usa**: cada pasta de `md_by_dir` num tipo (`vigente`,
     `pesquisa`, `evidencia`, `arquivo` ou um tipo próprio) ou no `ignore`, e os papéis `entry`, `state` e `index`
     nos arquivos que já fazem esse papel. Nada é renomeado para caber no padrão. Peça o "sim" por pasta, não por
     arquivo; com mais de 15 pastas (monorepo), agrupe por `md_by_top` com padrões `pasta/**`. Vale o padrão mais
     específico (`docs/historico/**` ganha de `docs/**`); pasta só com arquivos soltos é `pasta/*.md`. Se os tetos
     estourarem, siga para o caso seguinte no mesmo PR.
   - **Acima do teto ou com documento superado** (`docs.problems`, ou o que o texto dos próprios documentos
     disser): faça a limpeza pelas regras abaixo.
   - **Planta e tudo dentro do teto** (`docs.status` `PASS`): só confira e diga isso.
   Se o setup criou o `AGENTS.md` do modelo num repositório que já existia, a seção "Onde gravar" dele cita caminhos
   padrão: ajuste-a à planta aprovada, ou tire a seção se o usuário não quiser planta.
   Depois de qualquer mudança, rode `docs-check --repo "<CAMINHO>"`, depois o mesmo com `--base origin/<padrão>`
   (a branch padrão do remoto: `git symbolic-ref --short refs/remotes/origin/HEAD`; sem remoto, a branch base local),
   e de novo `project-verify`, que precisa dar `OK` com `docs.status` `PASS`. `DOCS_NOT_RUN` não é sucesso: relate o
   motivo.
8. **CI:** se o repositório já tem `.github/workflows/`, ofereça o job de documentos: copiar
   `<pasta do Harness>/templates/ci/harness-docs-check.yml` para `.github/workflows/`. Ele chama a action do Harness
   fixada por tag; troque `TAG` pela versão instalada (o nome da pasta para onde aponta o atalho `current`). Só com
   o "sim". Sem CI no repositório, não crie um.
9. Em repositório novo, sugira preencher a seção "Comandos do projeto" do `AGENTS.md`.
10. Relate o que foi criado, o que foi mantido, as regras acrescentadas ou já cobertas, a planta, o que foi movido
    e o próximo passo: commit e PR, feitos pelo usuário ou com pedido explícito.

## Regras de limpeza (passo 7)

- **Nada é apagado.** O que está superado sai com `git mv` para a pasta `arquivo` da planta. Só documentação:
  não mexa em código, testes, configuração, hooks nem validadores do repositório.
- **Só vai para o arquivo o que está claramente superado**: o próprio texto diz, ou outro documento o substituiu.
  "Antigo" ou "fora do índice" não basta. Na dúvida, fica.
- **Antes de mover, procure o caminho** em documentos **e** em código, scripts, testes e configuração. Se algo lê
  o arquivo, ele não muda de lugar: dê a ele o tipo `arquivo` na planta, onde está (arquivar no lugar).
- **Índice ou estado gerado ou lido por programa:** não mexa no programa. Dê o papel a outro arquivo ou deixe o
  papel fora da planta (`null`).
- **Validador próprio que já limita um arquivo:** use o mesmo teto na planta, ou deixe o papel fora dela.
- **Pasta com índice próprio:** tipo próprio na planta, fora da lista `indexed`. A planta v1 tem um índice só por
  repositório: use esse contorno e registre como pendência se não bastar.
- **AGENTS.md:** regra geral fica por inteiro. Regra de uma área vai para um documento da área e, no `AGENTS.md`,
  vira a linha "Vai mexer em X? Leia antes, obrigatório: <link>". Regra em vigor nunca vai para a pasta de arquivo.
- **Tetos:** quando um papel passa do teto, corte até ficar em no máximo 85% do teto (estado de 5 KB: até 4,3 KB;
  `AGENTS.md` de 8 KB: até 6,8 KB); dentro do teto, não corte. Se as regras gerais do `AGENTS.md` não couberem, suba
  o teto dele até 10 KB e avise o usuário; se nem assim chegarem a 85%, não resuma regra geral: avise e deixe acima.
- **Corte do estado:** faça `git mv` do estado inteiro para a pasta de arquivo (com a data no nome, por exemplo
  `ESTADO_ATE_2026-11-22.md`) e escreva um estado novo e curto com o que vale hoje. Não apague trechos dele.
- **Planta e corte do estado no mesmo PR.** Se houver outro PR aberto que mexe no estado, o papel `state` fica
  `null` até o corte.
- **Arquivo gerado:** regere só se o resultado mudar apenas o que este trabalho causou; se mudar mais, não regere
  e registre. Conferência que já falhava na `main`: registre e siga.
- **Não guarde cópia do texto antigo:** o `git mv` já preserva o histórico.
- **Conferência:** `docs-check` verde (também com `--base origin/<padrão>`), os validadores e testes do próprio
  repositório, e um teste negativo desfeito depois (por exemplo, um `.md` solto na raiz recusado e depois apagado).
- **Revisão independente antes do relato**, por um subagente que não fez o trabalho e recebe só o diff. Ele
  confere: nenhum `.md` apagado; conteúdo movido igual ao original; tabela regra por regra do `AGENTS.md` antigo
  contra o novo (regra sumida é erro); links abrem; nenhum código aponta para caminho antigo; todo `.md` cai num
  tipo ou no `ignore`; nenhum arquivo que não é documentação mudou; o estado novo bate com a realidade. Corrija o
  que ele achar antes de relatar. Sem ferramenta de subagente, diga isso e marque a revisão como `NOT_RUN`.
- **Paradas da limpeza:** Git sujo ou branch divergente, a proposta e o merge. A proposta tem tudo de uma vez: a
  planta, o que vai para o arquivo, e **quais regras saem do `AGENTS.md` e para onde** (tabela regra por regra).
  Na limpeza, nada mais: o resto, as regras acima decidem. Os outros passos mantêm o seu "sim".

## Limites

Não configure MCP, hooks, Node, credenciais nem preferências globais (o hook de documentos é do computador,
MANUAL §5). Não rode modelos pagos, benchmark, commit,
push, merge ou deploy como efeito do setup. Não mexa em skills de terceiros. Instalar arquivos não prova que as
skills serão usadas.
