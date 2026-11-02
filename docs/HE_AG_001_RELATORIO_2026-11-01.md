# RELATÓRIO EXECUTIVO — MISSÃO HE-AG-001
**Avaliação Experimental do Harness Engineering no Google Antigravity**

- **Data de referência:** 2026-11-01
- **Ambiente:** Google Antigravity CLI (`agy.exe` 1.4.10)
- **Modelo:** Gemini 3.8 Flash (`gemini-3.8-flash-low`), esforço `low`
- **Repositório:** `C:\dev\harness-engineering`
- **Branch:** `codex/poc-a0-offline` (Head: `8bdf30a`)
- **Diretório de evidências:** `C:\dev\harness-engineering\.poc\antigravity-flash-001\`

---

## 1. OBJETIVO E CONFIGURAÇÃO EFETIVA

Demonstrar por execução real e evidências objetivas se um Harness Engineering enxuto melhora o desempenho do Gemini 3.8 Flash no Google Antigravity.

### Condições Comparadas
- **Condição A (Baseline Nativo):** Gemini 3.8 Flash puro no Antigravity, sem `AGENTS.md` e sem skills adicionais no workspace.
- **Condição B (Contexto Mínimo):** Mesmo ambiente da Condição A, adicionando exclusivamente o arquivo de regras enxuto `AGENTS.md` (inspecionar antes de modificar, reutilizar código, cumprir requisitos, rodar testes, não afirmar sucesso sem verificação). Sem skills.
- **Condição C (Contexto + Skills):** Mesma configuração da Condição B, adicionando as duas skills do ECC fixadas (`tdd-workflow` e `verification-loop`) em `.agents/skills/`.

### Matriz de Tarefas
- **T1 — Correção de Bug:** `semver_parser.py` (defeito de inversão e ordenação de pré-releases SemVer 2.0.0).
- **T2 — Implementação de Feature:** `circuit_breaker.py` (máquina de estados CLOSED, OPEN, HALF_OPEN com timeout e mock clock).
- **T3 — Refatoração Controlada:** `order_calculator.py` (decomposição de função monolítica em classes modulares `DiscountPolicy`, `TaxCalculator`, `ShippingCalculator` preservando 100% de compatibilidade regressiva).

---

## 2. STATUS FINAL E VEREDITO

**VEREDITO: PARCIAL**

1. **Gemini 3.8 Flash Nativo (Condição A):** COMPROVADO. Obteve 100% de aprovação funcional em todas as três tarefas (T1, T2, T3) sem necessidade de regras ou skills adicionais.
2. **Contexto Mínimo (Condição B — `AGENTS.md`):** COMPROVADO com GANHO PRELIMINAR em tarefas construtivas. Nas tarefas de implementação (T2) e refatoração (T3), reduziu o número de chamadas de ferramenta e o consumo de tokens em relação ao baseline nativo. Em T1 (bug simples), gerou overhead de latência e tokens.
3. **Skills ECC (`tdd-workflow` e `verification-loop` — Condição C):** NÃO COMPROVADO / SEM GANHO OBSERVADO. As skills foram descobertas na estrutura de arquivos, mas **NÃO foram invocadas nem executadas** pelo agente em nenhuma das rodadas. A presença das skills gerou overhead de contexto sem produzir qualquer ganho funcional incremental sobre a Condição B. Além disso, as skills possuem dependências POSIX (`tail`, `sed`, `set -o pipefail`, bash) incompatíveis com o shell nativo do Windows.

---

## 3. MATRIZ DE RESULTADOS (A / B / C)

Todos os dados abaixo são extraídos diretamente da telemetria da CLI do Antigravity e dos oráculos independentes de teste (`RESULTADOS.csv`).

| Run ID | Tarefa | Condição | Testes Aceitos | Testes Passados | Sucesso | Duração (s) | Tokens Input | Tokens Output | Tokens Total | Tool Calls | Skills Invoked | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `run_t1_condA` | T1 | A | 5 | 5 | **TRUE** | 45.0s | 30.422 | 1.644 | **32.066** | 12 | Não | COMPROVADO |
| `run_t1_condB` | T1 | B | 5 | 5 | **TRUE** | 114.8s | 52.615 | 1.985 | **54.600** | 15 | Não | COMPROVADO |
| `run_t1_condC` | T1 | C | 5 | 5 | **TRUE** | 82.7s | 55.151 | 2.330 | **57.481** | 15 | Não | COMPROVADO |
| `run_t2_condA` | T2 | A | 7 | 7 | **TRUE** | 65.9s | 58.202 | 3.006 | **61.208** | 16 | Não | COMPROVADO |
| `run_t2_condB` | T2 | B | 7 | 7 | **TRUE** | 53.5s | 48.539 | 2.748 | **51.287** | 12 | Não | COMPROVADO |
| `run_t2_condC` | T2 | C | 7 | 7 | **TRUE** | 47.4s | 53.151 | 3.149 | **56.300** | 14 | Não | COMPROVADO |
| `run_t3_condA` | T3 | A | 3 | 3 | **TRUE** | 64.1s | 48.712 | 3.865 | **52.577** | 12 | Não | COMPROVADO |
| `run_t3_condB` | T3 | B | 3 | 3 | **TRUE** | 67.6s | 44.563 | 4.843 | **49.406** | 11 | Não | COMPROVADO |
| `run_t3_condC` | T3 | C | 3 | 3 | **TRUE** | 69.7s | 47.564 | 4.635 | **52.199** | 11 | Não | COMPROVADO |

---

## 4. ANÁLISE COMPARATIVA OBRIGATÓRIA

### 4.1 Condição B contra Condição A (Efeito das Regras Mínimas)
- **Taxa de Sucesso:** Idêntica (100% de sucesso em ambas).
- **Em T1 (Bug Fix):** Regressão de eficiência. B consumiu +70% de tokens (54.6k vs 32.1k) e +155% de tempo (114.8s vs 45.0s). O agente realizou mais leituras prévias e passos de verificação intermediários.
- **Em T2 (Feature):** Ganho de eficiência. B reduziu tokens em -16% (51.3k vs 61.2k), reduziu duração em -19% (53.5s vs 65.9s) e reduziu tool calls de 16 para 12. A regra de inspeção e adesão a requisitos evitou retrabalho e ciclos de tentativa e erro.
- **Em T3 (Refatoração):** Ganho ligeiro de eficiência em tokens. B consumiu -6% de tokens (49.4k vs 52.6k) com 11 tool calls vs 12.

### 4.2 Condição C contra Condição B (Efeito Incremental das Duas Skills ECC)
- **Taxa de Sucesso:** Idêntica (100%).
- **Invocação:** Zero invocações. As skills `tdd-workflow` e `verification-loop` não foram acionadas pelo modelo.
- **Consumo de Tokens:** C consumiu mais tokens que B em T1 (+5.3%) e em T2 (+9.8%), devido à presença dos arquivos no espaço de descoberta do agente.
- **Efeito Observado:** Nenhum ganho funcional; ligeiro aumento de sobrecarga de contexto.

### 4.3 Condição C contra Condição A (Configuração Completa versus Baseline)
- **Taxa de Sucesso:** Idêntica (100% em todas as tarefas).
- **Em T1:** Baseline nativo foi amplamente superior em tempo (45s vs 83s) e tokens (32k vs 57k).
- **Em T2:** Condição C foi mais rápida (47s vs 66s) e usou menos tokens (56k vs 61k) que A, mas foi inferior a B em tokens (56k vs 51k).
- **Em T3:** Desempenho praticamente equivalente (52.2k vs 52.6k tokens).

---

## 5. RESPOSTAS ÀS 12 PERGUNTAS DE ENGENHARIA (ETAPA 8)

1. **O Gemini 3.8 Flash funcionou na configuração nativa?**  
   **Sim.** Nas três tarefas propostas (T1, T2, T3), o modelo na Condição A atingiu 100% de sucesso nos testes de aceitação independentes sem regras ou skills adicionais.
2. **As regras mínimas foram carregadas e trouxeram algum ganho observado?**  
   **Sim.** As regras enxutas em `AGENTS.md` foram carregadas e respeitadas. Em tarefas mais complexas (T2 e T3), trouxeram redução de tool calls (-25% em T2) e menor consumo de tokens (-16% em T2, -6% em T3), ao disciplinar a inspeção prévia. Em bugs pontuais (T1), geraram sobrecarga burocrática.
3. **As duas skills foram descobertas?**  
   **Sim.** Foram identificadas na estrutura `.agents/skills/` pelo sistema de customizações do Antigravity.
4. **Foram efetivamente invocadas?**  
   **Não.** O Gemini 3.8 Flash não invocou nenhuma das duas skills nas 3 tarefas avaliadas.
5. **Seus procedimentos foram executados?**  
   **Não.** Os procedimentos específicos das skills (como git checkpoints após cada fase ou o helper `setup-package-manager.js`) não foram executados. O agente executou seu próprio loop nativo de leitura, edição e teste com `pytest`.
6. **Os testes confirmaram os resultados?**  
   **Sim.** Todos os resultados foram verificados de forma independente por suites pytest isoladas (`oracle/test_t*.py`), com assertivas estritas e sem acesso de escrita pelo agente avaliado.
7. **A condição C superou a A? Em quais tarefas e métricas?**  
   Superou A apenas em T2 (latência de 47.4s vs 65.9s e 56.3k vs 61.2k tokens), mas **não superou a Condição B**, evidenciando que qualquer ganho decorreu das regras em `AGENTS.md` e não das skills.
8. **Houve aumento de tokens, latência, complexidade ou falhas?**  
   **Sim.** A Condição C aumentou o consumo de tokens em relação à B em todas as tarefas onde houve variação e adicionou arquivos sem utilidade operacional.
9. **Quais incompatibilidades específicas existem no Antigravity?**  
   - Scripts e comandos no corpo do `SKILL.md` das skills ECC pressupõem bash POSIX (`set -o pipefail`, `tail`, `sed`, `grep`), incompatíveis com o shell padrão do Windows (PowerShell).
   - Dependência textual de variáveis de ambiente do Claude Code (`$CLAUDE_PLUGIN_ROOT`, `$CLAUDE_CONFIG_DIR`, `$HOME/.claude`).
   - A exigência de criar commits Git por fase conflita com restrições de isolamento e regras de governança locais.
10. **Que componentes podemos manter imediatamente?**  
    O arquivo enxuto de regras de projeto `AGENTS.md` (Condição B), especificamente voltado a direcionar a inspeção prévia e a verificação empírica antes de dar a tarefa por concluída.
11. **Que componentes devem ser rejeitados, corrigidos ou retestados?**  
    - **Rejeitar:** A importação cega de skills do ECC (`tdd-workflow`, `verification-loop`) sem reengenharia profunda para Antigravity/PowerShell.
    - **Retestar:** O comportamento das regras mínimas com amostragem estatística expandida (N >= 10 por condição) para avaliar dispersão estocástica.
12. **Qual é a menor configuração funcional comprovada até aqui?**  
    **A Condição B (Antigravity nativo com arquivo enxuto `AGENTS.md`).** Elimina a sobrecarga e incompatibilidade das skills legadas do Claude Code e proporciona foco em tarefas construtivas.

---

## 6. BLOQUEIOS E LIMITAÇÕES TÉCNICAS

1. **Bloqueio de Shell POSIX:** As skills do ECC contêm pipes bash incompatíveis com o PowerShell no Windows.
2. **Não Ativação Autônoma:** Sem prompts explicitamente desenhados para demandar as skills ou sem hooks forçados, o modelo Flash prefere resolver o problema diretamente com as ferramentas nativas (`run_command`, `edit_file`).
3. **Validade Amostral:** Este experimento piloto demonstra o comportamento local reproduzível em 9 execuções congeladas; conclusões populacionais gerais demandam baterias adicionais com diferentes seeds e repetições.

---

## 7. DECISÃO FINAL DE ENGENHARIA

- **Manter:** O arquivo de regras `AGENTS.md` como configuração mínima de projeto.
- **Rejeitar:** As skills `tdd-workflow` e `verification-loop` em seu estado atual do ECC no Antigravity.
- **Próximo Passo:** Reengenheirar uma skill nativa simplificada para Antigravity em PowerShell/Python e executar uma bateria de repetições estatísticas.
