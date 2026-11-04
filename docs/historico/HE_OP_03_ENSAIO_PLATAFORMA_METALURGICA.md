# HE-OP-03 — ensaio real na plataforma metalúrgica

Registro final em 03/11/2026 (America/Sao_Paulo), continuação do trabalho iniciado em 02/11. Projeto escolhido pelo usuário: `C:/dev/plataforma-metalurgica`; tarefa e modo de compatibilidade delegados ao Codex. Entrega: [PR #216 da plataforma](https://github.com/Williamitiro/plataforma-metalurgica/pull/216), **Draft**, SHA `845e0513ca1e5a96738845a0acedcddb8cd6bcf5`. Sem merge, deploy ou publicação do produto. O Harness continua na branch e PR #4 existentes.

## Preparação e preservação

1. O bootstrap pessoal Codex foi instalado por plano explícito, criação exclusiva e verificação de hashes. O Codex CLI 0.166.0 descobriu `setup-harness` em escopo de usuário, habilitada, em uma Git fixture vazia. Apenas `initialize` e `skills/list` foram enviados ao supervisor; zero novos turnos de modelo.
2. O projeto real tinha `AGENTS.md`; o plano padrão bloqueou e não escreveu nada. O modo `--preserve-contract` foi implementado/testado e aprovado como escolha reversível pelo usuário ao delegar a decisão. Ele gerencia somente as duas skills e o manifesto.
3. As instruções locais exigem cópia isolada e proíbem commit em main. Foi criada `b19-he-op-03-cli-finitos` em `C:/Users/itiro/.codex/worktrees/harness-he-op-03/plataforma-metalurgica`, a partir de `31e4c261678c418ca76004560c0c6019c39cf6c0`. A frente existente `b-forja-documento-unico` / PR #215 permaneceu intocada. O gerenciador da aplicação não aceita esse sourceRoot no chat do Harness; o Git local criou a cópia isolada exigida, sem alterar a origem dos dados.
4. O pacote foi instalado e verificado na cópia. O Codex nativo listou as duas skills com `scope=repo` e o bootstrap com `scope=user`, todos habilitados. Os três corpos foram lidos/aplicados nesta sessão. A orientação do bootstrap passou a recomendar o modo compatível; sua instalação pessoal foi atualizada por verify → backup dos arquivos próprios → remove → install → verify, sem tocar outros perfis. Não há atualizador silencioso.
5. Depois dos testes, `project-remove --apply` removeu exatamente o pacote temporário. O hash de AGENTS.md permaneceu `215c05c39b74c85240d28340dc9d0632a08cc04d033f6c2d02e230990a9c8287`. O checkout principal continua limpo no SHA inicial. A skill pessoal permanece instalada.

## Trabalho real e verificação

O comando de encaixe da linha de comando aceitava NaN (valor que não representa um número) e infinito positivo porque apenas comparava sinais. A correção acrescenta três linhas de produção: `math.isfinite` e recusa de largura, altura, folga ou margem não finitas antes do motor/pasta de saída. Não altera motores geométricos, fabricação ou dados privados.

- Critério registrado antes da edição em `.poc/he-op-03-installed.json`: 12 entradas inválidas, código 2, sem planejador/saída; preservar controle positivo finito.
- RED: 8 falhas e 4 casos já recusados; commit `8e70ed8` só de testes. GREEN: commit `de4dc09`; 92 testes da área aprovados e 4 privados pulados em 5,37 s.
- Verificador externo por subprocessos, fora da cópia do agente: 12/12 recusas corretas; controle finito gerou os dois desenhos sintéticos esperados e passou pelo validador do produto.
- Cobertura de `_nesting` com biblioteca padrão: 26/28 linhas executáveis, **92,86%**; 47 testes aprovados em 34,36 s. Não é cobertura global do projeto.
- Compilação, diff check e índice documental staged aprovados. Documentos canônicos e índices atualizados no próprio PR do projeto. Não foi instalada ferramenta de cobertura, Node ou dependência adicional.

## Resultado global e limites

A suíte completa da plataforma foi executada: **1.964 passed, 551 skipped, 2 failed e 22 subtests passed**, 816,63 s. Não é resultado verde. Uma falha veio da pasta temporária do executor dentro do Git do Harness; a guarda de relatório privado corretamente recusou a escrita. O mesmo caso passou fora de Git (1 passed, 0,73 s). A outra falha encontrou **36 evidências históricas com CRLF**, todos os blobs idênticos aos da main inicial. Não se regravou histórico nem alterou exceções/asserts para forçar aprovação. Revisão independente permanece pendente; a plataforma não tem CI configurada para esse PR.

[Recibo sanitizado completo](evidence/HE_OP_03_PLATAFORMA_METALURGICA.json) e [evidências do projeto](https://github.com/Williamitiro/plataforma-metalurgica/tree/b19-he-op-03-cli-finitos/evidence/2026-11-02_he_op_03_cli_finitos). Os logs brutos ficam em `.poc/he-op-03-*.log`/`.json`, ignorados. A evidência distingue descoberta por metadados nativos, leitura e comportamento nesta sessão e novo turno independente de modelo (**NOT_RUN**). Não confundir um com outro. Os passos RED/GREEN, cobertura, verificação externa, falhas e rollback comprovam o procedimento observado; não provam ganho causal, paridade entre clientes ou isolamento do sistema operacional.

Não foram executados modelos pagos ou benchmark A/B. Tokens e custo da sessão não foram observados e permanecem `null`; zero novos turnos não é estimativa de custo total zero. Nenhuma credencial foi copiada; variáveis de credenciais/fixtures privadas foram retiradas do ambiente da suíte. Sem alegar homologação do Gate G1 por esse fato.

## Continuidade

HE-OP-02B: ativação e descoberta observadas, com comportamento nesta sessão; validação independente de invocação nativa continua limitada. HE-OP-03: patch real com aceite específico aprovado, suíte global/revisão ainda pendentes. R1 não é declarado universalmente pronto e R2 permanece **NOT_RUN**. Próximo passo seguro é revisão independente e tratar a pendência histórica de finais de linha por escopo próprio, antes de integração. Não avançar automaticamente para modelos pagos, benchmark, Claude, merge ou deploy.
