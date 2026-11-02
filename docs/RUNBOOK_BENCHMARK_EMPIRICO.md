# Runbook Operacional — Execução do Benchmark Empírico Jev vs. Nativo

Este runbook documenta os procedimentos e comandos para executar o benchmark comparativo entre a classificação nativa de modelos e o classificador consultivo Jev com o gate local de políticas.

---

## 1. Estrutura de Arquivos e Componentes

- **Tarefas (Entradas Cegas):**
  - `benchmarks/jev/tasks/tasks_skills.jsonl` (Domínio Skills)
  - `benchmarks/jev/tasks/tasks_ci_triage.jsonl` (Domínio CI Triage)
  - `benchmarks/jev/tasks/tasks_code_review.jsonl` (Domínio Code Review)
  - `benchmarks/jev/tasks/tasks_all.jsonl` (Conjunto Unificado N=30)
- **Gabarito Independente (Holdout Ground Truth):**
  - `benchmarks/jev/ground_truth/golden_skills.jsonl`
  - `benchmarks/jev/ground_truth/golden_ci_triage.jsonl`
  - `benchmarks/jev/ground_truth/golden_code_review.jsonl`
  - `benchmarks/jev/ground_truth/golden_all.jsonl`
- **Políticas de Classificação:**
  - `config/jev_pilot_policy.json` (Skills)
  - `config/jev_ci_triage_policy.json` (CI Triage)
  - `config/jev_review_priority_policy.json` (Code Review)
  - `config/jev_multi_domain_policy.json` (Multi-domínio)
- **Scripts:**
  - `scripts/jev_collector.py`: Coleta de execuções com hash SHA-256 e cronometragem.
  - `scripts/jev_evaluator.py`: Verificador independente que computa métricas, Macro-F1 e separa evidências.

---

## 2. Execução em Modo de Simulação (Offline / Teste de Pipeline)

Utilizado para testar schemas, cálculo de métricas e regras de abstenção sem realizar chamadas de rede ou consumir créditos de API.

### 2.1 Coleta Simulada da Condição A (Nativa)
```powershell
python scripts/jev_collector.py `
  --tasks benchmarks/jev/tasks/tasks_all.jsonl `
  --condition CONDITION_A_NATIVE `
  --mode simulation `
  --output docs/evidence/runs/run_simulated_cond_a_all.jsonl
```

### 2.2 Coleta Simulada da Condição J (Jev Consultivo)
```powershell
python scripts/jev_collector.py `
  --tasks benchmarks/jev/tasks/tasks_all.jsonl `
  --condition CONDITION_J_ADVISORY `
  --mode simulation `
  --output docs/evidence/runs/run_simulated_cond_j_all.jsonl
```

### 2.3 Avaliação e Comparação Independente
```powershell
python scripts/jev_evaluator.py `
  --run docs/evidence/runs/run_simulated_cond_j_all.jsonl `
  --ground-truth benchmarks/jev/ground_truth/golden_all.jsonl `
  --policy config/jev_multi_domain_policy.json `
  --compare-run docs/evidence/runs/run_simulated_cond_a_all.jsonl
```

*Nota:* O relatório emitido em modo de simulação será estritamente marcado com `evidence_level: SYNTHETIC_SIMULATION_ONLY` e `recommendation: NO_EMPIRICAL_EVIDENCE_FOR_ADOPTION`.

---

## 3. Execução em Modo Live (Após Homologação do Gate G1)

Esta etapa é **BLOQUEADA** até que o operador forneça um container isolado e autorize faturamento de API.

### 3.1 Pré-Requisitos no Container
1. Container descartável ativo (sem montagem de chaves pessoais do host).
2. Variáveis de ambiente configuradas em memória:
   ```bash
   export TYPESAFE_API_KEY="sua-chave-temporaria"
   ```
3. Teste de isolamento de canários negativos aprovado.

### 3.2 Comando de Coleta Live
```bash
python3 scripts/jev_collector.py \
  --tasks benchmarks/jev/tasks/tasks_all.jsonl \
  --condition CONDITION_J_ADVISORY \
  --mode live \
  --isolation-verified \
  --api-key-authorized \
  --output docs/evidence/runs/run_live_cond_j_all.jsonl
```

### 3.3 Verificação da Evidência Coletada
```bash
python3 scripts/jev_evaluator.py \
  --run docs/evidence/runs/run_live_cond_j_all.jsonl \
  --ground-truth benchmarks/jev/ground_truth/golden_all.jsonl \
  --policy config/jev_multi_domain_policy.json
```

Apenas quando todas as amostras forem coletadas ao vivo sem simulação, o avaliador emitirá o status `evidence_level: OBSERVED_REAL_EXECUTION` (ou `VERIFIED_ISOLATED_BENCHMARK`).
