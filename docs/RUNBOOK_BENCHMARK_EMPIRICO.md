# Runbook Operacional — Execução do Benchmark Empírico Jev vs. Nativo

> **AUDITORIA DE SEGURANÇA 02/11/2026 (HE-JEV-003):** 
> 1. O avaliador rejeita qualquer registro sem proveniência criptográfica verificada (`adapter_attestation`). Falsificar hashes locais não permite upgrade para `OBSERVED` ou `VERIFIED`.
> 2. O gabarito no mesmo repositório Git **não é blindado operacionalmente**. É obrigatório utilizar `scripts/prepare_blind_sandbox.py` para exportar SOMENTE as tarefas para um workspace isolado sem `.git` e sem `golden_*`.
> 3. Chamadas live permanecem **bloqueadas no host Windows (`BLOCKED_G1`)** até execução em container/VM descartável com autorização expressa de API.

---

## 1. Estrutura de Arquivos e Componentes

- **Tarefas (Entradas Cegas — Sem Respostas):**
  - `benchmarks/jev/tasks/tasks_skills.jsonl` (Domínio Skills)
  - `benchmarks/jev/tasks/tasks_ci_triage.jsonl` (Domínio CI Triage)
  - `benchmarks/jev/tasks/tasks_code_review.jsonl` (Domínio Code Review)
  - `benchmarks/jev/tasks/tasks_all.jsonl` (Conjunto Unificado N=30)
- **Gabarito Independente (Holdout Ground Truth — Restrito ao Avaliador):**
  - `benchmarks/jev/ground_truth/golden_skills.jsonl`
  - `benchmarks/jev/ground_truth/golden_ci_triage.jsonl`
  - `benchmarks/jev/ground_truth/golden_code_review.jsonl`
  - `benchmarks/jev/ground_truth/golden_all.jsonl`
- **Políticas de Classificação:**
  - `config/jev_pilot_policy.json` (Skills)
  - `config/jev_ci_triage_policy.json` (CI Triage)
  - `config/jev_review_priority_policy.json` (Code Review)
  - `config/jev_multi_domain_policy.json` (Multi-domínio)
- **Configurações Nativas de MCP:**
  - `config/mcp/codex_mcp.json` (Codex CLI)
  - `config/mcp/claude_mcp.json` (Claude Code)
  - `config/mcp/jev_code_mcp_template.json` (Template canônico upstream)
- **Scripts:**
  - `scripts/prepare_blind_sandbox.py`: Prepara workspace cego sem `.git` nem gabaritos.
  - `scripts/jev_adapter.py`: Cliente stdio MCP JSON-RPC 2.0 e gerador de atestação criptográfica.
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

## 3. Preparação do Sandbox Cego (Eliminação de Contaminação)

Para garantir que o agente não acesse gabaritos nem histórico Git:

```powershell
python scripts/prepare_blind_sandbox.py `
  --tasks benchmarks/jev/tasks/tasks_all.jsonl `
  --target-dir /tmp/blind_eval_workspace `
  --clean
```

O diretório de destino `/tmp/blind_eval_workspace` conterá:
- `tasks/tasks_all.jsonl` (sem gabaritos)
- `scripts/jev_collector.py` e `scripts/jev_adapter.py`
- `config/` (políticas e configurações MCP)
- `Containerfile` e scripts de canários negativos
- `sandbox_manifest.json` com os hashes SHA-256 de todos os arquivos exportados.

---

## 4. Execução em Modo Live (Após Homologação do Gate G1)

Esta etapa é **BLOQUEADA** até que o operador forneça um container isolado e autorize faturamento de API.

### 4.1 Verificação de Canários Negativos no Container
Antes de executar qualquer coleta live:
```bash
sh verify_negative_canaries.sh
```
O script deve confirmar que `/root/.ssh`, `~/.aws` e `/mnt/c` são estritamente inacessíveis.

### 4.2 Injeção Volátil de Credenciais em Memória
```bash
export TYPESAFE_API_KEY="chave-temporaria-do-operador"
```

### 4.3 Comando de Coleta Live (Jev Consultivo via MCP)
```bash
python3 scripts/jev_collector.py \
  --tasks tasks/tasks_all.jsonl \
  --condition CONDITION_J_ADVISORY \
  --mode live \
  --isolation-verified \
  --api-key-authorized \
  --output /workspace/evidence/run_live_cond_j_all.jsonl
```

### 4.4 Avaliação Independente Fora do Sandbox
Após extrair `run_live_cond_j_all.jsonl` do container para o ambiente do avaliador:
```bash
python3 scripts/jev_evaluator.py \
  --run evidence/run_live_cond_j_all.jsonl \
  --ground-truth benchmarks/jev/ground_truth/golden_all.jsonl \
  --policy config/jev_multi_domain_policy.json
```

Apenas quando a coleta for realizada com atestação de adaptador e provas de contenção aprovadas, o avaliador emitirá `OBSERVED_REAL_EXECUTION` ou `VERIFIED_ISOLATED_BENCHMARK`.
