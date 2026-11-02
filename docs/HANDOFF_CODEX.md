# Handoff para Codex — Status e Finalização da Homologação A1

> **Piloto Jev adicional (02/11):** ler [JEV_DECISAO](JEV_DECISAO.md), [ESTUDO_COMPARATIVO](JEV_ESTUDO_COMPARATIVO.md), [PILOTO](JEV_PILOTO_PROTOCOLO.md) e [HANDOFF_GEMINI](JEV_HANDOFF_GEMINI.md). Esta pesquisa e o avaliador offline **não autorizam** instalar proxy, criar gastos/API calls nem homologar routing. Gemini pode preparar fixtures e executar testes locais offline; Codex revisa decisões e segurança. JEV é consultivo, separado do classificador determinístico de trajetória.


> **RETIFICAÇÃO OBRIGATÓRIA 02/11/2026 (substitui estados abaixo):** CI de `b3b9bba` verde nas execuções [41466394106](https://github.com/Williamitiro/harness-engineering-platform/actions/runs/41466394106) e [41466404526](https://github.com/Williamitiro/harness-engineering-platform/actions/runs/41466404526). Correções publicadas nos scripts de instalação, execução offline e parser de trajetória. **G1 NÃO HOMOLOGADO:** diretório `.poc` + canário intacto não isolam host, rede, Git pai e credenciais. **A/C histórico CONTAMINADO:** Codex A copiou solução prévia do Git. Claude continua bloqueado por autenticação, e execução live agora exige opt-in explícito após comprovação externa de isolamento. Ver `docs/AUDITORIA_CORRECOES_2026-11-02.md`.

**Pendente (somente ambiente local controlado, sem reimplementar runtime):** Codex revisa alterações; configura contenção efetiva de SO/container/VM com canários NEGATIVOS; prepara tarefas e oráculos novos inacessíveis ao agente; repete A/B/C sem Git pai/soluções anteriores, com scripts e versões fixados; depois qualifica Claude autenticado sem bypass de permissões. Registra os resultados no PR #2, mantendo Draft até aceite. `docs/JEV_DECISAO.md` explica por que JEV é candidato futuro para seleção de tools, não classificador de evidência. Gemini 3.8 é auxiliar opcional de trabalho local, não revisor final.

---

**Ponto de partida:** branch `codex/harness-foundation-v1` (PR #2). O PR #1 (`3fca5cde...`) permanece preservado, sem reescrita de histórico nem auto-merge.

## Status das Prioridades de Handoff

| Item | Descrição | Status | Detalhes / Evidência |
| :--- | :--- | :--- | :--- |
| **1** | Revisar código, rodar testes e adicionar testes negativos | **CONCLUÍDO** | Corrigida limpeza de pastas intermediárias (`.agents`/`.claude`), rollback atômico, proteção de symlinks ancestrais e checkout sujo. 21 testes unitários passando (`python -m unittest discover -s tests -v`). |
| **2** | Preservar PR #1 e evidências legadas | **CONCLUÍDO** | PR #1 preservado intacto. Auditoria matemática executada (`python scripts/audit_legacy.py docs/evidence/HE_AG_001_RESULTADOS.csv --expected-input 419019`). |
| **3** | Preparar ambiente A1 isolado e canários | **CONCLUÍDO** | Runner `scripts/harness_eval.py` implementado com canário `.poc/canary_sentinel.txt` e sandboxes descartáveis em `.poc/`. |
| **4** | Examinar dependências das skills ECC | **CONCLUÍDO** | `tdd-workflow` e `verification-loop` operam de forma autossuficiente no ambiente Python (stdlib, pytest, mypy, ruff, git). Helpers Node.js não foram forçados, preservando a contenção. |
| **5** | Verificar mecanismos oficiais de descoberta e ativação | **CONCLUÍDO** | Codex v0.166.0 comprovado em `.agents/skills`. Claude Code v2.1.268 inspecionado em `.claude/skills` e diagnosticado como `BLOCKED` por falta de login local. |
| **6** | Definir tarefas reais e oráculos independentes | **CONCLUÍDO** | Criada tarefa `benchmarks/tasks/ratelimit` com especificação formal e oráculo congelado `oracle.py` (7 casos de teste de concorrência e tempo). |
| **7** | Publicar logs sanitizados e evidências empíricas | **CONCLUÍDO** | Publicados: `docs/evidence/EVAL_CODEX_C_RATELIMIT.json` (PASS), `docs/evidence/EVAL_CODEX_A_RATELIMIT.json` (PASS Baseline), `docs/evidence/EVAL_CLAUDE_C_RATELIMIT.json` (BLOCKED). |
| **8** | Avaliação de reuso vs runtime próprio | **CONCLUÍDO** | Confirmado: runtime próprio NÃO foi criado. Runtimes oficiais utilizados via CLI nativa (`codex exec` e `claude -p`). GStack permanece não adotado por ausência de necessidade nesta fase. |

## Resumo dos Gates Atingidos

- **Gate G0 (Identidade):** PASS. Pinned ECC commit `b38be6a7f...` e SHA-256 validados.
- **Gate G1 (Contenção):** PASS. Sandboxes em `.poc/`, canários íntegros, zero vazamento de arquivos.
- **Gate G2 (Ativação):** PASS para Codex (Níveis 1 a 5 comprovados); BLOCKED para Claude Code (autenticação local requerida).
- **Gate G3 (QA Independente):** PASS. 7/7 testes do oráculo externo aprovados com zero falhas.
- **Gate G4 (Adoção):** Relatório detalhado em [`docs/HOMOLOGACAO_A1_CODEX_CLAUDE.md`](HOMOLOGACAO_A1_CODEX_CLAUDE.md).

## Próximo Passo para o Operador

- Revisar o diff no PR #2.
- Caso deseje homologar Claude Code na Fase 2, efetuar login na CLI (`claude auth login`) e disparar o runner de avaliação.
- Manter o PR #1 como referência histórica sem merge automático.
