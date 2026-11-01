# Harness Engineering V0.1 — revisão da auditoria e A0

Data: 2026-11-01. Escopo executado: ciclo de arquivos offline. A1 e benchmark B não executados.

## Parecer sobre os cinco apontamentos

| Apontamento | Verificação e tratamento |
| --- | --- |
| Dependência do TDD | Confirmado. A descrição anterior de independência era incompleta. O passo 0 manda executar `scripts/setup-package-manager.js --detect`. A cadeia local de imports é `setup-package-manager.js` → `lib/package-manager.js` → `lib/utils.js` → `lib/agent-data-home.js` → `lib/path-safety.js`. Todos foram conferidos contra o commit fixado e preparados fora da árvore de descoberta. Nenhum foi executado. |
| Diretório de carregamento | Correção pertinente para A1. O `Set-Location` anterior pertencia ao comando de cópia, não era uma instrução de lançamento do Claude; faltava o contrato explícito de lançamento. Config directory não define CWD e cópia não prova descoberta. |
| Commits versus TDD | O conflito já havia sido identificado; faltava enforcement. Texto de política e allowlist de ferramenta não substituem isolamento do SO. A0 verifica apenas ausência de metadados locais e uma sondagem de descoberta Git limitada por ambiente; não homologa contenção. |
| A/B combinado | Confirmado como limitação de atribuição, não como invalidação da triagem. Medir pacote TDD + verificação versus A; posteriormente testar TDD isolado e verificação isolada, com protocolo e orçamento próprios. |
| Orçamento | Confirmado. US$ 60 é planejamento, não limite financeiro independente demonstrado. B permanece bloqueado. |

## Componentes e dependências

ECC 2.2.3: `b38be6a7f6350964d59328b52f0624e1d1d552d1`.

Skills selecionadas, sem alteração:

- `skills/tdd-workflow/SKILL.md`: `b6a8dd3e5215641cd9c33a46eae1d2b87508a07bc451e2c2fe25591f33a6b519`.
- `skills/verification-loop/SKILL.md`: `9ee288d426660b0c785f534a003a4960fb4d8083a21302d8a4fd9b035b2edbb1`.

Dependências originais preparadas em `.poc/a0-20261101/ecc-support/`:

- Os cinco JS da cadeia acima, em sua disposição original.
- `scripts/package.json`, copiado de `manifests/install-assets/commonjs-scripts-package.json`, para manter CommonJS.
- A licença MIT upstream.

O `CLAUDE_PLUGIN_ROOT` futuro apontará exclusivamente para esse suporte revisado. Isso resolve a referência textual do helper sem expor o checkout completo como diretório de skills. Não instala plugin, hook, servidor MCP, memória ou aprendizado contínuo.

O helper depende de Node e de utilitários de descoberta de comandos (`where.exe`/`which`); seu ramo `--detect` consulta preferências e disponibilidade. Os ramos `--global` e `--project` escrevem configuração e não estão aprovados. O runtime do helper permanece pendente de teste. Nenhum pacote npm foi instalado.

As demais dependências são condicionais à tarefa: runner e gerenciador existentes, compilador, lint e cobertura. Os exemplos incluem npm/pnpm/yarn/Bun, Jest/Vitest, Playwright, pyright e ruff; não constituem autorização para instalar todas essas ferramentas. A referência `bun-runtime` é complementar ao caminho Bun e não foi incluída: as fixtures propostas são TypeScript/Node. Se um caminho escolhido exigir outra skill, registrar dependência ausente e bloquear esse caminho.

`verification-loop` usa também Git e utilitários POSIX (`tail`, `sed`, `grep`). Seu scan por padrões não equivale a auditoria de segurança. O limiar genérico de 80% não substitui critérios funcionais nem justifica novas dependências. Lint/E2E não aplicáveis devem ser identificados, não apresentados como PASS.

## A0 executado

Evidência completa: [A0_2026-11-01.json](evidence/A0_2026-11-01.json).

