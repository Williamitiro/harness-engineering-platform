# Harness Engineering — integração seletiva, verificável e reutilizável

**Status:** implementação inicial em revisão, não homologada. Este repositório NÃO é um runtime próprio de agentes. Os executores de código autorizados são **Codex** e **Claude Code**; o experimento histórico com Gemini/Antigravity é evidência legada, não referência de adoção.

## Comece aqui

- [Manual técnico e decisões](docs/MANUAL_HARNESS_V1.md)
- [Procedimento operacional e comandos](docs/RUNBOOK_CODEX_CLAUDE.md)
- [Protocolo experimental e critérios de aceite](docs/PROTOCOLO_VALIDACAO.md)
- [Handoff de conclusão para Codex](docs/HANDOFF_CODEX.md)
- [Fontes, revisão e política de atualização](docs/UPSTREAM_REUSE.md)
- [Registro de riscos e fases](docs/DECISOES_E_RISCOS.md)
- [Legado A0](docs/A0_RELATORIO_2026-11-01.md) e [HE-AG-001](docs/HE_AG_001_RELATORIO_2026-11-01.md)

## Entregue nesta branch

Ferramenta offline (Python stdlib) para planejar, instalar, conferir e remover **exatamente duas** skills ECC pinadas, com checagem de SHA e proteção contra colisão; auditor numérico dos CSVs legados; testes unitários e CI. Tudo isso é *preparação de A1*, não prova de skill funcional.

```powershell
# Execute na raiz do repositório. Prefira um diretório .poc descartável.
python -m unittest discover -s tests -v
python scripts/audit_legacy.py docs/evidence/HE_AG_001_RESULTADOS.csv --expected-input 419019
python scripts/harnessctl.py plan --source .poc/ecc-pinned --target .poc/a1-codex --adapter codex
# Escrita expressamente opcional, SOMENTE após conferir o plano:
python scripts/harnessctl.py install --source .poc/ecc-pinned --target .poc/a1-codex --adapter codex --apply
python scripts/harnessctl.py verify --target .poc/a1-codex
python scripts/harnessctl.py remove --target .poc/a1-codex --apply
```

Os diretórios de destino devem existir dentro de `.poc/`; o checkout do ECC deve ter o HEAD exatamente igual ao commit do manifesto. Esta ferramenta **não baixa repositórios, não instala plugins, não executa agentes, não habilita hooks, não faz deploy**.

## Política de segurança

Sem credenciais no Git; sem automação de publicação; sem alteração da home do usuário, do Core, Forja ou Marketing OS; sem execução com LLM em CI. Branches/PRs têm revisão independente; evidência de arquivo copiado não é evidência de skill carregada, invocada ou obedecida.

## PRs

O PR #1 contém o trabalho anterior A0 e evidências HE-AG-001; **não é reescrito por esta entrega**. Esta branch parte do commit de #1 e deve ser integrada apenas depois de validar o histórico e os testes, sem merge automático.
