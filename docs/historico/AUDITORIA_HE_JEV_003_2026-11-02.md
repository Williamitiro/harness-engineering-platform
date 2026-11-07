# Auditoria independente HE-JEV-003 — 02/11/2026

**Commit auditado:** `a35541ea745da13d44250573ff2ca1478f2d83b8` · **PR #2 (Draft)**. Inspeção de código fonte, testes, workflows reais e contrato oficial de `FrancoisChastel/jev-code@v0.5.0`.

**Veredito:** `OFFLINE_CI_PASS / MCP_INCOMPATIBLE / UNAUTHENTICATED_PROVENANCE / G1_BLOCKED / LIVE_PILOT_NOT_READY`.

## Fatos positivos verificados
- A alteração existe e o CI do commit `a35541e` passou em ambas as execuções GitHub Actions: `41485987789` e `41485976106`, 50 unit tests.
- `JevMcpClient`, mecanismo de simulação/coleção, pacote de tasks sem gabaritos, templates MCP, pré-registro e política estão versionados.
- O fluxo live real não foi executado: não há chamadas pagas ao Jev ou baseline Codex/Claude observadas; G1 segue não homologado.

## Bloqueios antes de qualquer execução live

### P0-1 — Contrato MCP real incompatível
**Fonte primária pinada:** https://github.com/FrancoisChastel/jev-code/blob/v0.5.0/skills/jev/references/tools.md e `src/tools/classify.ts`.

O adapter chama `tools/call` `jev_classify` com `{"question": question, "choice": choices}`. A ferramenta **v0.5.0** requer `{"instructions": "...", "items": [{"id": "...", "text": "..."}], "classes": {"class_id": "meaning", ...}}`. O output é `{"results": [{"id": ..., "label": ..., "confidence": ..., "margin": ...}], "usage": {"input_tokens": ..., "output_tokens": ...}, "model": "..."}`, **não** um único `{"choice": ...}`. O servidor possui `isError: true` em `result` para falhas de ferramenta. O mock atual (`tests/test_jev_empirical_pipeline.py`) reproduz o contrato incorreto e por isso PASS é falso positivo de compatibilidade.

**Ação:** corrigir adaptador contra esquemas reais da tag, validar ID/label e erros, adicionar fixture e testes de contrato reais, sem API paga.

### P0-2 — Digest chamado 'atestação criptográfica' não autentica provedor
`generate_attestation` produz `binding_digest = SHA256(task_id:hash_input:hash_output:adapter:provider:model:version:commit)`; **não existe chave de assinatura, HMAC, atestador externo, verificação de identidade do servidor ou recibo de provider**. Quem cria o JSON pode inventar resposta, metadata e um digest consistente. Em `jev_evaluator.py`, `verify_attestation` valida apenas consistência e permite promover registros com `evidence_kind=VERIFIED` + flags `environment_isolated=true` e `canary_check_passed=true` escritas pelo próprio produtor. No próprio teste `test_evaluator_evaluates_attested_observed_record`, a suposta observação live é criada artificialmente em Python.

**Ação:** separar `LOCAL_CHECKSUM` de `TRUSTED_ATTESTATION`. Até existir prova externa e não forjável de execução, recusar promoção OBSERVED/VERIFIED e recomendação de modelo aprovado; guardar outputs live como `UNVERIFIED_OBSERVATION` ou bloqueá-los. O avaliador não deve emitir `model_quality_proven=true` por conteúdo autorreferenciado. Incluir teste que forja resposta+digest+flags e exige FAIL.

### P0-3 — Preparação de workspace pode apagar diretórios arbitrários
`prepare_blind_sandbox.py::prepare_blind_sandbox`: `--clean` executa `shutil.rmtree(target_dir)` após `target_dir.resolve()`, recusando apenas `target_dir == ROOT`. Não há restrição a descendência de uma raiz descartável nem proteção adequada a destino personalizado. **Não executar --clean até corrigir**.

**Ação:** eliminar deleção automática ou exigir destino exatamente dentro de raiz descartável própria, com regras de ownership, symlink/ancestor protection, validação prévia, rollback e testes negativos (incluindo outro diretório do operador). Não apagar evidências existentes.

### P0-4 — 'Isolamento verificado' é autoafirmação
`jev_collector.py` aceita `--isolation-verified` e copia esse boolean para `canary_check_passed`; `jev_evaluator.py` confia no campo do próprio registro. O `verify_negative_canaries.sh` apenas verifica presença de quatro paths, não tenta demonstrar bloqueio de acesso ao Git pai, volumes, chave e rede. O `run_isolated_podman.sh` usa `node:20-alpine` sem instalar Python do `Containerfile`, deixando o runner inconsistente; usa mount `:rw` e rede sem whitelist demonstrada. **G1 = BLOCKED**, independentemente de flags.

### P1 — Métricas falsas e falhas de protocolo
- `JevMcpClient.classify` gera `tokens_in=len(question)//4`, `tokens_out=32` e `cost_usd=0.00001` como se fossem observados. Erro também retorna `cost_usd=0.0`. Substituir por `usage` do provedor quando presente e `null/UNKNOWN` no restante.
- `_send_and_receive` usa `stdout.readline()` bloqueante, portanto o teste de `time.monotonic` no laço não impõe deadline se o servidor fica silencioso. Falta correlação pelo `id` JSON-RPC e tratamento robusto de notifications, stderr e `result.isError`. Usar transporte MCP SDK oficial, ou cliente stdlib com timeout efetivo e testes reais de hang/ID errado.
- `CONDITION_A_NATIVE` não tem executor implementado, é explicitamente bloqueado no coletor; não é possível comparar A/J empiricamente.
- `npx -y @french-castle/jev-code@0.5.0` fixa versão sem registrar integridade de artefato/lockfile efetivo. Provisionar em imagem efêmera e pinada.
- O Gabarito está em `ground_truth/` no repositório original. O processo só será cego se o executor receber workspace limitado e sem acesso ao Git original/histórico.

## Próxima missão objetiva HE-JEV-004 (Codex executor)
1. Corrigir primeiro P0-2 e P0-3 em código com testes adversariais; não homologar live.
2. Corrigir contrato Jev `v0.5.0` e parsing, status de erros e métricas `UNKNOWN` quando não medidas; testar com fixtures derivadas do upstream pinado e mock fiel.
3. Corrigir framing/timeout de MCP ou adotar SDK oficial; incluir testes de servidor silencioso, resposta com ID incorreto e isError.
4. Preparar isolamento real e revisável para `G1`, entregando a Codex a evidência dos canários negativos fora do executor, sem Docker/WSL/home compartilhada e sem deletar diretórios.
5. Implementar baseline A com mesmo corpus e coleta realmente observada, preservando segregação de gabaritos; exigir aprovação de custos e keys antes de qualquer chamada real.
6. CI integral verde; relatório de revisão independente; sem merge e sem alegação de superioridade Jev por simulação.

**Status final:** não iniciar `READY_FOR_AUTHORIZED_PILOT` ainda; o rótulo adequado é `BLOCKED_LIVE_INTEGRATION_AND_G1`. Seguir com implementação local offline e revisão no PR #2.
