# Auditoria independente HE-JEV-001 — 02/11/2026

**Artefato auditado:** commit `a88ce619715969169fa1abbe6290fa372a69bc37`, PR #2, branch `codex/harness-foundation-v1`.

**Veredito:** `OFFLINE_CODE_VALIDATED / JEV_MODEL_NOT_TESTED / NO_EMPIRICAL_COMPARISON / G1_NOT_HOMOLOGATED`.

## O que foi efetivamente comprovado

- GitHub Actions da entrega do Gemini passou nas duas execuções `41472133579` e `41472140680`. O workflow só compila/testa código Python, audita dados históricos, processa uma fixture sintética e executa dry-run sem modelo.
- Os documentos, fixtures de 30 linhas e as políticas de classificação existem no repositório.
- `jev_offline_eval.py` computa corretamente métricas descritivas dos valores fornecidos, conforme testes offline. Não chama Codex, Claude ou TypeSafe e não mede suas respostas.
- Controle de abstenção para labels `uncertain`, baixa confiança ou margem reduzida é regra de código; prova-se apenas a regra dada uma entrada, não o comportamento real do Jev.
- O Gemini registrou G1 externo e live como NOT_RUN/BLOCKED; não há evidência de integração MCP real nem chaves usadas.

## Achados bloqueantes

### P0 — Comparativo A versus J é sintético, NÃO benchmark de modelos

`benchmarks/jev/fixtures_pilot.jsonl` contém **na mesma linha** `expected`, `native_predicted` e `predicted`, além de `native_latency_ms`, `latency_ms`, `native_tokens_in`, `tokens_in` e métricas de saída. Esses campos foram preenchidos no arquivo pelo próprio autor das fixtures; não derivam de logs de chamadas reais. O script os agrupa e calcula 22/30 versus 30/30. A condição J foi previamente ajustada para igualar cada gabarito. Portanto:
- 73,3% versus 100% = apenas aritmética de exemplos manuscritos;
- redução de 93,4% de latência e 90,8% de input tokens = comparação de números predefinidos, **não** medições;
- 'nativo foi vulnerável a injection' ou 'Jev protegido' = alegações sem testes reais de modelos;
- 'acurácia macro' = nome incorreto para acurácia global (micro) 22/30, e macro-F1 não foi calculado;
- 'o JEV elimina erros' = não demonstrado;
- `INCONCLUSIVE_FOR_PRODUCTION` é insuficiente como qualificador: **não houve sequer teste empírico**.

A partir desta auditoria, o arquivo `HE_JEV_001_BENCHMARK.json` deve ser tratado como **ARTEFATO SINTÉTICO HISTÓRICO**, não benchmark real.

### P1 — Cobertura e elegibilidade dos dados
O dataset mistura domínio de skills, CI e review numa única matriz de confusão, mas essas classes não são intercambiáveis. O futuro relatório deve medir por domínio e tratar revisão/abstenção como categoria separada; não contar `uncertain` correto como prova de resistência a injeção. Para futura medição, cada chamada requer IDs de execução, tipo de provedor, versão/modelo, timestamps e evidência bruta sanitizada com hashes e proveniência verificável. A ferramenta offline atual não verifica essa cadeia: são necessários adaptadores de ingestão e test runner aprovados, não inferir pela presença de campos preenchidos.

### P1 — Integridade do SHA de jev-skills
O registro de Gemini atribui `ff2d92b07091209c03d455d562f58c928b7b9e4e` à tag `v0.3.0`, mas GitHub `refs/tags/v0.3.0` aponta para um **objeto de tag anotada** `0c3a83ac32c6b120345f7b236f73f3433db0e301`, cujo commit-alvo é `4cb8ab4ec3c7fa3821dbd2b398b490a083b1b034`. O commit `ff2d92...` existe, mas não é a revisão contida nessa tag. Fixar commit-alvo real se for instalar ou reexecutar.

### P1 — Reconciliação de status e segurança
Muitos arquivos de documentação antigos contêm declarações de execução homologada por um runner que apenas observou um canário; a errata `docs/AUDITORIA_CORRECOES_2026-11-02.md` prevalece. Não executar Codex/Claude/Jev no host sem isolamento externo efetivo e sem opt-in do usuário. Nenhum pipeline CI do PR executa modelo.

## Correções realizadas por esta revisão

- `scripts/jev_offline_eval.py` agora rotula comparações como `SYNTHETIC_FIXTURE_ARITHMETIC_ONLY`, com proveniência explícita e recomendação `NO_EMPIRICAL_EVIDENCE_FOR_ADOPTION`; não altera os números manuscritos.
- Adicionada validação de inteiros de tokens e de latências nativas, rejeitando valores negativos ou não finitos.
- Novos testes de regressão e gate CI proíbem que comparação sintética produza status de benchmark empírico.
- O JSON histórico do Gemini foi anotado com invalidação de inferências empíricas, preservando as amostras e números originais.
- Documentação e PR devem usar **simulação offline** em vez de 'desempenho Jev medido'.

## Próximos passos locais — sequência curta
1. Codex revisa segurança e correções do PR, sem merge automático.
2. Se quiser avançar, separar golden labels de saídas dos modelos e fixar dataset, prompts e modelos antes de qualquer nova chamada.
3. Preparar contenção real (container/VM isolados, credenciais temporárias, negações de host e acesso ao Git pai), com G1 testado.
4. Medir amostras nativas de Codex e respostas reais da API Jev sob aprovação expressa de custos/dados; armazenar request IDs, hashes de payload, tempos, tokens e erros.
5. Executar avaliador independente **sobre logs reais verificados**, comparar por domínio, incluir incerteza e custos; somente então decidir `ADOPT/REJECT/DEFER`.

**Não criar outro framework nem instalar proxy global.** O trabalho feito até aqui já é uma base útil de políticas/fixtures e o cálculo offline, mas não evidencia melhoria de um modelo sobre outro.