Foram usadas operações da biblioteca padrão Python de cópia exclusiva, SHA-256, inventário e movimentação. Nenhum instalador, framework, adaptador ou código do ECC foi implementado/modificado. O procedimento foi executado pelo terminal; não foi criado um instalador próprio.

| Critério | Resultado | Limite |
| --- | --- | --- |
| Identidade upstream | PASS | Nove arquivos confrontados com bytes do commit remoto fixado |
| Backup inicial | PASS | Cópia e inventário dos arquivos sentinela; configurações pessoais só tiveram hashes lidos |
| Instalação seletiva | PASS | Exatamente dois SKILL.md adicionados ao projeto controlado |
| Integridade das skills | PASS | Hash completo instalado igual ao upstream |
| Colisão | PASS | Cópia para destino já existente recusada, sem alteração do inventário |
| Arquivos preexistentes | PASS | Skill sentinela, settings sentinela e arquivo de projeto preservados |
| Dependências | PASS estrutural | Cinco JS, fronteira CommonJS e licença disponíveis; execução não testada |
| Preparação de atualização | PASS limitado | Staging da mesma versão; atualização entre releases NÃO TESTADA |
| Desativação | PASS estrutural | Duas skills movidas para fora da descoberta; unload em sessão não testado |
| Reativação e rollback | PASS estrutural | Bytes restaurados a partir da versão preservada |
| Remoção | PASS | Só componentes do experimento movidos para quarentena |
| Restauração final | PASS | Inventário final idêntico ao inicial e ao backup |
| Configurações pessoais | PASS | Quatro hashes antes/depois idênticos; nenhum conteúdo pessoal publicado |
| Descoberta Git | PASS limitado | Fixture sem `.git`; `rev-parse` falhou com ceiling no subprocesso. Não prova isolamento de agente |

Total: 25 asserções PASS, zero FAIL, incluindo verificações individuais de hash. Inventários de cada fase, dependências e hashes pessoais completos constam no JSON. Backups e cópias experimentais ficam em `.poc/`, ignorado pelo Git. O projeto final contém somente os três arquivos sentinela iniciais; as skills permanecem preservadas em `disabled/` e `quarantine/` fora da descoberta.

Não houve remoção recursiva, execução de Claude com prompt, chamada LLM, instalação de Harbor ou mudança em projeto de produção.

## Contrato corrigido para A1 — ainda não executado

1. Em sandbox homologado, usar workspace standalone `/app/task`, sem `.git`, remotes, solução histórica ou ancestrais de outro repositório. A estação Windows pode fazer inspeção offline; não será usada como sandbox por ter pasta separada.
2. `CLAUDE_CONFIG_DIR=/runtime/claude` exclusivo de cada tentativa; `CLAUDE_PLUGIN_ROOT=/runtime/ecc-support`; `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`; background tasks desligadas. Nenhuma variável global da estação será alterada.
3. Carregar apenas os dois diretórios originais via `agents[].skills` do Harbor. A instalação manual de A0 serviu para testar o ciclo de arquivos, não substitui a prova de carregamento do Harbor.
4. Se o teste for nativo Windows no futuro, lançar o Claude a partir do diretório experimental que contém `.claude/skills`, com config directory separado. Se o CWD for outro, declarar `--add-dir` explicitamente. Não iniciar a partir da raiz e presumir descoberta de descendentes.
5. Usar somente fontes de configuração revisadas e MCP estrito com conjunto vazio; não montar home, keychain, socket Docker, SSH, repositório do operador ou plugins pessoais. Registrar políticas gerenciadas efetivas. Não usar `--bare` como única garantia na versão 2.1.268.
6. Obter evidência da lista efetiva de skills (quando exposta pela interface) e da invocação/leitura de cada corpo fixado na trajetória. Uma declaração na resposta final não serve. Distinguir carregamento, invocação e execução dos verificadores; uma leitura do Markdown sozinha não comprova adesão.
7. Executar o helper apenas após revisar a cadeia preparada, com configurações experimentais explícitas. Testes de negócio executam sem rede e não instalam ferramentas.

