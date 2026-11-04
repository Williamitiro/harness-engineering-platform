# HE-OP-02/02B — correções dos três achados de review

Base revisada: `c5c9ab78d7fce27e6dcce0898a960050aa892632`. Correção solicitada pelo usuário na mesma branch `codex/he-jev-007a`, PR #4 Draft. Antes de editar: worktree limpa; fetch e comparação local/remoto `0 0`; PR no mesmo SHA. Nenhuma configuração pessoal, projeto consumidor, modelo, benchmark, merge ou deploy foi executado.

## P1 — salvar arquivo entre verificação e remoção

`remove_package` agora compara cada snapshot com o hash aprovado no registro, antes da primeira remoção. Também confirma que o registro continua semanticamente igual ao validado. A comparação imediatamente antes de cada `unlink` continua ativa: se houver edição após o snapshot, interrompe e restaura os arquivos anteriores já removidos, preservando a edição que provocou o bloqueio.

Regressões exercitam salvar `AGENTS.md` depois de `verify_project`, salvar `SKILL.md` depois da verificação do bootstrap e editar a segunda skill enquanto a primeira remoção acontece. Edições humanas e registro de ownership são preservados; a comparação anterior apenas entre snapshot novo e bytes atuais não é mais suficiente para autorizar remoção.

## P1 — filtros externos disparados por Git status

Antes de `status`, `git_probe` consulta **somente os nomes** das configurações `filter.*.clean/process`, incluindo os arquivos de configuração efetivos. Para cada driver encontrado, passa overrides `clean=`, `process=` e `required=false` apenas ao subprocesso. Não lê os valores dos comandos, não os imprime e não altera `.git/config` ou configurações globais. Falha ao inspecionar a configuração bloqueia a sondagem. Hooks, fsmonitor, herança de credenciais e optional locks continuam desativados.

Um teste Git real configura filtros canário inofensivos `clean` e `process` em fixture temporária. Controle positivo: `git status` nativo executa o canário. Depois o teste apaga apenas o marcador artificial e chama a sondagem do Harness: **nenhum canário é executado**, e os bytes de `.git/config` continuam idênticos. A primeira solução experimental de recusar toda definição de filtro foi descartada porque Git for Windows pode ter LFS preconfigurado mesmo em repos que não o usam; os overrides evitam esse bloqueio desnecessário sem executar filtros.

A sondagem passa a comparar conteúdo sem a conversão de filtros externos. Portanto o status não representa uma avaliação funcional de LFS/outro driver. A validação da fonte ECC continua baseada no SHA e nos hashes exatos dos arquivos aprovados. Alterar a configuração do repositório concorrentemente entre consulta e execução continua fora da garantia contra escritor hostil; nenhum mecanismo novo de isolamento de processos foi alegado.

## P2 — falha de rmdir após apagar manifesto

A limpeza de diretórios agora está dentro do bloco transacional. A chamada registra quais diretórios realmente removeu. Se um `rmdir` posterior falhar, recria somente esses diretórios, dos pais para os filhos, e restaura os arquivos e o manifesto por criação exclusiva, sem sobrepor arquivos alheios. A remoção permanece verificável e pode ser tentada novamente depois que a causa do erro terminar.

Regressões provocam falhas **tardias**, depois da remoção de outros diretórios: `.harness` no projeto e `.agents` na home sintética. Confirmam bytes restaurados, registro presente, verificação válida e nova remoção bem-sucedida. No projeto também comparam a lista de diretórios antes/depois. Nada foi apagado na home real.

## Comandos e resultados observados

Ambiente local: Windows / Python 3.12.10.

| Validação | Resultado |
| --- | --- |
| Regressões antes da correção em `test_project_lifecycle.py` | RED: 14 testes, 4 falhas, 12,629 s; achados de snapshot, rmdir e os dois filtros reproduzidos |
| `python -W error -m unittest discover -s tests -p test_project_lifecycle.py -v` | 14 testes, OK, 14,527 s |
| `python -W error -m unittest discover -s tests -p test_setup_skill.py -v` | 10 testes, OK, 0,359 s |
| `python -W error -m unittest discover -s tests -p test_harnessctl.py -v` | 14 testes legados, OK, 7,419 s |
| `python -W error -m unittest discover -s tests -v`, `JEV_REAL_INTEGRATION=0` | 154 testes, OK, 2 skips opt-in (152 passaram), 22,373 s |
| `python -m py_compile scripts/harnessctl.py tests/test_project_lifecycle.py tests/test_setup_skill.py` | código 0 |
| `git diff --check` | código 0 |

Logs locais ignorados: `.poc/he-review-red.log` e `.poc/he-review-fixes-offline.log`. Skips: integração externa de pacote upstream e integração nativa MXC. CI do commit publicado e igualdade HEAD/remoto/PR são conferidos na entrega final; CI antigo não é atribuído à correção nova.

## Limites e continuidade

Os seis novos métodos de teste cobrem os três achados sem afrouxar os anteriores. Os canários executam apenas scripts artificiais criados pela própria suíte em fixtures; nenhuma ferramenta real do repositório do usuário é disparada como filtro.

A proteção continua sendo revalidação e rollback local, sem transação durável após queda de energia nem garantia contra substituições hostis entre a última leitura e o `unlink`. Falhas simultâneas no próprio mecanismo de restauração exigem inspeção. Não se afirma isolamento nativo nem descoberta/invocação da skill a partir desses testes.

R1 diário e R2 permanecem pendentes. Próxima ação de produto: ativação pessoal explícita e validação nativa HE-OP-02B, seguida de HE-OP-03 em projeto escolhido, sem execução automática neste pedido. Rollback do código, se solicitado: reverter somente o commit desta correção, preservando o histórico e os demais commits da branch.
