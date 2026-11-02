# Handoff para Codex — finalizar após revisão do PR

**Ponto de partida:** branch `codex/harness-foundation-v1`, derivada do PR #1 (`3fca5cde...`). Não editar PR #1, não rebater histórico nem modificar `main` sem revisão. Ler `README.md`, `docs/MANUAL_HARNESS_V1.md`, `docs/RUNBOOK_CODEX_CLAUDE.md`, `docs/PROTOCOLO_VALIDACAO.md`.

## O que já foi codificado

- `scripts/harnessctl.py`: lifecycle de arquivos de duas skills pinadas, em sandboxes descartáveis, sem rede, sem atualização global.
- `config/approved_skills.json`: pin ECC e SHA-256 dos SKILL.md.
- `scripts/audit_legacy.py`: auditor descritivo de CSV histórico, não verificador de runtime.
- `tests/`: testes de lifecycle e auditor.
- `.github/workflows/quality.yml`: testes offline.

## Trabalhos do Codex por prioridade

1. Revisar código e executar `python -m unittest discover -s tests -v` e auditor legado; corrigir erros demonstrados; adicionar testes negativos (symlinks de ancestrais, interrupção parcial, alterações do checkout e paths tampered).
2. Confirmar `README.md`/PR #1/snapshots locais, não sobrescrever evidências de experimento. Conciliar fonte e branch com o worktree real.
3. Preparar ambiente A1 realmente isolado, usando recurso de sandbox existente (Docker/VM/Harbor quando aprovado). Comprovar separação de tokens, repositórios, remotes, configurações, hooks, Git e rede; canários.
4. Examinar as dependências reais do `tdd-workflow` e do `verification-loop` no ECC pinado, incluindo `setup-package-manager.js` e imports; fornecer apenas suporte indispensável com integridade verificada, ou bloquear explicando falta.
5. Verificar versões locais do Codex e Claude Code, mecanismos **oficiais** de descoberta, escopo e invocação de skill. Não confundir `SKILL.md` em disco com ativação real.
6. Definir conjunto de tarefas de código reais, oráculos independentes e protocolo pré-registrado; testar primeiro somente se gates A1 passarem e usuário aprovar o uso de modelos/créditos.
7. Publicar logs sanitizados e evidências com classificação `PASS/FAIL/BLOCKED/NOT_RUN` e revisão separada. Não inventar métricas; não escolher vencedor por relatório.
8. Decidir se ECC/GStack agregam algo, com matriz de overlap; não criar runtime de agente.

## Limitações explicitamente abertas

- Os scripts de lifecycle não instalam helpers nem validam a semântica dos runtimes; isso é F1/F2.
- Nenhuma execução Codex/Claude ou instalação Harbor foi realizada por este commit.
- Alguns pontos de segurança são proteção de arquivo, não isolamento de processo/rede.
- Os resultados HE-AG-001 devem continuar **históricos e inconclusivos quanto a ECC**.

## Conclusão operacional

Devolver no PR: problemas corrigidos, testes e comandos com exit code, versions, artefatos, limites e decisão de gate. Produção e configurações globais continuam proibidas até autorização.
