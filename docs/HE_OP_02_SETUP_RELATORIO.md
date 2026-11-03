# HE-OP-02 — ciclo de arquivos por repositório

Escopo autorizado: completar o setup de repositórios, mantendo a branch `codex/he-jev-007a` e PR #4 Draft. Base inicial `fdb49b1602b0e8d8926a44cf4cf2c1887ec81307`, worktree limpa, remoto e PR no mesmo SHA. Fonte normativa: SPEC §§2.1, 7, 9–11. Sem modelos, benchmark, merge ou alteração de projetos consumidores/configurações pessoais nesta execução.

## Implementação

`scripts/harnessctl.py` agora oferece:

```powershell
python scripts/harnessctl.py project-plan --repo C:/caminho/projeto --client codex
python scripts/harnessctl.py project-attach --repo C:/caminho/projeto --client codex --source C:/caminho/ecc-pinado --apply
python scripts/harnessctl.py project-verify --repo C:/caminho/projeto
python scripts/harnessctl.py project-remove --repo C:/caminho/projeto
python scripts/harnessctl.py project-remove --repo C:/caminho/projeto --apply
```

Attach exige `--apply`, destino explícito e checkout ECC existente e limpo no SHA aprovado. Nenhuma busca/download implícito. Copia somente `AGENTS.md` e os dois `SKILL.md` permitidos. `.harness/manifest.json` registra identidade, SHA/hash de cada arquivo, diretórios criados e aviso MIT completo; a licença é validada contra hash pinado no catálogo. Fonte/licença concretas: ECC `b38be6a7f6350964d59328b52f0624e1d1d552d1`, `LICENSE` SHA-256 `326146379f01bb137c0a5d3c54770c1aa31076705c8b88a7f6b26a460f6221b2`. Nenhum outro componente ECC foi distribuído.

Reaplicar verifica todos os arquivos e retorna `ALREADY_ATTACHED`. Verify não precisa do checkout ECC, apenas do catálogo e template centrais aprovados. Remove sem `--apply` exibe a prévia; com `--apply`, verifica tudo antes da primeira remoção. Arquivo alterado/ausente ou manifesto adulterado bloqueia o conjunto. A lista de paths/hashes deve coincidir exatamente com o pacote aprovado; diretórios de ownership têm allowlist separada. Links simbólicos, junctions, hardlinks e arquivos especiais são recusados. Contratos existentes ou skills de terceiros bloqueiam a primeira instalação.

Diretórios preexistentes e arquivos de terceiros são preservados. Limpeza remove somente diretórios criados pela instalação que continuem vazios. Criação usa abertura exclusiva; falha parcial de escrita limpa apenas o que a chamada criou. Remoção retém bytes em memória e restaura os arquivos já removidos se uma remoção posterior falhar. Não há backup de arquivos preexistentes a restaurar porque eles nunca são sobrepostos.

O lifecycle valida o Git real e que `--repo` é a raiz da worktree, e consulta status sem imprimir paths/conteúdo. Usa Git sem optional locks, fsmonitor, hooks ou inspeção de submódulos, com ambiente mínimo sem credenciais. Não altera Git/config/status/index. `project-doctor/plan` permanecem a inspeção estrutural somente-leitura de HE-OP-01, sem subprocessos ou leitura de conteúdo do projeto; numa instalação existente podem continuar indicando colisão. Use `project-verify` ou reaplicação de attach para verificar estado instalado; atualização/merge de pacotes não faz parte desta entrega.

## Evidências executadas

- RED inicial: 9 testes falharam por ausência do lifecycle.
- `python -W error -m unittest discover -s tests -p test_project_lifecycle.py -v`: 10 testes, OK, sem skips, 8,572 s.
- Suíte offline (`JEV_REAL_INTEGRATION=0`): 140 testes, OK, 2 skips opt-in, 19,357 s. Log local `.poc/he-op-02-offline.log`.
- Compilação de `scripts/harnessctl.py` e `git diff --check`: aprovados.
- Smoke por subprocessos CLI com **checkout ECC real pinado**, em Git fixture sob `.poc/`: plan → attach → reaplicar → verify → remove preview → remove apply. Estados esperados; comparação dos bytes de todos os arquivos antes/depois provou rollback exato. Recibo local `.poc/he-op-02-smoke.json`.
- Testes negativos: colisão de contrato/skill alheia, fake `.git`, licença incorreta, arquivo alterado/ausente, paths/hashes/diretórios/SHA adulterados no manifesto, symlink/hardlink, falha de escrita e falha de remoção; nenhum teste afrouxado para passar.

## Aceite e limites

HE-OP-02 implementado/testado offline para Codex. O pacote de projeto Claude permanece R3; a skill pessoal de bootstrap para ambos os clientes será HE-OP-02B. Arquivo copiado não prova descoberta, invocação ou comportamento do runtime.

O registro local não é uma assinatura criptográfica contra um atacante com acesso de escrita ao próprio projeto. Não há garantia de transação durável após queda de energia nem proteção contra escritor hostil concorrente; revalidações e rollback cobrem falhas locais testadas. Interrupção abrupta que deixe estado parcial exige inspeção, nunca limpeza ampla. Upgrades que mudem hashes/template bloqueiam até migração explícita. Essas limitações não autorizam sobreposição ou remoção de arquivos alterados.

Rollback da entrega de código: reverter somente o commit correspondente, se solicitado; rollback de instalação: `project-remove --apply` quando a verificação passa. R1 diário e R2 continuam PENDENTES. Próxima entrega de implementação autorizada nesta solicitação: HE-OP-02B. Evidência de CI do SHA publicado é conferida na entrega final.
