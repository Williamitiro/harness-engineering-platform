# Pré-Registro do Experimento Empírico — Validação Jev vs. Nativo

> **AUDITORIA DE SEGURANÇA 02/11/2026:** A versão HE-JEV-002 continha um bug crítico de proveniência: `jev_evaluator.py` tratava qualquer JSONL com `evidence_kind: VERIFIED` (campo controlado pelo autor do JSONL) e hashes presentes no mesmo registro como prova de execução real. Isso não autentica provedor, ambiente nem sessão. Foi corrigido: o avaliador **aceita apenas evidência SYNTHETIC** até existir adaptador live com atestação/verificação externa. Os comandos de coleta live listados abaixo permanecem **não implementados e bloqueados**, mesmo com flags declarativas. O gabarito no mesmo repositório Git **não é blindado operacionalmente**; é necessário montar somente tarefas no workspace do executor e manter gabaritos em volume/ambiente separado, inacessível. Ver `docs/AUDITORIA_HE_JEV_002_2026-11-02.md`.


**Identificação do Estudo:** HE-JEV-EMP-001  
**Data do Pré-Registro:** 2026-11-02  
**Repositório:** `Williamitiro/harness-engineering-platform`  
**Branch:** `codex/harness-foundation-v1`  
**Status do Pré-Registro:** `CONGELADO_PRE_EXECUCAO`

---

## 1. Motivação e Hipóteses

O experimento preliminar anterior foi invalidado pela auditoria independente ([`docs/AUDITORIA_HE_JEV_001_2026-11-02.md`](AUDITORIA_HE_JEV_001_2026-11-02.md)) porque utilizou fixtures sintéticas nas quais gabaritos, previsões dos modelos e métricas de latência/tokens estavam pré-preenchidos no mesmo arquivo pelo autor.

Este pré-registro estabelece as regras, hipóteses, conjunto de tarefas e critérios de avaliação **antes** de qualquer execução empírica com modelos.

### Hipóteses Testáveis
- **H1 (Qualidade e Abstenção Segura):** Em tarefas ambíguas e instruções adversariais (ex.: injeção de prompt para forçar tool call), o classificador consultivo Jev com política de abstenção probabilística (`auto_accept_confidence >= 0.85`, `minimum_margin >= 0.50`, abstenção compulsória em `uncertain`) reduz a taxa de falsos encaminhamentos de alta confiança em relação à classificação nativa do LLM sem guardrail calibrado.
- **H2 (Latência Observada):** Para itens de alta confiança aceitos automaticamente, o modelo de decisões tipadas Jev (System One) apresenta latência de resposta menor que a chamada do LLM conversacional nativo.
- **H3 (Consumo de Tokens):** A triagem consultiva com payload delimitado consome menos tokens de entrada e saída por decisão do que o processamento completo de contexto conversacional no LLM nativo.

---

## 2. Separação Estrita de Dados

Para garantir integridade experimental e evitar contaminação:

1. **Tarefas de Avaliação (Entradas Cegas):**
   - Diretório: `benchmarks/jev/tasks/`
   - Arquivos: `tasks_skills.jsonl`, `tasks_ci_triage.jsonl`, `tasks_code_review.jsonl`, `tasks_all.jsonl`.
   - Conteúdo de cada registro: `task_id`, `domain`, `task_type`, `input_text`, `candidate_labels`.
   - **Garantia:** Nenhum rótulo esperado, previsão ou resultado numérico está presente nesses arquivos.
2. **Gabarito Independente (Holdout Ground Truth):**
   - Diretório: `benchmarks/jev/ground_truth/`
   - Arquivos: `golden_skills.jsonl`, `golden_ci_triage.jsonl`, `golden_code_review.jsonl`, `golden_all.jsonl`.
   - Conteúdo de cada registro: `task_id`, `domain`, `expected_label`, `allow_abstain`, `rationale`.
   - **Garantia:** Esse diretório nunca é exposto aos agentes ou modelos durante a coleta de respostas.

---

## 3. Domínios e Políticas

As avaliações serão processadas e reportadas **separadamente por domínio**, sem misturar matrizes de confusão:

### Domínio 1: Seleção de Skills ECC (`skills`)
- **Arquivo de Tarefas:** `benchmarks/jev/tasks/tasks_skills.jsonl` (N=10)
- **Gabarito:** `benchmarks/jev/ground_truth/golden_skills.jsonl`
- **Classes Permitidas:** `["tdd-workflow", "verification-loop", "both", "none", "uncertain"]`
- **Política:** `config/jev_pilot_policy.json` (`auto_accept_confidence: 0.85`, `minimum_margin: 0.50`)

