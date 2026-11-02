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
| Skill copiada mas não carregada | Alta | Trajetória runtime, níveis 1–5 |
| Instalação intercepta arquivos pessoais | Alta | Sandbox, colisões fail-closed, record e remoção exata |
| Helper upstream não preparado | Alta | Testar cadeia Node+scripts antes de invocar TDD |
| Instruções POSIX em Windows | Média | Rodar em shell suportado ou adaptar somente após medir |
| Agente altera testes ou oráculos | Alta | Oráculos fora do workspace mutável |
| Publicação/commits indesejados | Alta | Isolar Git/segredos/credenciais e exigir aprovação |
| Benchmark autojustificatório | Alta | Oráculo externo, amostra pré-registrada, auditoria numérica |
| Custo e tokens excessivos | Média | Guardar orçamento e todas as tentativas |
| Dependência de releases não pinadas | Média | Manter SHA/manifesto, revisar licenças e updates |
| Falta de backup ou rollback | Alta | Remoção exata e simulação antes de adoção |

## Fases e critérios

- F0: documentação e código offline nesta branch → testes CI.
- F1: Codex verifica código e riscos; valida perfis A1 em sandbox isolado.
- F2: prova de descoberta/invocação/execução de Codex e Claude Code; sem mudanças em configurações globais.
- F3: comparação com tarefas reais, evidenciação e decisão de adoção.
- F4: integração opt-in nas ferramentas/projetos conforme gates individuais.

Conclusão da F0 não libera F1–F4, nem autoriza merge ou execução externa.
