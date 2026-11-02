# Harness Engineering — JEV HTTP direto (sem Node/MCP)

Escopo: adaptar **somente o caminho J** de `scripts/paired_executor.py` para a API HTTP do OpenRouter. Preserva o Codex nativo e o preflight MXC já existentes. Não altera `.env`, Infisical, branch, worktree, tokens, conta ou configuração global.

Contrato oficial: `POST https://openrouter.ai/api/alpha/decisions`, modelo fixo `typesafe/jev-1.14`, `state` + pergunta `choice`, devolve `answers.task` com `choice`, `probabilities`, `confidence`, `usage` e `cost` quando observado.

## Instalação na worktree do PR #4

Baixe e extraia o ZIP **na raiz** `C:\dev\harness-engineering` (pasta `scripts` do ZIP deve se fundir à pasta `scripts` do projeto). **Antes, confirmar worktree sem alterações pendentes no arquivo `scripts/paired_executor.py`.**

No PowerShell, dentro da pasta do repositório:

```powershell
python scripts/apply_direct_jev.py
python -m unittest discover -s tests -p test_jev_http.py -v
```

A primeira instrução faz substituições fechadas no executor; se algo divergir do commit do PR #4, **não altera** o arquivo e retorna `PATCH_REFUSED`. A segunda executa somente 5 testes HTTP simulados, sem API, sem custo.

## Primeira chamada remota JEV (apenas uma; pode custar centavos ou fração)

```powershell
infisical run --env=dev -- python scripts/jev_http.py --one-call
```

Esse comando executa **um único** pedido de classificação público, não o benchmark. O `--one-call` é a autorização explícita. `TYPESAFE_API_KEY` só é aceito como legado caso seja de fato chave OpenRouter iniciando `sk-or-`; chave de outro provedor não é redirecionada. O resultado mostra etiqueta, confiança, tokens, custo quando observado, e código de erro sanitizado, jamais chave ou corpo bruto de resposta.

## Piloto A × J de 3 casos (somente depois do smoke HTTP)

O comando habitual do projeto permanece válido após aplicar o patch, pois `run_pilot_once.py` continua chamando `paired_executor.py`:

```powershell
python scripts/run_pilot_once.py --output "$env:TEMP\he-jev-http-pilot-3.json" --model gpt-6.1-sol
```

A saída precisa ter um nome novo, não reutilizar arquivos anteriores. `run_pilot_once.py` já envolve o executor em `infisical run --env=dev`, limite global 180s, sem retries, 3 tarefas máximo. **Essa etapa é paga** e continua opcional, separada da primeira chamada única.

## Restrições e verificação

- Não executa Node, MCP, WSL ou downloader na classificação J.
- Segredo do OpenRouter somente no supervisor Python; nenhum envio ao sandbox Codex; proxy de ambiente desativado e redirecionamentos HTTP proibidos.
- Sem retry automático. Erros de HTTP/status JSON retornam códigos seguros.
- Confiança para roteamento usa **probabilidade da categoria vencedora**, com política `>=0.85` e margem `>=0.50`; confiança fornecida pelo modelo é guardada separadamente.
- Custo/tokens `null` quando não retornados pelo provedor.
- Não declara G1 independentemente homologado nem valida performance do JEV sem piloto real.

**Estado desta entrega:** arquivos e testes construídos e executados em ambiente local isolado; **não publicados diretamente como commit no GitHub**. Atualize o PR #4 com estas alterações depois de confirmar o funcionamento, sem merge automático. O repositório remoto continua sem o adaptador completo até esse push.
