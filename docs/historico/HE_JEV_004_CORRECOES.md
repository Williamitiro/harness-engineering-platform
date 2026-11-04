# HE-JEV-004 — Correções executadas via GitHub

**Data:** 2026-11-02 · **Branch:** `codex/harness-foundation-v1` · **PR #2**.

## O que foi realmente implementado
1. `scripts/jev_adapter.py`: agora fala o contrato oficial `FrancoisChastel/jev-code@v0.5.0` em MCP: `jev_classify` recebe `instructions/items/classes` e devolve `results[]`, `usage`, `model`. Validadores conferem rótulos, probabilidades, IDs e status. O `result.isError` e erros JSON-RPC geram FAIL em vez de SUCCESS silencioso. `tokens_in/out` vêm só de `usage`; custo desconhecido é `null`, não zero ou estimativa.
2. Transporte stdio passou a usar thread leitora e fila com deadline real, ignorando notificações e IDs de resposta incorretos. O cliente encerra processos em timeout. Testado contra **mock fiel ao contrato público** e testes negativos (servidor silencioso, ID errado, `isError`).
3. `generate_attestation` devolve explicitamente `UNTRUSTED_LOCAL_DIGEST`. Os hashes servem para integridade, **não autenticidade**. `jev_evaluator.py` rejeita registros `OBSERVED/VERIFIED` mesmo com hash correto e flags isoladas até existir atestador externo confiável.
4. `scripts/prepare_blind_sandbox.py`: `--clean` proibido. Destino deve estar sob o diretório temporário do sistema, fora do checkout do Git e vazio, sem symlink. Gerar cópias de tarefas cegas **não** configura isolamento de SO. A receita Podman gerada é só preflight offline, sem chave/API e sem rede.
5. `scripts/jev_collector.py`: `mode=live` bloqueado explicitamente, até G1 externo e recibos reais do provedor. Flags `--isolation-verified`/`--api-key-authorized` não são provas de segurança e **não** habilitam rede/faturamento.
6. Testes de regressão garantem que respostas forjadas não recebem atestado, diretórios existentes não sejam apagados, o mock siga o contrato real e live permaneça bloqueado com flags autoafirmadas.

## Não foi realizado
- Nenhuma instalação do pacote Jev localmente, chamada API, autenticação, uso de créditos ou alteração de configuração do Codex/Claude.
- Nenhuma demonstração de isolamento G1 externo (container/VM) ou conectividade real com Jev.
- Nenhuma medição empírica ou execução do baseline A.
- O CI valida protocolo via mock e proteção de código, **não o serviço remoto**.

## Próxima etapa estritamente local (não duplicar código)
1. Validar a execução de preflight em container/VM com isolamento efetivo e sem mounts de home, Git pai, credenciais ou gabaritos. Completar canários negativos reais e atestado independente. Não tratar `blindness_verified` no manifesto como G1.
2. Testar a distribuição Jev 0.5.0 real em ambiente **sem chave** e verificar handshake/registro de ferramentas MCP, mediante pin de artefato e sem download aberto `npx -y` em CI. Corrigir divergências observadas.
3. Projetar a coleta e autenticação dos recibos reais da API/provider em um **verificador fora do workspace do agente**; até lá, não promover SYNTHETIC para OBSERVED/VERIFIED.
4. Preparar baseline nativo A (Codex ou Claude) com idênticas entradas sem gabaritos, versões e logs de uso reais, sem executar nenhum modelo antes das aprovações.
5. Só após G1 provado, autorização de credenciais/custos, revisão independente e testes verdes, executar um piloto pequeno com dados sintéticos mas **respostas realmente produzidas pelos modelos**.
6. Manter o PR #2 Draft e registrar status de gates sem declarações prematuras de prontidão.

## Fontes de contrato
- https://github.com/FrancoisChastel/jev-code/blob/v0.5.0/skills/jev/references/tools.md
- https://github.com/FrancoisChastel/jev-code/blob/v0.5.0/src/tools/schemas.ts
- https://github.com/FrancoisChastel/jev-code/blob/v0.5.0/src/tools/classify.ts

**Estado:** `MCP_CONTRACT_UNIT_TESTED / PROVENANCE_FAIL_CLOSED / DESTRUCTIVE_CLEAN_DISABLED / G1_NOT_VERIFIED / NO_LIVE_MODEL_EVIDENCE`.
