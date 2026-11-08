# AGENTS.md — regras deste projeto

Instruções para qualquer agente de código (Codex, Claude Code via `CLAUDE.md`, Cursor, OpenCode…).
Este arquivo pertence ao projeto: edite à vontade.

## Como trabalhar
- Pergunta não é pedido de mudança: responda e pare. Só altere arquivos quando o pedido for explícito.
- Faça só o que foi pedido, do jeito mais simples. Não refatore o que está ao lado nem crie abstração, opção ou
  arquivo que ninguém pediu. Achou outro problema? Anote e pergunte.
- Antes de criar função, classe ou dependência, procure no projeto e nas bibliotecas já instaladas algo que já
  faça isso.
- Ao corrigir um bug que dá para reproduzir, escreva primeiro o teste que falha por causa dele.
- Antes de dizer que terminou, rode os testes e o build **deste** projeto (seção abaixo) e mostre o comando e o
  resultado. Não suponha npm, Node ou bash se o projeto não usa.

## Limites
- Nunca leia, imprima ou envie segredos, tokens ou credenciais.
- Trabalhe só dentro deste repositório.
- Nunca apague, enfraqueça ou altere testes e critérios de aceite para forçar aprovação.
- Sem push, merge, deploy, publicação ou comando destrutivo sem autorização explícita.

## Comandos do projeto
<!-- Preencha: como instalar dependências, rodar os testes e executar. Exemplo: python -m pytest -->
