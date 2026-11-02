# Relatório de Auditoria de Isolamento e Estado do Gate G1

**Data:** 2026-11-02  
**Ambiente Auditado:** Host Windows local (`C:\dev\harness-engineering`)  
**Status do Gate G1:** **NÃO HOMOLOGADO (`PENDING_HOMOLOGATION`)**  
**Classificação de Execução Live:** **`NOT_RUN` / `BLOCKED_G1`**

---

## 1. Auditoria do Ambiente Host Atual

Foi realizada uma análise dos mecanismos de contenção disponíveis no host operacional Windows:

### 1.1 Superfície de Acesso ao Sistema de Arquivos
- **Exposição de Credenciais Pessoais:** Qualquer processo executado no host sob o usuário `itiro` possui acesso irrestrito de leitura a:
  - Chaves privadas SSH: `C:\Users\itiro\.ssh\`
  - Credenciais de nuvem: `C:\Users\itiro\.aws\`, `C:\Users\itiro\.azure\`, gcloud tokens
  - Configurações de Git e autenticação: `C:\Users\itiro\.gitconfig`, Windows Credential Manager
  - Sessões de IA e tokens: `C:\Users\itiro\.gemini\`, AppData de editores
- **Repositórios Pai e Vizinhos:** O diretório de trabalho `C:\dev\harness-engineering` é adjacente a outros repositórios em `C:\dev\`. Sem sandbox em nível de kernel, um agente pode ler ou modificar arquivos fora da árvore da tarefa.

### 1.2 Superfície de Rede
- Os processos locais possuem saída irrestrita para a internet e para a rede local (LAN).
- Não há regras ativas de filtragem de tráfego de saída (egress firewall) que restrinjam conexões exclusivamente a endpoints homologados.

### 1.3 Verificação de Ferramentas de Container
- `docker`: Não encontrado no `PATH`.
- `podman`: Não encontrado no `PATH`.
- `wsl.exe`: Presente, com distribuição `Ubuntu` (versão 2) em estado `Stopped`. No entanto, o WSL2 por padrão monta a raiz do Windows em `/mnt/c/`, vazando todo o diretório `C:\Users\itiro\` para dentro da VM Linux, a menos que `/etc/wsl.conf` desative expressamente o automount.

---

## 2. Por que Canários Locais Não Comprovam Isolamento

No histórico anterior do projeto (auditoria `docs/AUDITORIA_CORRECOES_2026-11-02.md`), demonstrou-se que:
- Criar uma subpasta `.poc/` e verificar se um arquivo "canário" permaneceu intacto **não comprova contenção**.
- O agente pode perfeitamente ler chaves do host, executar comandos de rede e inspecionar commits sem tocar no canário.
- **Portanto, o Gate G1 só é considerado HOMOLOGADO quando o isolamento é fornecido pelo sistema operacional, container ou hypervisor externo, com falhas de acesso ativamente comprovadas.**

---

## 3. Especificação para Homologação Futura do Gate G1

Para que o operador ou o Codex possam autorizar a homologação do Gate G1 no futuro, o ambiente deverá atender aos seguintes requisitos obrigatórios:

1. **Execução em Container Descartável (Rootless Docker/Podman ou VM Isolada):**
   - Imagem base minimalista (ex.: `alpine:latest` ou `node:20-slim`).
   - Apenas o diretório da tarefa montado em `/workspace`.
   - Nenhuma montagem do sistema de arquivos do host (`$HOME`, `/mnt/c`, etc.).
2. **Bateria de Canários Negativos (Negative Probes):**
   - O executor deve tentar acessar `/root/.ssh`, `~/.aws/credentials`, `~/.gitconfig` e receber obrigatoriamente `FileNotFoundError` ou `PermissionDenied`.
   - O executor deve tentar acessar diretórios fora de `/workspace` e receber `PermissionDenied`.
   - O executor deve tentar conectar a IPs internos não autorizados e receber `NetworkUnreachable`.
3. **Credenciais Temporárias e Voláteis:**
   - Chave de API injetada estritamente como variável de ambiente em memória dentro do container.
   - Destruição completa do container e da memória após o encerramento do benchmark.
4. **Sem Bypass de Permissões:**
   - Proibição absoluta de `--dangerously-skip-permissions`.

---

## 4. Conclusão e Decisão de Bloqueio

Como o host atual não atende aos requisitos de contenção externa do Gate G1:
- **Nenhuma execução live de agente ou chamada a API externa com tráfego real foi realizada.**
- Todos os componentes foram entregues preparados para operação offline, com pipeline de coleta simulada (`SYNTHETIC`) devidamente demarcada.
- O avanço para a fase empírica live requer aprovação expressa do operador e o provisionamento do ambiente isolado acima especificado.
