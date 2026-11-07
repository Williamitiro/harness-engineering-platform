# Ordem de serviço — deixar a suíte global da plataforma verde

> Copie este documento inteiro para uma thread nova no ambiente `plataforma-metalurgica`.
> Preparado em 03/11/2026 a partir de leitura somente-leitura do `main` (`31e4c26`).

## Objetivo

A suíte completa (`pytest`) tem **2 falhas que não vêm de código de produto**. Corrigir as duas
num PR pequeno e próprio, sem misturar com outras frentes (#215, #216, #217, #218, #219).

## Falha 1 — CRLF em evidências históricas

- Teste: `tests/test_quebra_de_linha.py::test_texto_versionado_sem_crlf`
- Estado: **falha no próprio `main`**, independente de qualquer PR.
- Causa: 36 arquivos de texto com CRLF no índice do Git, **todos** dentro de
  `evidence/2026-11-01_auditoria_adversarial_cad/` (30 `.json`, 4 `.csv`, 2 `.py`).
- Origem: commits de 01/11/2026 `d183965`, `1826bd7`, `fac4b78` (auditoria adversarial CAD / rodada Antigravity).
- Conferência: `git ls-files --eol | findstr "i/crlf"`.

**Decisão: não converter os arquivos.** São evidência histórica e a pasta tem recibos com SHA-256
(`AMBIENTE.json`, `AUDITORIA_EXECUTIVA.md`, `BACKGROUND_RECUPERADO.json`, …). Converter para LF
muda os bytes e pode invalidar esses recibos. Isso segue a regra que o próprio teste já usa
(“ficam como estão para não reescrever o arquivo inteiro”).

**O que fazer:**

1. Antes de editar, confirmar se algum recibo da pasta registra hash dos 36 arquivos. Registrar
   o resultado no PR (ele só reforça a decisão; não muda o caminho).
2. Em `tests/test_quebra_de_linha.py`, acrescentar uma exceção **por prefixo de pasta**, separada de
   `CRLF_EXISTENTES` (que é por arquivo e é usada também por `test_excecao_crlf_nao_e_regravada_inteira`).
   Exemplo de intenção, não de código final:
   - nova constante `PASTAS_CRLF_HISTORICAS = ('evidence/2026-11-01_auditoria_adversarial_cad/',)`;
   - `test_texto_versionado_sem_crlf` pula arquivos cujo caminho comece por um desses prefixos;
   - comentário com data, motivo e commits de origem, no mesmo estilo dos comentários existentes.
3. **Não** afrouxar a regra para pastas novas: arquivo novo fora desse prefixo continua tendo que ser LF.
4. Opcional, só se o dono aprovar: em `.gitattributes`, `evidence/2026-11-01_auditoria_adversarial_cad/** -text`
   para o Git não tentar normalizar esses arquivos no futuro. Não é necessário para o teste passar.

**Teste do próprio ajuste (obrigatório):**
- arquivo novo com CRLF **fora** do prefixo continua fazendo o teste falhar (controle negativo, em fixture ou checagem manual descrita no PR);
- os 36 arquivos continuam byte a byte iguais ao `main` (`git diff --stat main -- evidence/2026-11-01_auditoria_adversarial_cad` vazio).

## Falha 2 — pasta temporária dentro de um checkout Git

- Teste: `test_fechamento_ra1.py::test_relatorio_nao_e_gravado_dentro_do_git`
- Causa: a suíte foi executada com a pasta temporária do pytest dentro de um repositório Git
  (o checkout do Harness). A guarda de privacidade recusou a escrita, **corretamente**.
- Não é bug de produto. Fora de um Git, o teste passa.

**O que fazer:** não mudar o teste. Documentar a forma correta de rodar a suíte completa, por exemplo
`python -m pytest --basetemp=%TEMP%\pytest-plataforma` (pasta fora de qualquer repositório), no
lugar onde a plataforma documenta comandos de teste. Se o `pytest.ini`/`pyproject` já define
`basetemp`, conferir que ele aponta para fora do Git.

## Critério de pronto

- `python -m pytest` completo, com `--basetemp` fora do Git: **0 falhas** (skips continuam permitidos).
- Diff limitado a `tests/test_quebra_de_linha.py`, à documentação de como rodar a suíte e,
  se aprovado, ao `.gitattributes`.
- Nenhum arquivo de `evidence/` alterado.
- PR próprio, em Draft, seguindo as regras do `AGENTS.md` da plataforma (cópia isolada, nada direto na `main`).
- Depois do merge deste PR, o PR #216 (NaN/infinito no CLI de nesting) pode ser revalidado com a suíte completa.

## Fora do escopo

Converter evidências, mexer em outros testes, tocar nos PRs abertos, instalar o Harness na plataforma.
