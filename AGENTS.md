# AGENTS.md — Harness Engineering (instrução local para Codex)

## Fonte canônica
Leia **antes de planejar, editar, auditar ou executar releases**:
- [SPEC canônica de uso diário e benchmark](docs/HARNESS_SPEC_CANONICA_USO_DIARIO_E_BENCHMARK_V1.md), especialmente §0 (evidência), §4 (releases), §5 (benchmark), §9 (backlog), §10 (gates) e §11 (primeira ordem de serviço).
- [Dossiê original de 12 repositórios](docs/reference/CONSOLIDADO_REPOSITORIOS_HARNESS_ENGINEERING_2026-11-02.md). É **fonte histórica**, contém afirmações antigas sobre JEV/Node já superadas pela SPEC.
- [Manual](docs/MANUAL_HARNESS_V1.md) e [protocolo de avaliação](docs/PROTOCOLO_VALIDACAO.md) para invariantes e metodologia.

## Ordem de execução
- **R1 é a primeira implementação:** `HE-OP-01` (doctor + plan somente-leitura por repositório), depois attach/verify/remove (`HE-OP-02`) e a skill pessoal **`setup-harness`** como bootstrap de uma vez por agente/dispositivo (`HE-OP-02B`, SPEC §2.1), depois Codex em projeto real **autorizado**. O bootstrap invoca o CLI central; não instalar MCP ou hook global.
- **R2 é obrigatório para declarar V1 pronta:** benchmark de engenharia de software A/B com agente nativo, oráculo independente, custos/tempo/tokens e auditoria da alternativa Harbor. Nunca substituir essa prova pelo piloto JEV de classificação.
- R3 Claude, R4 roteamento JEV e R5–R6 ferramentas adicionais só após gates correspondentes; não instalar 12 upstreams por relevância.
- Não criar novo framework, runtime, MCP ou Node para a API JEV; `scripts/jev_http.py` já usa OpenRouter diretamente.

## Protocolo obrigatório de auditoria
1. Confirmar `git status --short`, branch, HEAD, remoto e PR antes de editar. Concorrência ou diffs desconhecidos: `BLOCKED` com evidência; nunca `reset --hard` implícito.
2. Inspecionar recursos nativos e código existente antes de escrever algo novo (*reuse-first*). Diferenciar o que está implementado, testado, proposto e desconhecido.
3. Alterar **uma entrega de escopo fechado** por vez, com testes direcionados, negativos e suíte offline; CI verde não equivale a benchmark real.
4. Uma única hipótese/experimento por falha, privilegiando API/CLI direta antes de instalar camada local. Nunca rodar chamadas pagas ou benchmarks sem autorização explícita.
5. Reportar SHA, arquivos, testes, lacunas, rollback, segurança, métricas reais e próximo ID de backlog. Custos parciais **nunca** são totais; despesas e franquias são grandezas distintas.
6. Não modificar outros repositórios nem configs globais sem opt-in; sem dump de secrets, merge, deploy, `git push` ou hooks persistentes por inferência.

Se instruções históricas contradisserem a SPEC sobre status JEV ou prioridade do benchmark, **a SPEC vence**, mantendo evidências originais intactas.
