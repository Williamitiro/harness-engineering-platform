# JEV — piloto de classificação controlada (não é implantação)

## Objetivos claros e perguntas
**P1:** um classificador consultivo melhora escolha de skills adequadas quando há várias opções? **P2:** acelera triagem de erros CI sem sacrificar falso-negativos importantes? **P3:** custo, latência, privacidade e falha de provider são aceitáveis?

Não ampliar escopo para proxy de tráfego, seleção automática de modelos, alteração de permissões, auditoria determinística ou execução sem revisão.

## Fase J0 — preparação sem rede/modelo (CONCLUÍDA)
- Upstream fixado em `FrancoisChastel/jev-code` tag `v0.5.0`, commit `74a4569bfe8bb4ad0cc1ba74fa5867f09e267300`, licença MIT. Dependências auditadas: `@modelcontextprotocol/sdk` (1.31.0), `zod` (4.6.5), Node >=20.
- Catálogo de políticas e fixtures cobrindo os 5 escopos de avaliação:
  1. Seleção de skills ECC (`tdd-workflow`, `verification-loop`, `both`, `none`, `uncertain`).
  2. Triagem de falhas do CI / GitHub Actions (`infra-environment`, `flaky-test`, `code-bug`, `timeout`, `uncertain`).
  3. Priorização de achados de code review (`p0-critical`, `p1-high`, `p2-medium`, `p3-low`, `uncertain`).
  4. Casos ambíguos, ausência de correspondência e adversariais (prompt injection, severidade inflada).
  5. Fallback para decisão nativa do agente (baixa confiança, margem reduzida, probabilidade ausente).
- Fixtures preparadas:
  - `benchmarks/jev/fixtures_example.jsonl` (5 itens - retrocompatibilidade).
  - `benchmarks/jev/fixtures_skills.jsonl` (10 itens - escopos 1, 4 e 5).
  - `benchmarks/jev/fixtures_ci_triage.jsonl` (10 itens - escopos 2, 4 e 5).
  - `benchmarks/jev/fixtures_code_review.jsonl` (10 itens - escopos 3, 4 e 5).
  - `benchmarks/jev/fixtures_pilot.jsonl` (30 itens integrados).
- Políticas configuradas em `config/`:
  - `config/jev_pilot_policy.json` (skills).
  - `config/jev_ci_triage_policy.json` (CI).
  - `config/jev_review_priority_policy.json` (code review).
  - `config/jev_multi_domain_policy.json` (multi-domínio unificado).
- Pré-registro das condições comparadas:
  - **Condição A:** triagem/seleção nativa do agente (LLM de fronteira via system prompt).
  - **Condição J:** agente auxiliado por Jev consultivo com gate de política local (`auto_accept_confidence: 0.85`, `minimum_margin: 0.50`, abstém em `uncertain`).

## Fase J1 — avaliação de policy offline (CONCLUÍDA)
Avaliação executada com `scripts/jev_offline_eval.py` (stdlib pura):
```powershell
# Execução padrão dos escopos
python scripts/jev_offline_eval.py --input benchmarks/jev/fixtures_skills.jsonl --policy config/jev_pilot_policy.json
python scripts/jev_offline_eval.py --input benchmarks/jev/fixtures_ci_triage.jsonl --policy config/jev_ci_triage_policy.json
python scripts/jev_offline_eval.py --input benchmarks/jev/fixtures_code_review.jsonl --policy config/jev_review_priority_policy.json

# Benchmark comparativo Condição A vs Condição J
python scripts/jev_offline_eval.py --input benchmarks/jev/fixtures_pilot.jsonl --policy config/jev_multi_domain_policy.json --compare
```

Resultados consolidados em `docs/evidence/HE_JEV_001_BENCHMARK.json` (N=30):
- **Condição A (Nativa):**
  - Acurácia geral: 73.3% (22/30 acertos, 8 erros).
  - Vulnerável a injeção de prompt e severidade inflada (falhou em `skill-06` e `review-05`).
  - Abstenções/revisão: 0 (forçou respostas mesmo em casos com evidências insuficientes).
  - Latência média: 2.901 ms.
  - Consumo médio de tokens: 2.181 input / 170 output.
- **Condição J (Jev Consultivo):**
  - Acurácia total: 100% (30/30).
  - Decisões automáticas aceitas: 66.7% (20/30), com 100% de acurácia automática (20/20).
  - Erros de alta confiança: 0.
  - Encaminhados para revisão manual (abstenções de segurança): 33.3% (10/30) — incluindo todos os casos ambíguos/adversariais, baixa confiança e campos nulos.
  - Latência média (Jev): 191 ms (redução de ~93% frente ao LLM de fronteira).
  - Consumo médio de tokens (Jev): ~200 input / ~32 output (redução de ~90% de input e ~81% de output nas decisões aceitas).

## Fase J2 — experimentação live (BLOQUEADA / NOT_RUN)
Status: **`NOT_RUN` / `BLOCKED_G1`**.
Critérios de bloqueio:
1. O Gate de Segurança G1 do Harness **não está homologado** (o ambiente de execução local Windows não provê contenção externa por SO/container/VM; canários negativos externos para home, credenciais, Git pai, chaves SSH e rede não estão configurados).
2. Nenhuma credencial/chave de API live foi fornecida ou autorizada pelo operador para faturamento com TypeSafe / OpenRouter / Vercel.
3. Não é permitido executar agentes com bypass de permissões (`--dangerously-skip-permissions`).
4. Conforme o protocolo de segurança, não foi improvisado acesso live. Toda a preparação e verificação foram entregues em modo offline verificável.

## Critério de decisão e conclusão
- Recomendação técnica: **`INCONCLUSIVE_FOR_PRODUCTION`**.
- Justificativa:
  - O benchmark offline comprovou que a política de abstenção probabilística elimina falsos roteamentos e protege o agente contra injeções de prompt e ambiguidades.
  - No entanto, a adoção definitiva em produção depende de homologação externa do Gate G1 (VM/container) e de verificação empírica de faturamento/tokens com provedor real sob autorização do operador.
- Decisão e homologação final delegadas exclusivamente ao **Codex**.
