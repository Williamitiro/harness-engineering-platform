# Runbook — instalação e reversão em sandbox

## Segurança antes de iniciar

1. Git limpo e branch correta; observar políticas e segredos da estação.
2. Clonar ECC no commit pinado (nunca atualizar implicitamente). Inspecionar dependências da skill e escopo de plugins/hook/MCP **antes** de chamar runtime.
3. Criar diretório descartável sob `.poc/`, sem `.git` e sem segredos. Não usar checkout real como cobaia.
4. Preparar isolamento verdadeiro do runtime e custos controlados. `harnessctl.py` sozinho NÃO isola LLM/processo/rede.
5. Jamais compartilhar configuração pessoal, tokens, SSH agent, Docker socket ou home nos mounts de avaliação.

## Exemplo PowerShell (estação Windows)

```powershell
git clone https://github.com/affaan-m/ECC.git .poc/ecc-pinned
git -C .poc/ecc-pinned checkout --detach b38be6a7f6350964d59328b52f0624e1d1d552d1
New-Item -ItemType Directory -Force .poc/a1-codex | Out-Null
python scripts/harnessctl.py plan --source .poc/ecc-pinned --target .poc/a1-codex --adapter codex
python scripts/harnessctl.py install --source .poc/ecc-pinned --target .poc/a1-codex --adapter codex --apply
python scripts/harnessctl.py verify --target .poc/a1-codex
# Reverter exatamente os arquivos próprios sem sobrescrever configurações:
python scripts/harnessctl.py remove --target .poc/a1-codex --apply
```

A instalação acima copia APENAS SKILL.md de cada skill. Alguns fluxos, como TDD, referenciam helpers JS; isso não prova que a skill funcione. O A0 estudou `scripts/setup-package-manager.js` e seus imports. A1 deve verificar e disponibilizar dependências do modo nativo oficial, sem suplantar as garantias do sandbox. Se ausentes, a execução é bloqueada. Nenhuma cópia de helpers foi implementada automaticamente nesta versão.

Para Claude, criar `.poc/a1-claude` e usar `--adapter claude`. **A localização de instalação aqui é preparatória:** verificar na versão instalada do Claude Code se o CWD e o escopo de descoberta correspondem ao diretório experimental; `CLAUDE_CONFIG_DIR` não substitui CWD. Não modificar diretórios globais.

## Regras para execução no runtime

- Criar tarefa e oráculo congelados pelo avaliador, separadamente do agente.
- Usar o runner nativo com política de aprovações/limites e observabilidade.
- Guardar saída bruta e metadados: versão CLI, modelo, esforço, timeouts, commit inicial, hashes, permissão efetiva, lista de skills e transcrição sanitizada.
- Confirmar se a skill foi descoberta; depois se foi invocada; depois se os passos exigidos foram observados; finalmente medir o resultado externo.
- Desligar memória/plugins globais no sandbox conforme documentação da versão; revisar políticas gerenciadas e conectividade efetiva.
- Sem acesso a Git de publicação, rede ou secrets, exceto quando a tarefa aprovada justificar e a proteção externa for verificada.
- O operador deve aprovar qualquer chamada que gere custo, escrita externa, merge, publicação ou deploy.

## Como depurar

`hash mismatch`: restaurar checkout no commit aprovado, investigar modificações. `collision`: preservar arquivos existentes, não usar force. `managed file modified`: verificar diff manualmente, não remover silenciosamente. `NOT_RUN`: não é PASS; coletar prova real ou registrar bloqueio. `skill not invoked`: testar demanda explícita e catálogo de skills dentro de protocolo separado, não alterar o relato do mesmo experimento após resultado.

## Retorno ao Codex

Após executar localmente, registrar no PR: versão, SHA, comandos e exit, evidências suficientes, confs pessoais preservadas, testes com resultado e casos não executados. Não fazer merge/deploy até revisão.
