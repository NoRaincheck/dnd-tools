# dnd-tools — Tool-Grounded D&D Simulation (Setting the DC)

Implements the framework from *Setting the DC: Tool-Grounded D&D Simulations to Test LLM Agents* (NeurIPS 2025 Workshop).

- **State**: seedable characters (12 classes, 3 tiers) + height-aware maps (indoor rasterized JSON / outdoor procedural)
- **Actions**: typed API with validation (initiative, movement, LoS, attack/spell, economy, bookkeeping)
- **Transition**: deterministic atomic functions, stochastic dice `1d20`, `2d20kh1` etc., auditable `tool_trace`
- **Observations**: natural-language transcript + structured tool returns (partial observability per agent)
- **Agents**: DM (transactional controller, `GM_PROMPT`) + Players (`PLAYER_PROMPT`) via **Tau** (pure Python, Hugging Face `tau-ai` + `tau_agent` harness) / LMStudio or heuristic fallback
- **Metrics**: 6 axes — Function Usage, Parameter Fidelity, Acting Quality, Tactical Optimality, State Tracking, Function Efficiency

## Quickstart

```bash
uv run dnd-tools demo --seed 42 --turns 10
uv run dnd-tools gen-scenarios --seed 42 --out scenarios   # 27 scenarios (3×3×3)
uv run dnd-tools run-scenario scenarios/scenario_01.json --turns 10
```

## Using `tau` (pure Python LLM) as DM / Players

This repo uses [`tau-ai`](https://github.com/huggingface/tau) as a **self-contained Python library** — no subprocesses, no Pi CLI. Tau's `OpenAICompatibleProvider` + `AgentHarness` talk directly to any OpenAI-compatible endpoint (LMStudio at `http://127.0.0.1:1234/v1` by default). Every D&D tool is exposed as a `tau_agent.tools.AgentTool` with JSON-schema validation; the harness streams `AssistantMessageEvent`s and `ToolExecutionEndEvent`s in-process.

```bash
# list available models (LMStudio local server)
curl http://127.0.0.1:1234/v1/models | jq .data[].id
# run encounter with Tau LLM (heuristic off) — each player turn is a Tau harness with tool-calling loop
uv run dnd-tools demo --use-llm --model qwen3.6-35b-a3b-mtp --base-url http://127.0.0.1:1234/v1
# any OpenAI-compatible endpoint works:
# uv run dnd-tools demo --use-llm --model gpt-4o --base-url https://api.openai.com/v1  # with OPENAI_API_KEY
```

Heuristic fallback (no LLM) gives instant deterministic play for debugging and headless CI. `agents.py` exposes `make_tau_provider`, `_tools_to_agent_tools`, and `run_tau_player_turn_sync` — see `simulation.py` for integration; no `subprocess` or external CLI is invoked.

## Architecture

```
src/dnd_tools/
  models.py      — Character, Weapon, Spell, Cell, templates
  dice.py        — roll_dice("1d20"), advantage, seeded RNG
  state.py       — GameState (HP, pos, initiative, LoS, death log)
  tools.py       — 30+ typed tools (check_valid_attack_line, roll_attack, roll_dmg, move_player, …) + OpenAI schemas
  mapgen.py      — indoor (JSON rooms/walls) / outdoor (procedural, connectivity, heights)
  prompts.py     — GM_PROMPT / PLAYER_PROMPT verbatim from paper appendix
  agents.py      — Tau-native (tau_ai OpenAICompatibleProvider + tau_agent AgentHarness), AgentTool conversion, heuristic fallback
  simulation.py  — Generation + Simulation Loop (Fig. 1: query → move → validate → resolve → bookkeep; Tau harness per player turn)
  metrics.py     — 6 automated metrics (A density/diversity, O reward, hallucination rate, F1 proxies)
  cli.py         — demo / gen-scenarios / run-scenario / eval (Tau --use-llm flag)
```

## Tool API (6 categories, paper §3)

1. **Query/validation**: `check_valid_attack_line`, `check_hp`, `check_side`, `check_player_property`, `check_resources`, `check_class`, `check_monster_type`, `check_monster_actions`, `get_names_of_all_*`, `check_player_mainhand`, `check_buffs`, `check_concentration`, `check_resist`
2. **Movement**: `move`/`move_player`, `dash`, `disengage`, `opportunity_attack`, `clear_speed`, `reset_speed`
3. **Dice**: `roll_dice`
4. **Attack/spell**: `roll_attack`, `roll_spell_attack`, `roll_save`, `roll_dmg`, `update_hp`
5. **Economy/bookkeeping**: `roll_initiative`, `reset_resources`, `add_resist/immune/vulner`, `remove_a_buff`, `remove_resist/immune/vulner`, `remove_a_concentration`, `print_death_point`
6. **Rendering**: `visualize_map`

Each call is validated (initiative, action/bonus/reaction budgets, spell slots, range/LoS, height advantage) and logged to `tool_trace` for auditable evaluation.

## Loop (Fig. 1)

`roll_initiative` → turn loop: `check_side` → (optional) `move`/`dash` → `check_valid_attack_line` → `roll_attack`/`roll_spell_attack`/`roll_save`/`roll_dmg` → `check_resist`→`update_hp` → `reset_resources`+`reset_speed`+ buff/concentration audits → `<End Turn/>`. Players propose; DM validates/executes (enforced via tools). Ends after 10 turns or one side dies; `print_death_point`.

## Paper Fidelity

- Spells: 19 canonical (Fire Bolt … Thunderous Smite) with cost/range/damage/concentration per appendix
- Conditions: charmed/prone/incapacitated/frightened/poisoned/restrained/paralyzed/blinded/deafened (via `check_buffs`/`clear_speed`)
- Height-aware LoS: `terrain_z >= line_z+0.25` sampled per cell (`check_valid_attack_line:16`)
- Economy: Dash/Disengage consume action; spell-slot gating via `check_resources`+`check_class`; advantage/disadvantage cancel

## Reproducing Paper Tables

Run all 27 scenarios heuristically and aggregate `evaluate_all` — see `eval` helper:

```bash
uv run python -c "from dnd_tools.simulation import generate_scenarios, load_scenario; from dnd_tools.metrics import evaluate_all; ..."
```

Swap `--use-llm` per model (`claude-3.5-haiku`, `gpt-4o`, `deepseek-v3` via their APIs, or local `qwen3.6-35b-a3b-mtp`/`tiel-coder-35b-a3b-mtp` through LMStudio) to mirror Table 2/3.

## License

MIT — implementation only; paper © authors.
