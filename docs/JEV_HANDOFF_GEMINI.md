# Handoff — Gemini 3.8 para execução local do piloto Jev (sem implementação extra)

**Repositório:** `Williamitiro/harness-engineering-platform`. **Branch única de trabalho:** `codex/harness-foundation-v1`, PR #2 (Draft). Preservar PR #1, main e evidências; nunca fazer merge ou force push.

## Ordem operacional
1. Fazer bootstrap: ler README, AGENTS/contratos, documentação Jev, errata de segurança, protocolo e handoff; validar git status clean e HEAD remoto antes de mudanças. Não reescrever documentação de arquitetura.
2. Executar `python -m unittest discover -s tests -v`, `python scripts/jev_offline_eval.py --input benchmarks/jev/fixtures_example.jsonl --policy config/jev_pilot_policy.json`, compilação e validação CI. Corrigir só falhas reproduzidas. Dados de fixture não são resultados de modelo.
3. Inspecionar via GitHub `FrancoisChastel/jev-code`, `felpsdev/jev-classifier`, TypeSafe docs, releases/PRs/licenses/security; confrontar com matriz em `docs/JEV_ESTUDO_COMPARATIVO.md`. Registrar divergências, versão e SHAs. Priorizar `jev-code` como primeira candidata, mas não instalar global.
4. Preparar conjunto rotulado de tarefas de *classificação*, golden labels e avaliação sem live. Não reutilizar soluções do Git pai nem escolher testes depois de ver resultados.
5. **Gate de segurança:** se isolamento externo ainda não estiver comprovado, concluir com `BLOCKED_G1` para chamadas Codex/Claude/Jev live, sem tentar resolver via prompt. Pode implementar fixtures, teste e documentação offline.
6. Se, e somente se, o ambiente de SO/container/VM tiver isolamento comprovado **e** o operador autorizar chave/custo, testar integração `jev-code` em workspace descartável e `--project --dry-run --no-env` antes de qualquer configuração. Não interceptar tráfego de modelo.
7. Registrar resultado em PR #2: comandos, versão, SHA, testes, erros, matriz, custos medidos ou UNKNOWN, canários de isolamento, e revisão necessária.
8. Encaminhar ao Codex para revisão independente de código, segurança e autorização de adoção. Gemini não declara G1/A1/B/C ou Jev homologado por conta própria.

## Entrega esperada
Scripts e testes existentes funcionando, fixtures congeladas e protegidas, relatório do piloto separado entre offline e live, nenhum segredo publicado, nenhuma mudança fora da branch, indicação explícita do próximo passo que depende do operador. Se não houver login/credenciais/isolamento, entregar tudo offline e marcar a parte live `NOT_RUN`.

**Não criar** outro runtime, proxy, classificador alternativo, stack, app web ou framework. Não substituir Codex/Claude Code.
