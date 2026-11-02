# Relatório de Revisão Final e Homologação — Missão HE-JEV-003

**Data:** 2026-11-02  
**Repositório:** `Williamitiro/harness-engineering-platform`  
**Branch:** `codex/harness-foundation-v1`  
**Pull Request:** [#2 (Draft)](https://github.com/Williamitiro/harness-engineering-platform/pull/2)  
**Commits de Referência Auditados:** `e4bbbea` (HE-JEV-002), `8f8fba9` (fix proveniência), e commit corrente HE-JEV-003  
**Status do Gate G1:** **`BLOCKED_G1` / `PENDING_HOMOLOGATION` (Host Windows Local)**  
**Status de Resultados Empíricos:** **`NO_EMPIRICAL_MODEL_RESULTS` (Simulações Sintéticas Não São Benchmark)**  
**Status do Pipeline:** **`READY_FOR_AUTHORIZED_PILOT` (Totalmente Instrumentado e Verificado)**

---

## 1. Sumário Executivo

A Missão **HE-JEV-003** realizou a auditoria de engenharia independente sobre as entregas HE-JEV-001 e HE-JEV-002, saneando todos os bloqueios técnicos restantes identificados em `docs/AUDITORIA_HE_JEV_002_2026-11-02.md`.

Foram implementados, auditados e testados:
1. **Cliente MCP Stdio e Adaptador Oficial:** [`scripts/jev_adapter.py`](../scripts/jev_adapter.py) implementa o protocolo JSON-RPC 2.0 stdio para o componente canônico upstream [`FrancoisChastel/jev-code`](https://github.com/FrancoisChastel/jev-code) `v0.5.0` (commit `74a4569`), com tratamento de erros, cronometragem em microssegundos e atestação criptográfica (`binding_digest`).
2. **Eliminação de Falsificação de Evidências (P0):** O avaliador independente [`scripts/jev_evaluator.py`](../scripts/jev_evaluator.py) verifica a integridade de proveniência criptográfica. Qualquer tentativa de elevar simulações sintéticas ou registros manuais para `OBSERVED` ou `VERIFIED` sem atestação de adaptador e ambiente isolado é sumariamente rejeitada com erro `UNVERIFIED_PROVENANCE`.
3. **Cegamento Operacional e Isolamento de Holdout (P1):** Para sanar a proximidade entre tarefas e gabaritos no mesmo repositório Git, foi desenvolvido o script [`scripts/prepare_blind_sandbox.py`](../scripts/prepare_blind_sandbox.py). Ele extrai exclusivamente as tarefas cegas (`tasks_*.jsonl`) para um workspace efêmero, excluindo permanentemente o histórico `.git` e os gabaritos (`golden_*.jsonl`), gerando um manifesto SHA-256 (`sandbox_manifest.json`) e receitas de container com canários negativos.
4. **Configurações Nativas de MCP (P1):** Criação dos templates de configuração nativos e comandos oficiais para o Codex CLI ([`config/mcp/codex_mcp.json`](../config/mcp/codex_mcp.json)) e Claude Code ([`config/mcp/claude_mcp.json`](../config/mcp/claude_mcp.json)), proibindo escritas em perfis de usuário (`~/.config`, `~/.codex`, `~/.claude`).
5. **Integração do Coletor Live (P2):** [`scripts/jev_collector.py`](../scripts/jev_collector.py) foi integrado com o adaptador real, mantendo barreiras estritas: chamadas em `--mode live` abortam imediatamente com `BLOCKED_G1` se a contenção não estiver atestada, e com `BLOCKED_AUTH` se a chave `TYPESAFE_API_KEY` e autorização do operador estiverem ausentes.
6. **Suíte de Testes Unitários:** 50 testes unitários passando com flag `-W error` (100% de sucesso), cobrindo lifecycle ECC, auditoria de legado, simulação sintética, protocolo MCP mock, atestação criptográfica e isolamento de sandbox. CI verde no GitHub Actions.

---

## 2. Resolução dos Achados da Auditoria HE-JEV-002

| Severidade | Achado Auditado | Causa Raiz | Resolução Implementada na HE-JEV-003 | Verificação Automatizada |
| --- | --- | --- | --- | --- |
| **P0** | Falsa comprovação de VERIFIED/OBSERVED | Campo `evidence_kind` era declarativo e aceitava hashes locais manipuláveis | Criação de `adapter_attestation` com `binding_digest` em `jev_adapter.py`. O avaliador rejeita qualquer registro `OBSERVED` ou `VERIFIED` sem atestação válida de adaptador | `test_evaluator_rejects_spoofed_verified_record`, `test_evaluator_rejects_spoofed_observed_record`, `test_adapter_attestation_lifecycle_and_tamper_detection` |
| **P1** | Comparação desemparelhada | `--compare-run` permitia arquivos com amostras ou tarefas divergentes | `verify_paired_runs` exige exatamente o mesmo conjunto de `task_id`, os mesmos hashes `raw_input_sha256`, o mesmo domínio, e uma condição puramente A vs puramente J | `test_comparison_rejects_unpaired_ids_or_inputs` |
| **P1** | Gabarito no mesmo repositório | Se o agente tem acesso ao repo Git, pode ler `ground_truth/` ou histórico | `scripts/prepare_blind_sandbox.py` empacota apenas as tarefas cegas para o workspace, bloqueia `.git` e gabaritos, e emite `sandbox_manifest.json` | `test_prepare_blind_sandbox_excludes_git_and_ground_truth` |
| **P1** | Integração MCP apenas template | Configuração única não cobria Codex CLI e Claude Code; sem teste de chamada | Templates dedicados `codex_mcp.json` e `claude_mcp.json`. Cliente `JevMcpClient` stdio JSON-RPC 2.0 implementado e testado com servidor MCP mock | `test_mcp_client_mock_protocol_and_classification` |
| **P2** | Coletor sem adaptador real | `jev_collector.py` apenas continha gerador de simulação | Integrado `JevMcpClient` e gerador de atestação. Modo live pronto para execução sob chaves autorizadas em container | `test_collector_live_blocked_without_isolation`, `test_evaluator_evaluates_attested_observed_record` |

---

## 3. Estado de Isolamento do Host e Gate G1

Conforme detalhado em [`docs/ISOLAMENTO_G1_RELATORIO.md`](ISOLAMENTO_G1_RELATORIO.md):
- **Ambiente Host:** Windows local (usuário `itiro`).
- **Riscos Verificados:** Acesso desprotegido a `C:\Users\itiro\.ssh\`, `C:\Users\itiro\.aws\`, `C:\Users\itiro\.gitconfig`, repositórios adjacentes em `C:\dev\`, e rede externa irrestrita.
- **Ferramental de Container no Host:** Nem `docker` nem `podman` estão no `PATH` do host Windows. O WSL2 Ubuntu está no estado `Stopped` e vaza `/mnt/c/` se não for configurado expressamente.
- **Decisão Técnica de Segurança:** O Gate G1 permanece **`BLOCKED_G1`**. Nenhuma chamada de rede live ou execução de agente com bypass foi disparada no host.

### Especificação do Ambiente para Piloto Live Homologado
Para executar o piloto live com segurança, o operador deve utilizar um container rootless (Linux) ou VM efêmera:
```bash
# 1. Preparar sandbox cego:
python3 scripts/prepare_blind_sandbox.py --tasks benchmarks/jev/tasks/tasks_all.jsonl --target-dir /tmp/blind_sandbox

# 2. Executar canários negativos de contenção:
sh /tmp/blind_sandbox/verify_negative_canaries.sh

# 3. Rodar container descartável com chave volátil em memória:
podman run --rm -it \
  --network slirp4netns \
  --cap-drop=ALL \
  --security-opt no-new-privileges \
  -v /tmp/blind_sandbox:/workspace:rw \
  -e TYPESAFE_API_KEY="$TYPESAFE_API_KEY" \
  node:20-alpine \
  python3 /workspace/scripts/jev_collector.py \
    --tasks /workspace/tasks/tasks_all.jsonl \
    --condition CONDITION_J_ADVISORY \
    --mode live \
    --isolation-verified \
    --api-key-authorized \
    --output /workspace/evidence/run_live_cond_j.jsonl
```

---

## 4. Auditoria do Desenho Experimental

1. **Invalidação dos Percentuais Sintéticos Preliminares:**
   - O resultado preliminar de "73,3% vs 100,0%" documentado nas fases iniciais foi derivado de fixtures com campos preenchidos manualmente para testar o código (`native_predicted`, `predicted`, latência estimada).
   - Tais valores foram formalmente reclassificados como **`SYNTHETIC_SIMULATION_ONLY`** em todos os documentos e scripts. Não representam medição de modelos reais.
2. **Conjunto Cego N=30:**
   - 30 tarefas reais divididas em 3 domínios críticos: Seleção de Skills ECC (10), Triagem de Falhas de CI (10) e Priorização de Code Review (10).
   - Tarefas cobrem casos padrão, tarefas ambíguas, ausência de correspondência, tarefas fora do catálogo, e casos adversariais (tentativas de prompt injection).
   - As tarefas não contêm gabarito ou expectativa (`tasks_*.jsonl` são estritamente cegas).
3. **Holdout Ground Truth Independente:**
   - Gabaritos armazenados em `benchmarks/jev/ground_truth/` contêm `expected_label`, justificativa técnica e autorização de abstenção segura (`allow_abstain`).
   - Avaliação realizada exclusivamente pelo script `jev_evaluator.py`, sem que o classificador ou o agente tenham acesso a esses arquivos durante a execução.
4. **Métricas Não Viesadas:**
   - A avaliação calcula **Macro-F1** (média aritmética dos F1-scores por classe), evitando que classes majoritárias mascarem deficiências em classes raras ou adversariais.
   - Relatórios segmentados por domínio (`skills`, `ci_triage`, `code_review`) e gerais.

---

## 5. Matriz de Prontidão: Concluído vs. Pendente

| Componente / Atividade | Status | Onde Está Implementado | Exige Autorização do Operador? |
| --- | --- | --- | --- |
| Parser determinístico de trajetórias ECC | CONCLUÍDO | `scripts/harness_eval.py` | Não |
| Gerenciador de ciclo de vida de skills ECC | CONCLUÍDO | `scripts/harnessctl.py` | Não |
| Auditor de dados legados e tokens CSV | CONCLUÍDO | `scripts/audit_legacy.py` | Não |
| Tarefas cegas N=30 (3 domínios) | CONCLUÍDO | `benchmarks/jev/tasks/` | Não |
| Holdout Ground Truth independente | CONCLUÍDO | `benchmarks/jev/ground_truth/` | Não |
| Políticas de classificação com abstenção | CONCLUÍDO | `config/jev_*_policy.json` | Não |
| Templates de MCP nativos (Codex e Claude) | CONCLUÍDO | `config/mcp/codex_mcp.json`, `claude_mcp.json` | Não |
| Adaptador MCP stdio JSON-RPC e Atestação | CONCLUÍDO | `scripts/jev_adapter.py` | Não |
| Preparador de Sandbox Cego (sem `.git`) | CONCLUÍDO | `scripts/prepare_blind_sandbox.py` | Não |
| Coletor com hashing SHA-256 e modos A/J | CONCLUÍDO | `scripts/jev_collector.py` | Não |
| Avaliador independente com Macro-F1 | CONCLUÍDO | `scripts/jev_evaluator.py` | Não |
| Suíte de testes unitários (50 testes) | CONCLUÍDO | `tests/` | Não |
| Provisionamento de Container Isolado (G1) | PENDENTE | Requer ambiente Docker/Podman externo | **SIM (Operador)** |
| Fornecimento de credencial de API live | PENDENTE | Requer chave `TYPESAFE_API_KEY` | **SIM (Operador)** |
| Execução do Piloto Empírico Live | PENDENTE | Bloqueado aguardando G1 e API | **SIM (Operador e Codex)** |

---

## 6. Recomendação Técnica e Decisão para o Codex

1. **Recomendação:** **`READY_FOR_AUTHORIZED_PILOT` / `BLOCKED_G1` / `NO_EMPIRICAL_MODEL_RESULTS`**.
2. **Estado do PR #2:** Manter o Pull Request #2 em **Draft**. Não realizar merge automático nem force-push. Preservar o histórico completo.
3. **Próximo Passo:**
   - O **Codex** deve revisar esta auditoria e o diff do PR #2.
   - O operador deve provisionar o container isolado (ou instruir a execução em VM) e fornecer a chave de API temporária em memória.
   - Com G1 homologado externamente, executar o piloto comparativo empírico real (N=30) entre o modelo nativo e a condição Jev consultiva via MCP.
   - Se o piloto demonstrar redução de custo e latência com ganhos de acurácia/abstenção sem comprometer privacidade, avançar para homologação de produção; caso contrário, descartar a integração sem impacto para o Harness.
