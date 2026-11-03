# CLAUDE.md — Harness Engineering

Fonte normativa: [docs/HARNESS_SPEC_CANONICA_USO_DIARIO_E_BENCHMARK_V1.md](docs/HARNESS_SPEC_CANONICA_USO_DIARIO_E_BENCHMARK_V1.md). Fonte histórica preservada: [dossiê dos 12 repositórios](docs/reference/CONSOLIDADO_REPOSITORIOS_HARNESS_ENGINEERING_2026-11-02.md).

Ao trabalhar neste repositório, audite primeiro branch, HEAD e alterações locais/remotas. Mantenha Codex e Claude Code como runtimes nativos: não crie um terceiro agente. Primeira implementação R1 = pacote de projeto com attach/verify/remove seguro **e skill pessoal `setup-harness` opt-in (SPEC §2.1), que apenas aciona o CLI central, sem MCP/hook**; R2 = **benchmark real de programação e telemetria obrigatório** para declarar V1 pronta, avaliando Harbor sem impor Docker/WSL. R3 = homologação Claude; R4 = JEV HTTP opcional; R5/R6 = skills e ferramentas selecionadas por lacuna.

Leia §11 da SPEC para a ordem de serviço atual. Não editar outros repositórios, instalar hooks globais, executar modelos pagos, iniciar release seguinte, fazer merge/deploy/push ou expor segredos sem autorização pertinente. Não confundir JEV classificador com programador; evitar Node/MCP para consumir a API JEV. Evidências reais e códigos testados prevalecem sobre claims antigos, custos ausentes permanecem `null`.
