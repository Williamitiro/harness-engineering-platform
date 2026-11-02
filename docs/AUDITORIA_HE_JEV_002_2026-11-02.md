# Auditoria independente — HE-JEV-002 (02/11/2026)

**Fonte auditada:** commit `e4bbbea4c30d7ab290ffcbf18ab35d53ab5e9b06` do PR #2. Revisão de código, documentação, CI e evidências GitHub. **Estado após correção:** PREPARED_OFFLINE / LIVE_UNIMPLEMENTED / G1_NOT_HOMOLOGATED / NO_EMPIRICAL_MODEL_RESULTS.

## Entregas reais confirmadas
- Novo coletor `scripts/jev_collector.py` com simulação explicitamente sintética e hashes para detectar adulteração acidental do payload em trânsito/arquivo.
- Avaliador `scripts/jev_evaluator.py` com relatório por domínio, Macro-F1, taxas de aceitação e abstenção, e processamento de gabaritos separados **por diretório**.
- Tarefas, golden labels, políticas e pré-registro do estudo presentes em Git. Relatório simulado corretamente identificado como `SYNTHETIC_SIMULATION_ONLY`.
- CI verde nos dois eventos do commit `e4bbbea`: 42 testes unitários, validação offline e dry-run. **CI não executou APIs nem modelos**.
- G1 documentado como não homologado. `run_collection(...,mode="live")` SEMPRE termina em bloqueio; `--isolation-verified` é uma mera flag passada pelo operador, não prova isolamento.

## Falhas encontradas e correções implementadas

### P0 — Falsa comprovação de VERIFIED/OBSERVED
O avaliador originalmente atribuía `VERIFIED_ISOLATED_BENCHMARK` e `model_quality_proven=true` sempre que todos os registros traziam `evidence_kind: VERIFIED`. Da mesma forma `OBSERVED` bastava para concluir que modelos foram chamados. Como a mesma pessoa podia escrever os dados e seus SHA-256, era trivial falsificar. **Correção:** avaliador rejeita qualquer entrada não-sintética até implantar adaptador de captura e atestação independente. Hash local garante consistência, não origem autêntica, segurança ou execução.

### P1 — Comparação sem pareamento
A interface `--compare-run` comparava arquivos sem verificar cobertura dos mesmos `task_id`, `raw_input_sha256`, domínio ou condição. Era possível comparar amostras distintas e inferir diferenças espúrias. **Correção:** exigir mesmas tarefas, os mesmos inputs e condições A/J distintas, em runs internamente homogêneos.

### P1 — Gabarito no mesmo repositório
`benchmarks/jev/ground_truth` está versionado e acessível no mesmo checkout. A separação de pastas **não é cegamento real** se o agente puder acessar o Git pai, diretório ou histórico. **Pendente local:** sandbox que receba SOMENTE `tasks/`, sem `ground_truth/` ou histórico de respostas, com verificador independente isolado. Auditoria por canários negativos externos.

### P1 — Integração MCP é apenas TEMPLATE
`config/mcp/jev_code_mcp_template.json` não representa simultaneamente os formatos nativos do Codex e Claude Code; ainda não existe adaptador instalado, sessão Codex/Claude comprovada, nem chamadas `jev_classify` observadas. `npx -y` pode baixar conteúdo; executar apenas com versão/sha aprovados, rede e configuração efêmera controladas.

### P1 — Qualidade de fixtures
Os 30 casos originais continuam visíveis e derivados dos exemplos anteriores, logo não podem ser apresentados como holdout desconhecido para um agente com acesso ao projeto. Alguns rótulos exigem julgamento de especialistas (ex.: correção que pula testes e nível P0/P1); revisar os gabaritos de forma independente antes de medir. Um único piloto N=10 por domínio é exploratório e não valida desempenho generalizável.

### P2 — Sem collector real
Não há integração de provider, evento de resposta, medição de latência real ou coleta de custo: função `simulate_provider_call` gera dados fictícios; live está bloqueado inclusive com `--isolation-verified`. **Não se trata de bug:** é o gate de segurança correto até o ambiente externo estar pronto.

## Próxima execução recomendada
1. Codex revisa diff, CI, modelo de ameaça e regressões de proveniência; não faz merge automático.
2. Gemini/Codex local configura **isolamento real** (container/VM) e testa proibição de acesso ao host, às credenciais, ao Git pai e aos gabaritos. Não basta passar `--isolation-verified`.
3. Codex aprova adaptador de coleta real de saída MCP Jev, com logs de requests, respostas e métricas do provedor, e coleta nativa separada (Codex e/ou Claude Code). `VERIFIED` exige trilha externa e evidência revisável, não campo JSON declarativo.
4. Refazer tarefas com holdout inédito e anotadores independentes, registrar versões/IDs, congelar critérios e amostra. JAMAIS reutilizar valores simulados para inferência causal.
5. Com G1 aprovado **e aprovação explícita de chaves/custos pelo operador**, executar piloto pequeno, sem bypass; comparar evidência real; reportar `INCONCLUSIVE` se amostra insuficiente.

**Critério de adoção:** resultados empíricos auditáveis + melhoria líquida de qualidade/custo/latência sem regressão de privacidade. Caso contrário, não adotar.