### Domínio 2: Triagem de Falhas de CI (`ci_triage`)
- **Arquivo de Tarefas:** `benchmarks/jev/tasks/tasks_ci_triage.jsonl` (N=10)
- **Gabarito:** `benchmarks/jev/ground_truth/golden_ci_triage.jsonl`
- **Classes Permitidas:** `["infra-environment", "flaky-test", "code-bug", "timeout", "uncertain"]`
- **Política:** `config/jev_ci_triage_policy.json` (`auto_accept_confidence: 0.85`, `minimum_margin: 0.50`)

### Domínio 3: Priorização de Code Review (`code_review`)
- **Arquivo de Tarefas:** `benchmarks/jev/tasks/tasks_code_review.jsonl` (N=10)
- **Gabarito:** `benchmarks/jev/ground_truth/golden_code_review.jsonl`
- **Classes Permitidas:** `["p0-critical", "p1-high", "p2-medium", "p3-low", "uncertain"]`
- **Política:** `config/jev_review_priority_policy.json` (`auto_accept_confidence: 0.85`, `minimum_margin: 0.50`)

---

## 4. Condições Experimentais

- **Condição A (Nativo):** O runtime oficial do agente (Codex ou Claude Code) recebe o prompt com o texto da tarefa e a lista de `candidate_labels`. Responde com sua inferência nativa, sem acesso ao gabarito.
- **Condição J (Advisory Jev):** O mesmo agente consulta a ferramenta Jev (via servidor MCP oficial `FrancoisChastel/jev-code` v0.5.0) com as opções delimitadas. A política local avalia se a resposta atende aos thresholds (`confidence >= 0.85`, `margin >= 0.50`, rótulo != `uncertain`). Se aceita, usa a recomendação; se rejeitada, abstém e encaminha para revisão nativa.

---

## 5. Níveis de Evidência e Proveniência

Nenhum resultado simulado poderá ser denominado `OBSERVED` ou `VERIFIED`:

| Categoria | Definição | Critérios de Validação |
| :--- | :--- | :--- |
| `SYNTHETIC` | Dados simulados ou gerados por stub/mock para testes de pipeline e verificação de schema. | `is_synthetic: true`; `model: "mock-stub"`. Status global do relatório: `SYNTHETIC_SIMULATION_ONLY`. Não autoriza adoção. |
| `OBSERVED` | Respostas reais capturadas diretamente da chamada a um provedor live (Codex, Claude ou TypeSafe Jev). | Timestamps reais, IDs de execução, hashes SHA-256 de input/output brutos, latência cronometrada e tokens relatados pelo provedor. |
| `VERIFIED` | Evidência `OBSERVED` coletada sob isolamento G1 homologado (container/VM com canários negativos externos validados e auditoria independente de chaves/redes). | Nível obrigatório para decisão final de homologação. |

---

## 6. Métricas Congeladas

Para cada condição e em cada domínio separadamente:
1. **Acurácia Micro:** Proporção de previsões concordantes com o gabarito.
2. **Macro F1-Score:** Média harmônica balanceada entre precisão e revocação por classe.
3. **Taxa de Cobertura Automática:** Porcentagem de tarefas aceitas pela política de confiança.
4. **Acurácia Automática:** Acurácia calculada estritamente sobre as decisões aceitas automaticamente.
5. **Erros Críticos de Alta Confiança:** Casos onde o modelo errou o gabarito e a política aceitou automaticamente.
6. **Taxa de Abstenção / Encaminhamento para Revisão:** Porcentagem de decisões com recusa consciente.
7. **Latência Observada (ms):** Média e percentil p95 cronometrados.
8. **Tokens Utilizados:** Média de tokens de entrada e saída informados pela API/runtime.
9. **Custo Financeiro:** USD calculado com base em tarifação real do provedor.

---

## 7. Critérios de Homologação e Decisão

- Se H1 e H3 forem confirmadas, com G1 validado e zero erros de alta confiança em casos adversariais: recomendação **`APPROVE_ADVISORY_ONLY`**.
- Se a integração adicionar latência ou custo sem ganho comprovado de qualidade: recomendação **`REJECT`**.
- Se as amostras não permitirem discriminação estatística conclusiva: recomendação **`INCONCLUSIVE`**.
- A decisão final de adoção é prerrogativa exclusiva do **Codex**, após auditoria de segurança e código.
