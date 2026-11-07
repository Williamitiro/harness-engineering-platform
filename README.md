# Harness Engineering

Kit pequeno de **regras e skills** para o Claude Code e o Codex trabalharem com mais disciplina em qualquer
repositório (teste antes, verificação antes do "pronto", sem apagar trabalho alheio), mais um **benchmark** para
provar se o kit realmente ajuda.

Não é um agente novo: o Claude Code e o Codex continuam fazendo o trabalho. O Harness só instala, confere e mede.

## Onde ler

| Você quer… | Leia |
|---|---|
| **usar** (instalar no computador, preparar um repositório, trabalhar) | [docs/MANUAL.md](docs/MANUAL.md) |
| saber **o que funciona hoje** e o que falta | [docs/ESTADO.md](docs/ESTADO.md) |
| entender **as regras e o desenho** (para agentes e devs) | [docs/SPEC.md](docs/SPEC.md) |

O histórico (relatórios, auditorias, experimentos antigos) está em [docs/historico/](docs/historico/) apenas como
arquivo.

## Estrutura

```
docs/            MANUAL, SPEC, ESTADO (+ evidence/ com dados brutos, historico/ arquivado)
skills/          skills próprias do Harness (setup-harness)
vendor/ecc/      skills ECC (tdd-workflow, verification-loop), cópia pinada por hash, licença MIT
templates/       AGENTS.md / CLAUDE.md iniciais para repositórios novos
config/          catálogo de skills aprovadas (hashes), políticas
scripts/         harnessctl.py (instalador), harness_eval.py (benchmark), jev_http.py (JEV)
tests/           suíte offline (stdlib, sem rede, sem modelo)
```

## Testes

```bash
python -W error -m unittest discover -s tests
```
