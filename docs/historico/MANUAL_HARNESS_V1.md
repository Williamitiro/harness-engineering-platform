# Manual de engenharia — Harness Engineering V1

## 1. Objetivo e não objetivos

Aumentar a **qualidade verificável**, segurança e produtividade de Codex e Claude Code no desenvolvimento de software, reaproveitando suas capacidades nativas e componentes de terceiros. O sistema NÃO tenta substituir runtime, SDK, sessão, modelo, ferramentas de edição ou gestão de permissões do Codex/Claude.

**Não objetivos:** lançar framework multiagente, clonar funcionalidades de runtime, instalar 100+ skills por padrão, construir orquestrador próprio, integrar marketing/CAD/Core diretamente, tornar testes artificiais sinônimo de qualidade, garantir efeitos de prompts sem evidência.

## 2. Arquitetura mínima

```text
Developer -> Codex OU Claude Code (runtimes originais)
                  |
     instruções curtas do projeto + skills selecionadas
                  |
          ferramentas nativas e suíte real do projeto
                  |
   avaliador independente: testes/CI + logs/provas/artefatos
                  |
           revisão humana / merge governado
```

O repositório mantém somente: (a) contrato/manifesto de versões e hashes; (b) regras e documentação de compatibilidade; (c) utilitários offline; (d) testes e evidências; (e) protocolo de experimentação. Cada projeto de destino preserva seu `AGENTS.md`, `CLAUDE.md`, suites, autonomia, aprovações e fronteiras de segurança.

## 3. Pilares técnicos

| Pilar | Regra |
| --- | --- |
| Reuse-first | Inventariar nativo e upstream, comparar licença/manutenção/adaptação antes de escrever código |
| Native-first | CLI/SDK/skills oficiais de Codex e Claude Code têm precedência |
| Progressive disclosure | Descrição curta no catálogo; corpo da skill somente quando necessário |
| Verificação externa | Oráculo independente do agente avaliado; impedir autoavaliação circular |
| TDD proporcional | Regressão antes do patch em defeitos reais; evitar liturgia em alterações triviais |
| Evidência | Registrar commit, versão, comando, execução, saída, artefato e limitações |
| Segurança | Menor privilégio; backups; isolamento; secrets fora dos workspaces experimentais |
| Portabilidade | Configuração por cliente; não presumir que SKILL.md seja idêntico a plugin executável |
| Economia | Medir latência, tokens e custo, incluindo falhas e tentativas sem uso de skill |
| Governança | Não modificar produção nem outros projetos sem gate/autorização explícitos |

## 4. Componentes e decisões

**Codex:** runtime principal quando escolhido pelo operador, usando suas instruções e skills oficialmente suportadas. **Claude Code:** segundo executor nativo autorizado, aproveitando plugins e skills oficiais. **ECC (Everything Claude Code):** catálogo upstream, não dependência irrestrita. Selecionadas inicialmente apenas `tdd-workflow` e `verification-loop` para prova de lifecycle e invocação. **GStack:** candidato complementar para revisão de produto/engenharia e QA, ainda não adotado: mapear overlap antes. **Harbor:** candidato para avaliações isoladas se necessário; nenhum teste do Harbor foi executado nesta entrega.

Uso de `AGENTS.md` e `CLAUDE.md`: copiar requisitos mínimos e específicos do projeto; evitar instruções duplicadas ou conflitantes, e não pressupor que Claude leia AGENTS.md como Codex lê. Não criar agente próprio para despachar entre os dois; delegação continua via fluxo explícito existente.

## 5. Evidência e confiança

Níveis:
1. `FILE_PRESENT` — bytes presentes e SHA correto.
2. `DISCOVERED` — runtime listou a skill no escopo efetivo.
3. `INVOKED` — trajetória comprova solicitação/leitura do corpo correspondente.
4. `BEHAVIOR_OBSERVED` — procedimentos pertinentes realmente ocorreram no sandbox.
5. `OUTCOME_VERIFIED` — critérios externos passaram sem efeitos proibidos.

Cada nível exige prova adicional. Uma saída textual dizendo 'usei TDD' vale zero para inferir invocação. Uma skill que recomenda Git pode conflitar com sandbox sem Git: documentar incompatibilidade, nunca suprimir controles para forçar PASS.

## 6. Reuso disciplinado de ferramentas

Pesquisa de alternativas exige: último commit/release, abertura de issues/PRs relevantes, licença, compatibilidade Windows/Linux, operação offline, dependências, superfície de segurança, custo de integração, aderência aos critérios e experimentos reais. Estrelas só sinalizam visibilidade; não são critério de homologação. Upgrades são decisões versionadas; nunca `curl | bash` irrestrito na estação principal.

## 7. Definição de pronto

A V1 está pronta somente quando Codex e Claude Code executarem uma amostra aprovada de tarefas reais em sandbox seguro, e existir prova separada de descoberta/invocação/execução, critérios de QA objetivos, registros de custo e rollback. Quando um cliente não suportar alguma etapa, marcar `UNSUPPORTED`, não falsear `PASS`. Sem evidência runtime, estado é `PREPARED`.

Referências internas: `docs/PROTOCOLO_VALIDACAO.md`, `docs/RUNBOOK_CODEX_CLAUDE.md`, `docs/UPSTREAM_REUSE.md`.
