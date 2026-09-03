# AGENTS.md — Project Guidelines for AI Agents

## Project Overview

**dnd-tools** — Tool-Grounded D&D Simulation (Setting the DC). Implements the framework from *Setting the DC: Tool-Grounded D&D Simulations to Test LLM Agents* (NeurIPS 2025 Workshop).

- **Language**: Python 3.14
- **Package manager / runner**: [`uv`](https://github.com/astral-sh/uv)
- **Structure**: `uv` workspace with `packages/dnd-tools/` (paper impl, `src/dnd_tools/`) and `packages/dnd-campaign/` (long-horizon layer, `src/dnd_campaign/`), `ref/` (references), workspace `pyproject.toml`

## Tooling

This project uses **`uv`** for everything — dependency management, virtual environment, and running commands.

```bash
# Install dependencies
uv sync

# Run the CLI
uv run dnd-tools demo --seed 42 --turns 10

# Run any Python script
uv run python -c "from dnd_tools import ..."
```

## Code Quality

**Before committing any changes, ensure all of the following pass:**

### 1. Tests

```bash
uv run pytest
```

- Tests live alongside the code they test (or in a `tests/` directory if created).
- Write new tests for new functionality and bug fixes.

### 2. Formatting & Linting (Ruff)

```bash
uv run ruff check .        # lint
uv run ruff format --check .  # formatting check
```

- Apply fixes automatically when in doubt: `uv run ruff check --fix . && uv run ruff format .`

### 3. Type Checks (ty)

```bash
uv run ty check .
```

- The project uses `ty` for static type checking.
- Add type annotations to new code and ensure existing code stays clean.

### Combined Check

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run ty check .
```

## Key Modules

| Module | Purpose |
|---|---|
| `models.py` | Character, Weapon, Spell, Cell, templates |
| `dice.py` | Seeded RNG dice rolls (`1d20`, advantage, etc.) |
| `state.py` | GameState (HP, position, initiative, LoS, death log) |
| `tools.py` | 30+ typed tools with validation and OpenAI schemas |
| `mapgen.py` | Indoor (JSON rooms) / outdoor (procedural) map generation |
| `prompts.py` | GM_PROMPT / PLAYER_PROMPT |
| `agents.py` | LLMClient, DMAgent, PlayerAgent, tool-use loop, heuristics |
| `simulation.py` | Scenario generation + simulation loop |
| `metrics.py` | 6 automated evaluation metrics |
| `cli.py` | CLI entry points (`demo`, `gen-scenarios`, `run-scenario`) |

## Common Commands

```bash
# Run demo encounter
uv run dnd-tools demo --seed 42 --turns 10

# Generate 27 scenarios (paper package)
uv run dnd-tools gen-scenarios --seed 42 --out packages/dnd-tools/scenarios

# Run a single scenario
uv run dnd-tools run-scenario packages/dnd-tools/scenarios/scenario_01.json --turns 10

# Run with LLM (requires LMStudio at :1234)
uv run dnd-tools demo --use-llm --model qwen3.6-35b-a3b-mtp

# Campaign demo
uv run dnd-campaign demo --seed 42 --turns 10
```

## Dependencies

Dev dependencies (from `pyproject.toml`):
- `pytest` — testing
- `ruff` — linting and formatting
- `ty` — type checking

Runtime dependencies:
- `tau-ai`

## Constraints

- Python ≥ 3.14 (enforced via `.python-version` and `pyproject.toml`)
- All code must pass the combined quality check before commit
- New tools should follow the typed API pattern in `tools.py` with validation
- Deterministic behavior: use seeded RNG where applicable
