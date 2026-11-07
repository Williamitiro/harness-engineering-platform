# Protocolo de validação A0 → A1 → B → C

## Situação herdada
**A0:** 25 verificações de ciclo de arquivos offline, PR #1, sem runtime. **HE-AG-001:** nove rodadas Antigravity; nenhuma invocou ou executou skill. Resultado histórico não é prova de ganho ECC. **A1/B/C:** não executados. Alvo operacional V1: Codex e Claude Code.

## Gates
| Gate | Objetivo | Prova |
| --- | --- | --- |
| G0 | Identidade e reuso | fonte, licença, SHA, hashes, dependências e inventário |
| G1 | Contenção | fronteiras reais de arquivos, segredos, rede, Git, configurações e canários negativos |
| G2 | Ativação | descoberta, invocação e execução da skill demonstradas em trajetória |
| G3 | QA independente | tarefas reais, oráculos externos, negativos, logs, diffs, custos e latência |
| G4 | Adoção | ganho suficiente, conflitos, rollback, decisão humana |

Estados: PASS / FAIL / BLOCKED / NOT_RUN / NOT_APPLICABLE. Não converter teste omitido em PASS.

## Comparação
Dentro de cada runtime (não misturar Codex e Claude Code como condições):
- A: nativo sem personalização extra;
- B: instruções mínimas adequadas ao cliente;
- C: B + skills ECC permitidas;
- D opcional: ablação isolada ou GStack, sob protocolo próprio.

Pré-registrar tarefas, critérios e tentativas antes da observação. Misturar tarefas sintéticas e reais com oráculos que discriminem defeitos; repetir, randomizar ordem, registrar todos os fracassos e não invocações. Medir sucesso de QA, segurança, esforço humano, duração, tokens, custo, regressões e qualidade externa. Se a amostra for pequena ou todos passarem igualmente, concluir INCONCLUSIVE.

Oráculos não podem ser reescritos pelo agente avaliado. O agente não recebe segredos de publicação, acesso ao repositório original ou ao verificador. A infraestrutura deve aplicar isolamento; instrução de prompt não é proteção suficiente.

## Formato mínimo de evidência
```json
{
 "schema_version":1,
 "experiment_id":"a1-example",
 "client":"codex",
 "client_version":"NOT_RUN",
 "task_id":"NOT_RUN",
 "condition":"C",
 "isolation_verified":false,
 "skills":{"discovered":false,"invoked":false,"procedure_executed":false},
 "acceptance":{"status":"NOT_RUN","tests_passed":null,"tests_total":null},
 "metrics":{"duration_seconds":null,"input_tokens":null,"output_tokens":null,"cost_usd":null},
 "evidence":{"transcript":null,"oracle_log":null,"diff":null},
 "verdict":"NOT_RUN"
}
```

Guarde brutos em .poc ignorado e publique somente evidências sanitizadas. Copiar SKILL.md comprova bytes, não carregamento. Leitura da skill não comprova a execução. Um teste verde sem casos negativos não prova a qualidade do sistema.

## Critério de encerramento
A1 exige demonstração real do cliente e canários de segurança. B exige comparação pré-registrada com tarefas reais. C exige decisão revisada e custo/risco aceitáveis. CI offline nesta branch **não** autoriza marcar A1/B/C como concluído.
