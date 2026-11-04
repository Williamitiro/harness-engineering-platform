# Manual do Harness Engineering

Este manual diz **o que você faz, em que ordem**. Ele não explica como o Harness funciona por dentro; isso está na
[SPEC](SPEC.md). Se um passo falhar, veja [Problemas comuns](#7-problemas-comuns).

> **O que já funciona hoje (03/11/2026)**
>
> | Passo | Claude Code | Codex |
> |---|---|---|
> | 1. Instalar no computador | 🔧 em implementação | ✅ funciona (versão antiga, só a skill de setup) |
> | 2. Preparar um repositório | 🔧 em implementação | ✅ funciona (com o CLI; ver [ESTADO](ESTADO.md)) |
> | 3. Trabalhar | ✅ normal | ✅ normal |
> | 4. Medir se ajuda (benchmark) | ⏳ ainda não existe | ⏳ ainda não existe |
>
> Este manual descreve o fluxo **definitivo**. Os passos marcados 🔧 ficam prontos na próxima etapa de
> implementação; até lá, não os execute.

---

## 1. A ideia em 30 segundos

O Harness é um **kit de regras e skills** que deixa o Claude Code e o Codex mais disciplinados: escrever o teste
antes, verificar antes de dizer "pronto", não apagar trabalho dos outros.

Ele tem **duas partes**, e cada uma é instalada **uma vez**:

| Parte | Onde fica | Quando você instala | O que contém |
|---|---|---|---|
| **No computador** | sua pasta de usuário (`C:\Users\itiro\.agents\skills`) | uma vez por computador | as skills genéricas, iguais para todos os projetos |
| **No repositório** | dentro de cada projeto | uma vez por projeto | as regras **daquele** projeto (`AGENTS.md`) e um recibo do que foi instalado |

### ❌ O que você NÃO faz

**Não copie a pasta `C:\dev\harness-engineering` para dentro dos seus projetos.** Nunca. Essa pasta é a
"fábrica": ela fica num lugar só e entrega a cada projeto apenas os 2 a 4 arquivos pequenos de que ele precisa. Quem
faz essa entrega é a skill **`setup-harness`**, e você só precisa chamá-la.

---

## 2. Instalar no computador (uma vez só) 🔧

Faça isto uma vez em cada computador que você usa.

**2.1. Ter a pasta do Harness.** Neste computador ela já existe em `C:\dev\harness-engineering`. Num computador
novo, abra o PowerShell e rode:

```bash
git clone https://github.com/Williamitiro/harness-engineering-platform.git C:\dev\harness-engineering
```

**2.2. Instalar.** Abra o **Claude Code** (ou o Codex) **dentro da pasta `C:\dev\harness-engineering`** e escreva:

> Instale o Harness neste computador.

O agente mostra o que vai copiar e para onde, pede o seu "sim", instala e confere. Se preferir fazer sem o agente,
o comando equivalente é:

```bash
python C:\dev\harness-engineering\scripts\harnessctl.py machine-install --apply
```

**2.3. Conferir.** Feche e abra de novo o Claude Code (ou o Codex), em qualquer pasta, e escreva:

> Quais skills você tem disponíveis?

A resposta deve citar **`setup-harness`**, **`tdd-workflow`** e **`verification-loop`**. Se citar, a parte do
computador está pronta, para o Claude Code e o Codex ao mesmo tempo.

---

## 3. Preparar um repositório (uma vez por projeto) 🔧

O comando é o mesmo para projeto novo e projeto antigo. A skill descobre sozinha qual é o caso.

| Ferramenta | O que você digita no chat |
|---|---|
| Claude Code | `/setup-harness` |
| Codex | `$setup-harness` |

### 3.1. Projeto novo (pasta vazia)

1. Crie a pasta. Exemplo: `C:\dev\meu-projeto-novo`.
2. Abra o Claude Code (ou o Codex) **nessa pasta**.
3. Digite `/setup-harness` (ou `$setup-harness` no Codex).
4. O agente vai:
   - perguntar se pode iniciar o Git na pasta, caso ela ainda não seja um repositório;
   - mostrar a lista de arquivos que vai criar (`AGENTS.md`, `CLAUDE.md`, `.harness/manifest.json`);
   - pedir o seu "sim";
   - criar os arquivos e conferir.
5. Pronto. Comece a programar normalmente.

### 3.2. Projeto que já existe (plataforma-metalurgica, Nexus Quant, Resiplac Core, Video Motion…)

1. Abra o Claude Code (ou o Codex) **na pasta do projeto**.
2. Digite `/setup-harness` (ou `$setup-harness`).
3. O agente vai:
   - **ler sem alterar nada** e mostrar o que encontrou: se já há `AGENTS.md`, `CLAUDE.md` ou skills próprias;
   - **preservar** as regras que já existem, sem apagar ou reescrever nada seu;
   - propor os arquivos novos e, se o projeto exigir, criar uma **branch** e um **PR** em vez de mexer na `main`;
   - pedir o seu "sim", aplicar e conferir.
4. Revise o PR, como faria com qualquer outra mudança, e faça o merge.

> **Regra de ouro:** o setup nunca apaga nem reescreve um arquivo que não foi ele que criou. Se encontrar um
> conflito, ele **para e pergunta**.

---

## 4. Trabalhar no dia a dia

Depois do setup, **você não faz nada diferente.** Peça as tarefas como sempre. Quando fizer sentido, o agente usa
sozinho:

- **`tdd-workflow`**: escreve um teste que falha, depois o código que o faz passar;
- **`verification-loop`**: roda testes, lint e revisão antes de dizer "pronto".

Para forçar o uso de uma skill, cite o nome dela: *"use o tdd-workflow para corrigir este bug"*.

---

## 5. Conferir, atualizar e remover

| Quero… | O que digito no repositório | O que acontece |
|---|---|---|
| **Conferir** se está tudo certo | `/setup-harness verificar` | compara os arquivos com o recibo e diz OK ou o que mudou |
| **Atualizar** depois de uma versão nova do Harness | primeiro, na pasta do Harness: `git pull` e o passo 2.2 de novo; depois, em cada repositório: `/setup-harness verificar` | o computador recebe as skills novas; o repositório só muda se a versão nova pedir, e sempre com o seu "sim" |
| **Remover** do projeto | `/setup-harness remover` | mostra o que vai apagar (só o que ele criou) e pede confirmação |

---

## 6. Saber se o Harness realmente ajuda

Instalar não prova que ajuda: pesquisas de 2026 mostram que muitas skills populares **não mudam nada**, e algumas
atrapalham. Por isso o Harness terá um **benchmark** que põe o mesmo agente para resolver as mesmas tarefas **com**
e **sem** o kit e compara acerto, tempo, tokens e custo. Ele ainda não existe; quando existir, este manual terá a
seção "Rodar o benchmark".

---

## 7. Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| O agente não conhece `/setup-harness` | o passo 2 não foi feito, ou o chat foi aberto antes dele | refaça o passo 2.3 e reabra o chat |
| "BLOCKED_COLLISION" | já existe um arquivo com o mesmo nome no projeto | normal: o setup para em vez de sobrescrever; leia a opção que ele propõe |
| "harnessctl não encontrado" | a pasta `C:\dev\harness-engineering` foi movida ou apagada | coloque-a de volta (passo 2.1) e refaça o passo 2.2 |
| O agente não usa as skills | elas são opcionais e o agente decide quando usar | cite o nome da skill no pedido |
| Quero ver o estado técnico | — | [ESTADO.md](ESTADO.md) |

---

## 8. Glossário rápido

- **Skill**: um arquivo de instruções (`SKILL.md`) que o agente lê quando o assunto aparece. É como um procedimento
  operacional padrão.
- **`AGENTS.md`**: as regras do projeto. Codex, Cursor e outros leem direto; o Claude Code lê através do
  `CLAUDE.md`.
- **Manifesto** (`.harness/manifest.json`): o recibo do que o Harness instalou no projeto. Permite conferir e
  remover sem apagar nada seu.
- **Harness** (no sentido amplo): a ferramenta onde o modelo trabalha (Claude Code, Codex, Cursor…). O nosso
  "Harness Engineering" é o kit que melhora o trabalho dentro delas.
