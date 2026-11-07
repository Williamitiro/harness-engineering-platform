# Manual do Harness Engineering

Este manual diz **o que você faz, em que ordem**. Ele não explica como o Harness funciona por dentro; isso está na
[SPEC](SPEC.md). Se um passo falhar, veja [Problemas comuns](#7-problemas-comuns).

> **Situação em 07/11/2026**
>
> | Passo | Claude Code | Codex |
> |---|---|---|
> | 1. Instalar no computador | ✅ feito neste computador, versão `v1.0.0` | ✅ idem |
> | 2. Preparar um repositório | ✅ feito em 7 repositórios (no `main` deles); nos outros, `/setup-harness` | ✅ idem, com `$setup-harness` |
> | 3. Trabalhar | ✅ normal | ✅ normal |
> | 4. Ver se está funcionando (relatório do dia) | ✅ §4.1 | ✅ §4.1 |
> | 5. Medir se ajuda (benchmark) | ⏳ ainda não existe | ⏳ ainda não existe |

---|---|---|
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

O Harness é instalado a partir de uma **versão fixa** (ex.: `v1.0.0`), numa pasta só dele:

| Pasta | Para quê |
|---|---|
| `C:\dev\harness-engineering` | onde o Harness é **desenvolvido**. Trocar de branch aqui **não afeta** o que está instalado |
| `C:\Users\itiro\.harness-engineering\v1.0.0` | a versão **instalada**: cópia exata da versão marcada, sem Git, que ninguém edita |
| `C:\Users\itiro\.harness-engineering\current` | atalho para a versão em uso; é o caminho dos comandos deste manual |

É o mesmo padrão de `pipx`, `uv tool` e Homebrew: o que está instalado não muda até você instalar outra versão.

**2.1. Ter a pasta do Harness.** Neste computador ela já existe em `C:\dev\harness-engineering`. Num computador
novo, abra o PowerShell e rode:

```bash
git clone https://github.com/Williamitiro/harness-engineering-platform.git C:\dev\harness-engineering
```

**2.2. Ver o plano** (não grava nada):

```bash
python C:\dev\harness-engineering\scripts\harness_release.py install --tag v1.0.0
```

**2.3. Instalar:**

```bash
python C:\dev\harness-engineering\scripts\harness_release.py install --tag v1.0.0 --apply
```

Ele extrai a versão, instala as três skills (`setup-harness`, `tdd-workflow`, `verification-loop`) para o Claude Code
e o Codex, confere os arquivos e aponta o atalho `current`. Se já havia uma instalação, ele a remove antes e, se a
nova falhar, volta à anterior. Nunca sobrescreve uma skill sua com o mesmo nome.

**2.4. Conferir:**

```bash
python C:\dev\harness-engineering\scripts\harness_release.py status
```

Deve mostrar a versão (`release.tag`) e `machine_verify: FILE_HASHES_OK_RUNTIME_NOT_VERIFIED` (arquivos íntegros).
Depois, abra o Claude Code ou o Codex em qualquer pasta e pergunte *"Quais skills você tem disponíveis?"*. A
resposta deve citar `tdd-workflow` e `verification-loop`. A `setup-harness` só aparece quando você a chama.

**Atualizar para uma versão nova** (ex.: `v1.1.0`): `git -C C:\dev\harness-engineering fetch --tags` e repita
2.2 e 2.3 com a tag nova. A versão anterior continua na pasta dela, para voltar se precisar.

### 2.5. Antes de formatar o computador

**Ainda não há restauração completa homologada.** A instalação acima recupera o pacote do Harness; suas outras
skills, configurações e MCPs precisam da entrega de recuperação (SPEC §11, HE-REC-02).

O procedimento a entregar é: instalar os aplicativos → clonar o repositório privado de ambiente pessoal → rodar
`restore.ps1` → entrar novamente nas contas → conferir skills e MCPs. O script ainda não está entregue.

Antes de formatar, é preciso conferir a cópia no GitHub privado, provar a restauração em um perfil limpo e preservar
trabalhos locais sem cópia externa. Senhas e tokens ficam em armazenamento seguro separado. O inventário inicial
em `docs/evidence/HE_REC_01_WORKSTATION_INVENTORY.json` registra caminhos e nomes; ele não salva os conteúdos.

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
python C:\Users\itiro\.harness-engineering\current\scripts\harnessctl.py project-plan --repo C:\dev\meu-projeto
```

```bash
python C:\Users\itiro\.harness-engineering\current\scripts\harnessctl.py project-attach --repo C:\dev\meu-projeto --apply
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

### 4.1. Relatório do dia

No fim do dia, em qualquer pasta:

```powershell
python C:\Users\itiro\.harness-engineering\current\scripts\harnessctl.py machine-verify
python C:\Users\itiro\.harness-engineering\current\scripts\daily_report.py
```

O primeiro confere se as skills do computador continuam intactas. O segundo lê as sessões do dia do Claude Code e
do Codex no seu computador e mostra, por sessão: o repositório, se ele tem o Harness, quais skills o agente usou, se
rodou testes (se algum falhou e depois passou, e se o último passou) e os tokens. Para outro dia, use
`--date 2026-11-07`; para JSON, use `--json`. Nada sai do computador, e nenhum texto das conversas entra no relatório.

**O que ele não diz:** se o trabalho ficou melhor. Isso só o benchmark responde (seção 6). Use o relatório para
achar problemas de funcionamento, como uma skill que nunca é usada ou uma sessão que termina com teste falhando.

---

## 5. Conferir, atualizar e remover

| Quero… | O que digito no repositório | O que acontece |
|---|---|---|
| **Conferir** se está tudo certo | `/setup-harness verificar` | compara os arquivos com o recibo e diz OK ou o que mudou |
| **Atualizar** depois de uma versão nova do Harness | §2, "Atualizar para uma versão nova"; depois, em cada repositório: `/setup-harness verificar` | o computador recebe as skills novas; o repositório só muda se a versão nova pedir, e sempre com o seu "sim" |
| **Remover** do projeto | `/setup-harness remover` | mostra o que vai apagar (só o que ele criou) e pede confirmação |
| **Remover do computador** | `python C:\Users\itiro\.harness-engineering\current\scripts\harnessctl.py machine-remove` (prévia) e depois o mesmo comando com `--apply` | apaga só as skills que o Harness instalou; se você editou alguma, ele para e não apaga nada |

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
