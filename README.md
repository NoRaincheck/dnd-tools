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
packages/dnd-tools/src/dnd_tools/   # paper implementation (frozen)
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

packages/dnd-campaign/src/dnd_campaign/  # long-horizon layer (isolated)
  state.py     — CampaignState wrapper (snapshots, persistence, long/short rest)
  tools.py     — CampaignTools (delegates to Tools + 6 campaign tools)
  session.py   — CampaignSession (multi-encounter orchestration)
  memory.py    — transcript/state compaction for LLM context
  cli.py       — dnd-campaign demo
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

> Workshop PDF is not tracked verbatim in this repo (see `ref/31_Setting_the_DC_Synthesis.md:100`).

### How to reproduce (CLI — single source of truth)

All commands are deterministic and seedable. The 27 scenarios are committed in `scenarios/`
(generated via `gen-scenarios --seed 42`); regenerate them at any time:

```bash
# 1. Generate (or regenerate) the 27 scenarios (3 party-groups × 3 tiers × 3 monster–map sets)
#    Creates scenarios/scenario_01.json … scenario_27.json (seed 42 + sid)
uv run dnd-tools gen-scenarios --seed 42 --out scenarios
ls scenarios  # 27 files, committed in git

# 2. Heuristic baseline — deterministic, no LLM (auditable via tool_trace)
#    Runs all 27, prints per-scenario O/A/err and an aggregated line
uv run dnd-tools eval scenarios --turns 10

# 3. Save machine-readable metrics for further analysis
uv run dnd-tools eval scenarios --turns 10 --out metrics.json
cat metrics.json | jq .

# 4. Single-scenario drill-down (transcript + 6-axis metrics)
uv run dnd-tools run-scenario scenarios/scenario_01.json --turns 10
uv run dnd-tools demo --seed 42 --turns 10   # ad-hoc encounter without scenarios dir
```

Metrics are `src/dnd_tools/metrics.py:8` (`function_usage`, `parameter_fidelity`, `acting_quality`,
`tactical_optimality`, `state_tracking`, `function_efficiency`) via `evaluate_all` on
`transcript` + `tool_trace`. The heuristic policy is `src/dnd_tools/agents.py:276`
(`heuristic_player_turn`); hallucination is 0 by construction (authoritative `Tools` dispatch).
See paper §4 / `ref/31_Setting_the_DC_Synthesis.md:60` for definitions.

### Reproduced results — heuristic baseline on committed `scenarios/` (seed 42, 10 turns, `n=27`)

Run via `uv run dnd-tools eval scenarios --turns 10` (2526 tool calls total, 93.6 avg/scenario).
Table below is the exact output of that command on the committed scenarios — no other results are included.

**Aggregated (micro-averaged over 27 scenarios):**

| Metric | Source | Value |
|---|---|---|
| Function Usage — incorrect function % | `metrics.py:8` | **2.11%** |
| Parameter Fidelity — incorrect params % | `metrics.py:27` | **0.00%** |
| Function Efficiency — unnecessary % | `metrics.py:125` | **12.66%** |
| State Tracking — hallucination rate | `metrics.py:117` | **0.000** |
| Acting Quality — A = 0.5·density + 0.5·diversity | `metrics.py:39` | **0.552** |
| Tactical Optimality — O (mean turn reward) | `metrics.py:92` | **0.795** |
| Avg tool calls / scenario | — | **93.6** (2526 total) |

`Aggregated — O 0.795 | A 0.552 | func_err 2.1% | n=27` — matches CLI footer.

**Per-scenario (27 = 3×3×3, seed 42+sid):**

