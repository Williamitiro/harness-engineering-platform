# Guia de Integração Oficial do Jev via `jev-code` (MCP Consultivo)

**Upstream Canônico:** [`FrancoisChastel/jev-code`](https://github.com/FrancoisChastel/jev-code)  
**Versão Pinada:** `v0.5.0` (08/10/2026)  
**Commit SHA:** `74a4569bfe8bb4ad0cc1ba74fa5867f09e267300`  
**Licença:** MIT  
**Runtimes Suportados:** Codex e Claude Code  
**Modo de Operação:** Consultivo via MCP stdio (sem proxy, sem autoridade executiva)

---

## 1. Princípios de Segurança e Não Invasão

O instalador padrão do `jev-code` (`npx @french-castle/jev-code setup`) tenta por padrão gravar configurações na pasta de perfil do usuário (`~/.claude/` ou `~/.agents/`) e copiar chaves de API para os arquivos de configuração do agente.

**Controles Obrigatórios:**
1. **Nunca instalar globalmente:** Proibido rodar `npm install -g` ou `setup` no perfil do operador.
2. **Flag `--no-env`:** Impede a cópia e persistência de credenciais em disco.
3. **Flag `--project`:** Restringe as definições de MCP ao diretório do projeto ou sandbox descartável.
4. **Flag `--dry-run`:** Usada previamente para auditoria do plano de execução do instalador.
5. **Comunicação por stdio:** Não abrir portas de rede locais (como proxies na porta 8080).

---

## 2. Configuração em Ambiente Descartável

### Configuração do Servidor MCP para Codex / Claude Code
O arquivo template está disponibilizado em [`config/mcp/jev_code_mcp_template.json`](../config/mcp/jev_code_mcp_template.json).

Em um container descartável com isolamento homologado:
```json
{
  "mcpServers": {
    "jev": {
      "command": "npx",
      "args": ["-y", "@french-castle/jev-code@0.5.0", "mcp"],
      "env": {
        "TYPESAFE_API_KEY": "${TYPESAFE_API_KEY}"
      }
    }
  }
}
```

### Invocação de Verificação em Modo Dry-Run
```bash
# Inspecionar o que o setup faria sem aplicar alterações em disco:
npx -y @french-castle/jev-code@0.5.0 setup codex --project --dry-run --no-env
```

---

## 3. Ferramentas Fornecidas pelo `jev-code`

O servidor expõe 5 ferramentas tipadas que o modelo pode consultar:
- `jev_classify`: Classificação entre opções pré-definidas com probabilidades calibradas.
- `jev_check`: Verificação booleana (Noul) com probabilidade de confirmação.
- `jev_score`: Pontuação contra rubric ordinal.
- `jev_rank`: Ordenação de candidatos por relevância.
- `jev_ask`: Resposta estruturada a pergunta delimitada com evidências.

A política do Harness (`config/jev_*_policy.json`) atua como filtro após a resposta da tool:
- Se `confidence >= 0.85` e `margin >= 0.50` e `choice != "uncertain"`: recomendação aceita.
- Caso contrário: abstenção segura e fallback imediato para o raciocínio nativo do agente.
