# ADR, riscos e fases

## Decisões

**ADR-001: dois executores oficiais.** Apenas Codex/Claude Code são alvo de desenvolvimento; manter Antigravity como arquivo histórico. Motivo: decisão explícita do produto e redução de superfície técnica.

**ADR-002: não criar um harness próprio.** Aproveitar runtimes nativos; limitar repo a seleção, configuração, validação e registro de evidências. Reversível se os runtimes não expuserem integração necessária.

**ADR-003: ECC seletivo e pinado.** Piloto com duas skills e manifestos. O histórico A0 prova integridade de arquivos, não eficácia do comportamento.

**ADR-004: GStack não instalado por padrão.** Requer matriz de overlap e benchmark separado.

**ADR-005: Harbor não requerido em tarefas simples.** Usar suites nativas primeiro. Harbour/Harbor somente quando isolamento, repetição e benchmark justificarem dependência.

**ADR-006: CI offline.** Python stdlib e unit tests; sem LLM, credenciais, alterações externas ou claims de execução de skills.

**ADR-007: segurança e custos antes de A1.** Políticas de isolamento, canários, orçamento e acesso restrito são pré-condições, não tarefas posteriores.

## Riscos e mitigação

| Risco | Gravidade | Mitigação |
| --- | --- | --- |
| Skill copiada mas não carregada | Alta | Trajetória runtime, níveis 1–5 comprovados no relatório de homologação |
| Instalação intercepta arquivos pessoais | Alta | Sandbox, colisões fail-closed, record e remoção exata sem resíduos |
| Helper upstream não preparado | Alta | Operação verificada com ferramentas nativas padrão (pytest, mypy, ruff) |
| Instruções POSIX em Windows | Média | Subprocessos com encoding UTF-8 explícito e tratamento de charmap |
| Agente altera testes ou oráculos | Alta | Oráculos congelados fora do workspace mutável |
| Publicação/commits indesejados | Alta | Isolar Git/segredos/credenciais e exigir aprovação |
| Benchmark autojustificatório | Alta | Oráculo externo, amostra pré-registrada, auditoria numérica |
| Custo e tokens excessivos | Média | Guardar orçamento e todas as tentativas registradas em JSON |
| Dependência de releases não pinadas | Média | Manter SHA/manifesto, revisar licenças e updates |
| Falta de backup ou rollback | Alta | Remoção exata e simulação antes de adoção |

## Fases e critérios

- F0: documentação e código offline nesta branch → testes CI (CONCLUÍDO).
- F1: Codex verifica código e riscos; valida perfis A1 em sandbox isolado (CONCLUÍDO).
- F2: prova de descoberta/invocação/execução de Codex e Claude Code; sem mudanças em configurações globais (CONCLUÍDO para Codex: Níveis 1 a 5 comprovados; Claude Code diagnosticado e bloqueado fatualmente por ausência de login local).
- F3: comparação empírica de tarefas reais (Condição A baseline vs Condição C com skills), evidenciação e decisão de adoção (CONCLUÍDO para tarefa ratelimit; ver `docs/HOMOLOGACAO_A1_CODEX_CLAUDE.md`).
- F4: integração opt-in nas ferramentas/projetos conforme gates individuais.

Conclusão da F0-F3 documentada no PR #2; não autoriza merge automático nem alterações em produção.
