# HE-OP-02B — ativação pessoal, descoberta nativa e contrato existente

Continuação autorizada pelo usuário após as correções do review (`e77ba76`). O usuário escolheu `C:/dev/plataforma-metalurgica` para HE-OP-03 e delegou a escolha do tratamento ideal do contrato existente. Nenhum modelo pago, benchmark ou merge foi autorizado/executado.

## Ativação e descoberta observadas

O plano pessoal retornou quatro arquivos novos, sem colisões. A instalação foi aplicada por `setup-skill-install --client codex --apply` e conferida por `setup-skill-verify --client codex`. Diretório: `C:/Users/itiro/.agents/skills/setup-harness`; o restante da home permaneceu fora da operação. A skill instalada e seu descritor foram lidos nesta sessão; o CLI central foi usado para inspecionar o projeto escolhido.

Codex CLI nativo **0.166.0** executou apenas `initialize` e `skills/list` com `forceReload=true`, sobre Git fixture vazia em `.poc/he-op-02b-native-discovery`. O transporte finito existente `NativeBroker` foi reutilizado por stdio, sem serviço/listener persistente. A lista retornou `setup-harness`, path pessoal correto, `scope=user`, `enabled=true`, zero erros de leitura. Nenhum `thread/start` ou `turn/start`: **zero turnos de modelo**. Fonte do contrato: [OpenAI Docs, App Server](https://learn.chatgpt.com/docs/app-server).

Recibo sanitizado: [HE_OP_02B_ATIVACAO_DESCOBERTA.json](evidence/HE_OP_02B_ATIVACAO_DESCOBERTA.json). Ele preserva também o bloqueio inicial do projeto, antes desta extensão. **Descoberta nativa: OBSERVADA. Invocação por novo turno nativo: NOT_RUN.** Ler/aplicar a skill nesta sessão não é contado como um turno novo executado pelo supervisor. O gate completo não é promovido a PASS por presença/listagem de arquivo.

## Decisão: preservar o contrato específico do projeto

O projeto escolhido está em `main`, SHA `31e4c261678c418ca76004560c0c6019c39cf6c0`, limpo na inspeção inicial, com `AGENTS.md` próprio. O plano padrão retornou `BLOCKED_COLLISION` e não escreveu nada. Esse contrato tem regras de CAD/fabricação, isolamento de cópias e governança próprias; substituir ou concatenar instruções centrais não é a opção adequada.

A solução selecionada é **opt-in explícito `--preserve-contract`** para doctor/plan/attach. Requer `AGENTS.md` regular existente, preserva-o sem ler conteúdo nem reivindicar ownership e instala apenas duas skills mais `.harness/manifest.json`. O padrão continua bloqueando colisão. Skills de terceiros, links e demais colisões continuam bloqueadas; o flag não as ignora.

O manifesto registra `contract_policy=preserve-existing` e somente os dois arquivos gerenciados. Verify/remove derivam a lista exata dessa política; trocar a política no manifesto sem corresponder ao pacote bloqueia. O contrato preservado pode ser editado pelo projeto e nunca é removido/restaurado pelo Harness. Registros antigos sem política continuam usando `create-new`.

```powershell
python scripts/harnessctl.py project-plan --repo C:/caminho/projeto --client codex --preserve-contract
python scripts/harnessctl.py project-attach --repo C:/caminho/projeto --client codex --source C:/caminho/ecc-pinado --preserve-contract --apply
python scripts/harnessctl.py project-verify --repo C:/caminho/projeto
python scripts/harnessctl.py project-remove --repo C:/caminho/projeto --apply
```

O exemplo de plan foi executado sobre a plataforma e retornou três caminhos novos, nenhum bloqueio e `contract_source=null`. Attach e trabalho de produto devem respeitar a cópia isolada exigida pelo AGENTS do projeto; **não se escreve nem se comita na main do proprietário**. A frente já ativa `b-forja-documento-unico` / PR #215 permanece intocada. O usuário atual autoriza a validação Codex neste projeto; isso não altera a política permanente D51 nem distribui novas tarefas fora deste ensaio.

## Testes desta extensão

- RED: 18 testes do lifecycle, quatro erros por ausência do argumento/modo.
- Dirigidos: 18 testes de `test_project_lifecycle.py`, OK, 14,868 s.
- Suíte offline com `JEV_REAL_INTEGRATION=0`: 158 testes, OK, 2 skips opt-in (156 passaram), 23,651 s; log `.poc/he-preserve-contract-offline.log`.
- Compilação de CLI/testes e `git diff --check` aprovados.
- Positivos/negativos novos: instalar/verificar/reaplicar/remover apenas skills; contrato preservado byte a byte; edição posterior do contrato permanece; recusa de AGENTS ausente e skill de terceiro; adulterar política não permite tomar ownership do contrato.

## Continuidade e limites

HE-OP-03 usa uma pequena correção de entrada na linha de comando (CLI): recusar NaN/infinito antes de chamar o planejador de encaixe. A inspeção inicial demonstrou `nanx100` e `100xinf` chegando ao planejador, com retorno 0 quando ele é substituído por stub. O motor geométrico não precisa ser alterado; a correção é validação de parâmetros, com testes negativos e controle positivo de números finitos.

Esta entrega documenta ativação/descoberta e o modo compatível. Instalação e QA do projeto real terão recibo próprio, sem afirmar antecipadamente que o patch foi concluído. R1 diário e R2 continuam pendentes até as evidências correspondentes. Rollback pessoal: `setup-skill-remove --client codex --apply` após verify; rollback do pacote de projeto: `project-remove --apply`, sem tocar no contrato preservado. Não há migração automática de versões ou garantia contra escritor hostil concorrente.