| # | Tier | Monster Set | Party | O | A | func_err | calls |
|---|---|---|---|---|---|---|---|
| 01 | low | Goblin Ambush | fighter,wizard,cleric,rogue | 0.909 | 0.200 | 0.0% | 102 |
| 02 | low | Kennel | fighter,wizard,cleric,rogue | 0.727 | 0.200 | 2.3% | 86 |
| 03 | low | Klarg's Cave | fighter,wizard,cleric,rogue | 0.909 | 0.200 | 0.0% | 97 |
| 04 | medium | Goblin Ambush | fighter,wizard,cleric,rogue | 0.818 | 0.200 | 1.1% | 94 |
| 05 | medium | Kennel | fighter,wizard,cleric,rogue | 0.727 | 0.200 | 2.2% | 92 |
| 06 | medium | Klarg's Cave | fighter,wizard,cleric,rogue | 0.636 | 0.200 | 5.6% | 90 |
| 07 | high | Goblin Ambush | fighter,wizard,cleric,rogue | 0.909 | 0.200 | 0.0% | 100 |
| 08 | high | Kennel | fighter,wizard,cleric,rogue | 0.909 | 0.200 | 0.0% | 94 |
| 09 | high | Klarg's Cave | fighter,wizard,cleric,rogue | 0.818 | 0.200 | 2.9% | 102 |
| 10 | low | Goblin Ambush | ranger,paladin,bard,druid | 0.727 | 0.962 | 0.0% | 90 |
| 11 | low | Kennel | ranger,paladin,bard,druid | 0.909 | 0.967 | 0.0% | 93 |
| 12 | low | Klarg's Cave | ranger,paladin,bard,druid | 0.909 | 0.967 | 0.0% | 103 |
| 13 | medium | Goblin Ambush | ranger,paladin,bard,druid | 0.909 | 1.000 | 0.0% | 102 |
| 14 | medium | Kennel | ranger,paladin,bard,druid | 0.909 | 0.969 | 0.0% | 97 |
| 15 | medium | Klarg's Cave | ranger,paladin,bard,druid | 0.818 | 1.000 | 2.4% | 85 |
| 16 | high | Goblin Ambush | ranger,paladin,bard,druid | 0.909 | 0.967 | 0.0% | 103 |
| 17 | high | Kennel | ranger,paladin,bard,druid | 0.455 | 0.858 | 10.7% | 84 |
| 18 | high | Klarg's Cave | ranger,paladin,bard,druid | 0.727 | 0.958 | 3.5% | 86 |
| 19 | low | Goblin Ambush | barbarian,monk,sorcerer,warlock | 0.909 | 0.487 | 0.0% | 107 |
| 20 | low | Kennel | barbarian,monk,sorcerer,warlock | 0.455 | 0.367 | 12.8% | 78 |
| 21 | low | Klarg's Cave | barbarian,monk,sorcerer,warlock | 0.909 | 0.479 | 0.0% | 96 |
| 22 | medium | Goblin Ambush | barbarian,monk,sorcerer,warlock | 0.727 | 0.467 | 2.3% | 87 |
| 23 | medium | Kennel | barbarian,monk,sorcerer,warlock | 0.636 | 0.621 | 3.6% | 84 |
| 24 | medium | Klarg's Cave | barbarian,monk,sorcerer,warlock | 0.455 | 0.325 | 7.7% | 78 |
| 25 | high | Goblin Ambush | barbarian,monk,sorcerer,warlock | 0.909 | 0.569 | 0.0% | 94 |
| 26 | high | Kennel | barbarian,monk,sorcerer,warlock | 0.909 | 0.581 | 0.0% | 96 |
| 27 | high | Klarg's Cave | barbarian,monk,sorcerer,warlock | 0.909 | 0.565 | 0.0% | 106 |

### Per-model LLM reproduction (requires an OpenAI-compatible endpoint)

Swap `--use-llm` to evaluate LLMs on the same 27 scenarios. No LLM results are committed.

```bash
uv run dnd-tools eval scenarios --use-llm --model claude-3-5-haiku --base-url https://api.anthropic.com/v1
uv run dnd-tools eval scenarios --use-llm --model gpt-4o --base-url https://api.openai.com/v1
uv run dnd-tools eval scenarios --use-llm --model deepseek-v3 --base-url https://api.deepseek.com/v1
# Local open-weight via LMStudio:
uv run dnd-tools eval scenarios --use-llm --model qwen3.6-35b-a3b-mtp --base-url http://127.0.0.1:1234/v1
```

## License

MIT — implementation only; paper © authors.
