---
name: setup-harness
description: Preparar, verificar ou remover o pacote Harness em um repositório explicitamente escolhido, usando o CLI central e preservando regras existentes. Use quando o usuário pedir setup do Harness no projeto.
---

# Setup Harness

Leia `harness-location.json` ao lado desta skill, gerado pelo instalador pessoal.
Ele informa `harnessctl`, o checkout ECC sugerido e o cliente desta instalação.
Confira que o CLI existe; se foi movido, informe o bloqueio e peça a localização
correta, sem procurar segredos nem instalar outro runtime.

Atue somente quando o usuário pedir este setup. O diretório atual serve como
sugestão de repositório; torne o caminho explícito antes de qualquer cópia.
Não escolha outro projeto silenciosamente. Não execute ao abrir chat ou criar Git.

O pacote de projeto atual suporta **Codex**. Se o descritor indicar `claude`,
informe `BLOCKED_CLIENT_R3`: o bootstrap pessoal está preparado, mas o lifecycle
Claude depende de R3. Não aplique o pacote Codex como fallback.

Use Python e o caminho absoluto `harnessctl` do descritor para todos os comandos.
Passe argumentos separadamente ou com quoting apropriado ao terminal; não use
shell gerado a partir do conteúdo do projeto. Não copie o CLI para o projeto.

1. Em um projeto já instalado (`.harness/manifest.json` presente), execute
   `project-verify --repo CAMINHO --client codex`. Não infira sucesso pela presença
   do arquivo; se alterado, pare. Reaplicação pode usar `project-attach` após verificar.
2. Em projeto novo, execute `project-doctor` e `project-plan`, ambos com `--repo`
   explícito e `--client codex`. Mostre arquivos novos, bloqueios e conflitos.
   `BLOCKED_COLLISION` exige preservar o arquivo e apresentar a decisão necessária;
   não concatene contratos, não edite instruções existentes e não reivindique ownership.
3. Com plano aprovado para esse repositório e esses arquivos, execute
   `project-attach --repo CAMINHO --client codex --source ECC --apply`, usando o
   checkout ECC já disponível indicado no descritor ou escolhido pelo operador.
   Sem aprovação suficiente, peça autorização após apresentar o plano. Não repita
   a pergunta quando a aprovação exata já existir. Sem fonte pinada válida, pare;
   não faça clone, atualização, download ou instalação de dependências por inferência.
4. Execute `project-verify` e informe o resultado. Instalação de arquivos não prova
   descoberta, invocação, comportamento, ganho ou isolamento do agente.
5. Para remoção solicitada, mostre `project-remove --repo CAMINHO` sem `--apply`.
   Com autorização, rode o mesmo comando com `--apply`. Arquivos alterados bloqueiam;
   não os apague nem restaure bytes por cima de trabalho humano para forçar remoção.

Não configure MCP, Node, daemon, hooks, credenciais ou preferências globais.
Não execute modelos, benchmarks, push, merge ou deploy como efeito do setup.
O instalador pessoal é uma operação separada e explícita do CLI central; esta skill
não se autoatualiza nem se instala em outras máquinas. Relate sempre o cliente,
repositório, estados reais e o que ficou pendente.
