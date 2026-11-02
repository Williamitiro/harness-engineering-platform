# MANIFESTO EXPERIMENTAL — MISSÃO HE-AG-001

## 1. Identificação do Experimento
- **Missão:** HE-AG-001 (Comprovação Experimental do Harness Engineering no Antigravity)
- **Data de referência:** 2026-11-01
- **Repositório:** `C:\dev\harness-engineering`
- **Branch:** `codex/poc-a0-offline` (Head: `8bdf30a`)
- **Diretório isolado do experimento:** `C:\dev\harness-engineering\.poc\antigravity-flash-001\`

## 2. Ambiente de Execução e Versões
- **Sistema Operacional:** Windows 10/11 (win32, x86_64)
- **Interface de Execução do Agente:** Google Antigravity CLI (`agy.exe`) versão `1.4.10`
- **Modelo Avaliado:** Gemini 3.8 Flash (`gemini-3.8-flash-low`)
- **Nível de Esforço:** `low` (fixado em todas as 9 execuções)
- **Runtime Python:** Python 3.12.10
- **Runner de Teste:** pytest 9.1.1 (pluggy 1.7.0)
- **Runtime Node.js:** Node.js v24.19.0 / npm 11.17.0 (npm.cmd)
- **Gerenciador uv:** uv 0.13.5
- **Git:** git version 2.54.0.windows.1

## 3. Hashes Criptográficos dos Componentes Pinned

### 3.1 Skills Upstream do ECC
- **Origem:** ECC 2.2.3 (Commit `b38be6a7f6350964d59328b52f0624e1d1d552d1`)
- `tdd-workflow/SKILL.md`: `B6A8DD3E5215641CD9C33A46EAE1D2B87508A07BC451E2C2FE25591F33A6B519`
- `verification-loop/SKILL.md`: `9EE288D426660B0C785F534A003A4960FB4D8083A21302D8A4FD9B035B2EDBB1`
- `setup-package-manager.js`: `499F38EF03B3F7F9896AD97229B8213DF215544BB3C6BD6343E3889F023F6BDA`

### 3.2 Regras Enxutas do Experimento
- `harness_assets/AGENTS.md`: `B91172A4CEF602156EB7722C9B101DCB787075CCCCFAC729580D262729D4E53D`

### 3.3 Templates Pristinos das Tarefas (Estado Inicial)
- **T1 (Bug Fix - SemVer Parser):**
  - `src/semver_parser.py`: `1F431B1FB2A426EC77A0E7061CFF531A4CFB5D9F6B5E3D8ED69C4D12AB9319ED`
  - `tests/test_initial.py`: `1046641769764B52BF27A1010B104C9935237F84AD96892A4CF1F978B406B874`
- **T2 (Feature - Circuit Breaker):**
  - `src/circuit_breaker.py`: `977FF96A197BC5F03B488AEA086A935C223CA4A10AF8B2F58AD94BD07126082B`
  - `tests/test_initial.py`: `AAE6EA8B461200E96A08BE2397E314ED59931BA8D92AB618F1BAAE30AEC91504`
- **T3 (Refactoring - Order Calculator):**
  - `src/order_calculator.py`: `6CC510404652A0B11C8395D28C7D767DD19861E7FE0B50A708A4DA141A3C3504`
  - `tests/test_initial.py`: `188D98B4465D4E6ECAD18AAF86BDA3D02E7634329747EA58EED94831545CC254`

### 3.4 Oráculos de Aceitação Independentes (Protegidos)
- `oracle/test_t1_acceptance.py`: `34A01013854187B3F5A0FE3349BE3AA9B5A84D97C636DC37E00706B6883D1011`
- `oracle/test_t2_acceptance.py`: `286611A70007913D222DFBD70786DABDB4614D43A94B0F088AC08DC94E5AEE48`
- `oracle/test_t3_acceptance.py`: `CC5793A90AEE390D5D329DF81F0A5A8E10F548E1F686E8C36FB911832439135C`

## 4. Procedimento de Repetição e Execução
1. Clonar ou posicionar no repositório `C:\dev\harness-engineering`.
2. Assegurar que Python 3.12+ com `pytest` e Antigravity CLI (`agy.exe`) estejam disponíveis no PATH.
3. Executar o orquestrador automatizado:
   ```powershell
   python C:\dev\harness-engineering\.poc\antigravity-flash-001\run_experiments.py
   ```
4. O script executa as 9 rodadas sequenciais na ordem fixa:
   - T1: Condição A -> Condição B -> Condição C
   - T2: Condição A -> Condição B -> Condição C
   - T3: Condição A -> Condição B -> Condição C
5. Em cada rodada:
   - O workspace é recriado a partir do template pristino.
   - A condição experimental (A: puro, B: com `AGENTS.md`, C: com `AGENTS.md` + `.agents/skills`) é montada.
   - O agente Antigravity executa o prompt congelado em sessão isolada e não interativa.
   - A telemetria real (tokens, duração, status) e transcrições são copiadas para `EVIDENCIAS/<run_id>/`.
   - A suite de aceitação independente do oráculo é executada e registrada.
   - O diff de código é calculado e arquivado.
   - O arquivo `RESULTADOS.csv` é gerado/atualizado.

## 5. Limitações Conhecidas e Declarações de Escopo
1. **Incompatibilidade das Skills Upstream:**
   As skills do ECC (`tdd-workflow` e `verification-loop`) foram escritas originalmente para Claude Code em ambiente POSIX (bash). Elas instruem a execução de comandos como `set -o pipefail`, `tail -20`, `sed -n '1,30p'`, e utilizam variáveis como `$CLAUDE_PLUGIN_ROOT`. No Antigravity sob Windows, esses comandos não são suportados nativamente pelo shell padrão (PowerShell). Além disso, as diretrizes de git commits colidem com o isolamento de metadados Git do experimento.
2. **Não Ativação Autônoma das Skills:**
   O modelo Gemini 3.8 Flash não invocou nem leu as skills do ECC nas tarefas testadas. As tarefas foram resolvidas diretamente pelas ferramentas nativas do Antigravity (`read_file`, `write_file`, `edit_file`, `run_command` executando `python -m pytest`).
3. **Escopo Estatístico:**
   Trata-se de um piloto inicial controlado com 9 execuções (1 por condição por tarefa). Embora forneça evidência objetiva e reproduzível das 9 execuções locais, não constitui prova estatística multiamostral de superioridade universal.
