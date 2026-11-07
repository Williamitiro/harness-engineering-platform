# Manual do Harness Engineering

Este manual diz **o que você faz, em que ordem**. Ele não explica como o Harness funciona por dentro; isso está na
[SPEC](SPEC.md). Se um passo falhar, veja [Problemas comuns](#7-problemas-comuns).

> **O que já funciona hoje (03/11/2026)**
>
> | Passo | Claude Code | Codex |
> |---|---|---|
> | 1. Instalar no computador | ✅ feito neste computador (03/11) | ✅ feito neste computador (03/11) |
> | 2. Preparar um repositório | ✅ `/setup-harness` (primeiro teste em chat novo: pendente) ou comandos (§3.3) | ✅ `$setup-harness` (primeiro teste em chat novo: pendente) ou comandos (§3.3) |
> | 3. Trabalhar | ✅ normal | ✅ normal |
> | 4. Medir se ajuda (benchmark) | ⏳ ainda não existe | ⏳ ainda não existe |
>
> Este manual descreve o fluxo **definitivo**. O que ainda falta para o Harness V1 é o benchmark (passo 4).

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

## 2. Instalar no computador (uma vez só)

Faça isto uma vez em cada computador que você usa. O mesmo comando instala as três skills (`setup-harness`,
`tdd-workflow`, `verification-loop`) e, se encontrar uma instalação antiga do Harness, atualiza sozinho, sem tocar em
skills suas. **Rode sempre a partir de `C:\dev\harness-engineering`**: a `setup-harness` guarda o endereço de quem a
instalou.

**2.1. Ter a pasta do Harness.** Neste computador ela já existe em `C:\dev\harness-engineering`. Num computador
novo, abra o PowerShell e rode:

```bash
git clone https://github.com/Williamitiro/harness-engineering-platform.git C:\dev\harness-engineering
```

**2.2. Instalar.** Abra o **Claude Code** (ou o Codex) **dentro da pasta `C:\dev\harness-engineering`** e escreva:

> Instale o Harness neste computador.

O agente mostra o que vai copiar e para onde, pede o seu "sim", instala e confere. Ele só instala nas ferramentas
que encontrar no computador (Claude Code, Codex), e nunca sobrescreve uma skill sua com o mesmo nome. Se preferir
fazer sem o agente, os comandos são estes, um de cada vez:

```bash
python C:\dev\harness-engineering\scripts\harnessctl.py machine-plan
```

```bash
python C:\dev\harness-engineering\scripts\harnessctl.py machine-install --apply
```

```bash
python C:\dev\harness-engineering\scripts\harnessctl.py machine-discover
```

O primeiro mostra o plano sem gravar nada, o segundo instala e o terceiro confirma que o Codex enxerga as skills,
sem gastar nenhuma resposta do modelo.

**2.3. Conferir.** Feche e abra de novo o Claude Code (ou o Codex), em qualquer pasta, e escreva:

> Quais skills você tem disponíveis?

A resposta deve citar **`setup-harness`**, **`tdd-workflow`** e **`verification-loop`**. Se citar, a parte do
computador está pronta, para o Claude Code e o Codex ao mesmo tempo.

---

## 3. Preparar um repositório (uma vez por projeto)

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

**Os arquivos de regras são do projeto.** Depois de criados, o `AGENTS.md` e o `CLAUDE.md` são seus: edite à
vontade (por exemplo, a seção "Comandos do projeto"). Se um dia você remover o Harness, ele apaga só os que você
**não** editou.

### 3.3. Pelos comandos (funciona hoje, sem a skill)

Abra o PowerShell e rode, trocando o caminho pelo do seu projeto, um comando de cada vez:

```bash
python C:\dev\harness-engineering\scripts\harnessctl.py project-plan --repo C:\dev\meu-projeto
```

```bash
python C:\dev\harness-engineering\scripts\harnessctl.py project-attach --repo C:\dev\meu-projeto --apply
```

O primeiro só mostra o que faria (`PRESERVE` = mantém o seu arquivo; `WOULD_CREATE` = cria). O segundo aplica. Num
projeto que exige branch e PR, como a plataforma, rode numa branch nova e faça o PR dos arquivos criados.

---

## 4. Trabalhar no dia a dia

Depois do setup, **você não faz nada diferente.** Peça as tarefas como sempre. Quando fizer sentido, o agente usa
sozinho:

- **`tdd-workflow`**: escreve um teste que falha, depois o código que o faz passar;
- **`verification-loop`**: roda testes, lint e revisão antes de dizer "pronto".

Para forçar o uso de uma skill, cite o nome dela: *"use o tdd-workflow para corrigir este bug"*.

### 4.1. Onde abrir cada conversa

| Você quer… | Abra o chat em |
|---|---|
| pesquisar, estudar, comparar, ter uma ideia, resolver algo pessoal | **Central** (`C:\dev\central-inteligencia`) |
| decidir algo que envolve mais de um projeto | **Central** |
| implementar ou corrigir um sistema | a pasta **do sistema** (Resiplac Core, plataforma, Nexus…) |
| guardar o que vale a pena | peça *"salve isso na Vault"*: o agente só confirma com recibo |

Quando uma conversa na Central vira trabalho num sistema, peça ao agente o **pacote de delegação** (repositório,
decisão, escopo, critério de aceite, quem revisa) e abra a sessão no repositório com ele. As regras completas e o
motivo de cada decisão estão na [SPEC §10](SPEC.md#10-modelo-operacional-onde-trabalhar-o-que-é-global-e-como-coordenar).

---

## 5. Conferir, atualizar e remover

| Quero… | O que digito no repositório | O que acontece |
|---|---|---|
| **Conferir** se está tudo certo | `/setup-harness verificar` | compara os arquivos com o recibo e diz OK ou o que mudou |
| **Atualizar** depois de uma versão nova do Harness | primeiro, na pasta do Harness: `git pull` e o passo 2.2 de novo; depois, em cada repositório: `/setup-harness verificar` | o computador recebe as skills novas; o repositório só muda se a versão nova pedir, e sempre com o seu "sim" |
| **Remover** do projeto | `/setup-harness remover` | mostra o que vai apagar (só o que ele criou) e pede confirmação |
| **Remover do computador** | `python C:\dev\harness-engineering\scripts\harnessctl.py machine-remove` (prévia) e depois o mesmo comando com `--apply` | apaga só as skills que o Harness instalou; se você editou alguma, ele para e não apaga nada |

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
| "installed by another Harness checkout" | o Harness foi instalado a partir de outra pasta | rode os comandos a partir da pasta indicada na mensagem, ou remova de lá e reinstale a partir de `C:\dev\harness-engineering` |
| "UPGRADE_AVAILABLE" | há uma versão nova do Harness | refaça o passo 2.2: ele atualiza sozinho |
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
