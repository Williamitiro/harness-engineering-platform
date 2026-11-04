# AGENTS.md — regras deste projeto

Instruções para qualquer agente de código (Codex, Claude Code via `CLAUDE.md`, Cursor, OpenCode…).
Este arquivo pertence ao projeto: edite à vontade.

## Como trabalhar
- Ao criar funcionalidade, corrigir bug ou refatorar, use a skill `tdd-workflow`: primeiro um teste que falha,
  depois o código mínimo que o faz passar, depois a limpeza.
- Antes de dizer que terminou, use a skill `verification-loop`: build, testes, lint e revisão do diff.
- Use sempre os comandos de teste e build **deste** projeto (seção abaixo). Não suponha npm, Node ou bash se o
  projeto não usa.

## Limites
- Nunca leia, imprima ou envie segredos, tokens ou credenciais.
- Trabalhe só dentro deste repositório.
- Nunca apague, enfraqueça ou altere testes e critérios de aceite para forçar aprovação.
- Sem push, merge, deploy, publicação ou comando destrutivo sem autorização explícita.

## Comandos do projeto
<!-- Preencha: como instalar dependências, rodar os testes e executar. Exemplo: python -m pytest -->