## Enforcement externo ao modelo — gate para A1/B

O agente nunca terá acesso aos metadados Git do publicador ou a credenciais de publicação. Fonte será exportada para volume descartável. A imagem mínima não disponibilizará executável Git ao agente; diffs e versões serão calculados externamente pelo avaliador. Git e Python na estação do avaliador não pertencem ao ambiente do agente. Nenhuma escrita de Git dentro da fixture conta como checkpoint; artefatos contendo `.git` serão recusados pelo avaliador. A skill que pedir `git diff` terá essa etapa marcada como não executada pelo agente e substituída pela verificação externa, limitação explícita do pacote sob a política do experimento.

Antes de qualquer tentativa, provar com canários no sandbox: impossibilidade de atingir metadados protegidos, ausência de Git, bloqueio da rede de publicação e rejeição de artefatos contendo metadados Git. Aplicar a mesma política em A e B. A sondagem offline do A0 não satisfaz esse gate. Se o backend não impuser a fronteira, não executar o experimento. Não há proposta de desenvolver um gateway ou controlador próprio.

## Método e orçamento corrigidos

O A/B inicial mede o PACOTE combinado sob essas restrições. Registrar dois resultados: efeito da atribuição A/B (todas as tentativas) e análise descritiva de uso observado. Não descartar tentativas sem invocação para melhorar o score. Sem ganho mensurável ou com intervalos largos, concluir inconclusivo. Ablações futuras testarão A/TDD/verificação/pacote em tarefas de confirmação; não ampliar automaticamente a campanha.

As quatro tarefas históricas anteriormente identificadas permanecem candidatas. Fixtures, dependências, oráculo e testes ocultos ainda não foram calibrados. Exigir base defeituosa falhando e referência aprovada antes de rodar modelos. Duas tarefas de roteamento correlacionadas não são observações independentes.

US$ 60 permanece teto de PLANEJAMENTO. Antes de B: conta/chave dedicadas; confirmar eventual limite ou saldo financeiro imposto pelo provedor; reserva separada de sandbox com expiração e recursos limitados; serialização, orçamento reservado antes de iniciar cada tentativa e reconciliação de chamadas em voo. `--max-budget-usd` é defesa complementar e pode exceder o valor pela última chamada; não prova corte agregado. Sem controle independente verificado e aprovação financeira, B continua bloqueado. Autenticação não autoriza gasto.

## Impedimentos

- A última consulta em 2026-11-01 retornou Claude não autenticado; não houve login nesta execução.
- Docker, Podman e Harbor não foram encontrados no PATH consultado; nenhum sandbox alternativo foi homologado.
- Não há cutoff financeiro independente demonstrado.
- Descoberta/invocação, helper em runtime, contenção de SO e atualização entre releases permanecem NÃO TESTADOS.
- A0 aprovou o ciclo offline de arquivos; não aprovou o funcionamento integral das skills ou o piloto pago.

## Fontes primárias

- [TDD fixado](https://github.com/affaan-m/ECC/blob/b38be6a7f6350964d59328b52f0624e1d1d552d1/skills/tdd-workflow/SKILL.md).
- [Verification fixado](https://github.com/affaan-m/ECC/blob/b38be6a7f6350964d59328b52f0624e1d1d552d1/skills/verification-loop/SKILL.md).
- [Helper fixado](https://github.com/affaan-m/ECC/blob/b38be6a7f6350964d59328b52f0624e1d1d552d1/scripts/setup-package-manager.js).
- [Descoberta de skills Claude](https://code.claude.com/docs/en/skills).
- [Configuração Claude](https://code.claude.com/docs/en/settings).
- [Skills Harbor](https://docs.harborframework.com/jobs/skills).
- [Configuração e dry-run Harbor](https://docs.harborframework.com/jobs/configs).
