# Errata e correções de auditoria — Harness Engineering (02/11/2026)

## Origem e prova
Branch PR #2, HEAD anterior `847835f`. GitHub Actions `41462268408` e `41462276596` concluíram **FAIL**: dois testes do avaliador dependiam da descoberta de binários locais, inexistentes no CI Linux. Relatório anterior dizia 21/21 PASS local; isso não equivale ao CI remoto.

## Desqualificação da comparação A/C antiga
O commit `cea85b0` incluiu `.poc/eval-codex-A-ratelimit/ratelimit.py` e `test_ratelimit.py` em Git. Durante a condição A, o Codex executou `git show HEAD:.poc/eval-codex-A-ratelimit/...` e copiou esses arquivos. A amostra **não é baseline independente**. Os 7 testes passaram para o artefato observado, mas nenhuma inferência causal de eficácia/eficiência ECC pode ser feita. Remover esses dois arquivos do HEAD (preservados no histórico) não desfaz a contaminação do teste antigo.

## Segurança
- `setup_sandbox` apagava `target` com `shutil.rmtree` antes de conferir limites; removido. Recusar diretórios existentes não vazios. Aceitar somente filhos da `.poc` canônica deste repositório.
- `check_sandbox` do instalador faz guardrails de arquivos, não isolamento de SO. Execução de agentes em diretório .poc no host não impede ler o Git pai/arquivos pessoais.
- Flag `--dangerously-skip-permissions` removida do comando Claude.
- Chamada live bloqueada por padrão. O opt-in `--live-in-preisolated-environment` requer isolamento de SO/container/VM **estabelecido e comprovado externamente**. O flag não concede isolamento e não autoriza escrever credenciais, acessar rede ou produzir alterações externas.
- `isolation_verified` permanece falso até inspeção independente da camada real de contenção. Canário intacto = apenas canário intacto.
- `cost_usd` desconhecido é `null`, nunca zero inferido.

## Classificador de trajetória
A função `analyze_trajectory` **não é Jev**: é um parser determinístico das transcrições. Exige comando concluído com código de saída, leitura real das duas skills e sequência RED/GREEN com passos de verificação, sem contar simples menções. Uma sequência de comandos shell encadeados não comprova que cada etapa teve sucesso; não proclamar Nível 4 universal sem provas isoladas de cada fase. Evidência histórica antiga permanece, porém seu boolean anterior não é aceite canônico.

## Próximos gates (Codex local / executor autorizado)
1. CI offline verde no HEAD corrigido.
2. Imagem/sandbox isolado sem acesso ao Git pai, soluções históricas, home, tokens, SSH, rede ou oráculo mutável. Canários negativos demonstram negação; configuração e hashes registrados.
3. Corrigir também possíveis brechas nas APIs de install/remove e validar o runner em Linux/Windows.
4. Repetir teste com tarefas novas, mesmo ambiente/modelo e **condições A/B/C**. Congelar antes de executar. Incluir pelo menos uma tarefa que diferencie qualidade, não só todas as condições com 100%.
5. Só depois Claude Code autenticado em ambiente seguro, com política de permissões que não use bypass.
6. Codex revisa e usuário aprova adoção; nenhum merge/instalação global decorrente de relatório.

**Status:** code review e testes offline não homologam G1/A1/B/C. Não inferir segurança ou ganho causal da execução histórica.
