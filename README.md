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

> Workshop PDF is not tracked verbatim in this repo (see `ref/31_Setting_the_DC_Synthesis.md:100`).
> Result tables are not committed — they are generated on demand via the CLI below. Only results that
> you explicitly run locally are reported; this section documents *how* to reproduce the paper's
> 27-scenario (3×3×3) design.

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
# Expected stdout shape (values depend on local run, not committed):
#   scenario_01.json: O=0.xxx A=0.xxx err=x.x%
#   ...
#   Aggregated — O 0.xxx | A 0.xxx | func_err x.x% | n=27

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

### Per-model LLM reproduction (requires an OpenAI-compatible endpoint)

Swap `--use-llm` to mirror paper Table 2/3. No LLM results are committed.

```bash
uv run dnd-tools eval scenarios --use-llm --model claude-3-5-haiku --base-url https://api.anthropic.com/v1
uv run dnd-tools eval scenarios --use-llm --model gpt-4o --base-url https://api.openai.com/v1
uv run dnd-tools eval scenarios --use-llm --model deepseek-v3 --base-url https://api.deepseek.com/v1
# Local open-weight via LMStudio:
uv run dnd-tools eval scenarios --use-llm --model qwen3.6-35b-a3b-mtp --base-url http://127.0.0.1:1234/v1
```

### Paper-reported results (paraphrased, §6) — the only table committed

The paper evaluated the same 27 JSON saves, 10 turns/episode, transcript + ordered tool trace,
micro-averaged, with automated + human judges (`r≈0.96` acting quality, `r≈0.98` tactical).
`gpt-oss-120b` was tried but omitted for identity inconsistency.

| Model (paper) | Function Usage ↓ incorrect fn | Parameter Fidelity ↓ incorrect params | Function Efficiency ↓ unnecessary / missing → F1 | State Tracking ↓ hallucination | Acting Quality ↑ A (density/diversity) | Tactical Optimality ↑ O / survivability / efficiency |
|---|---|---|---|---|---|---|
| **Claude 3.5 Haiku** — most reliable overall | **~1.2%** (lowest) | **~1.1%** (lowest) | **lowest** unnecessary & missing → **95% F1 (human)**, best auto F1 | lowest hallucination | competitive (r≈0.96 vs human) | most aggressive in easy maps (lower remaining resources); **best combat efficiency in hard maps** |
| **GPT-4o** — close second | slightly higher than Haiku | slightly higher, higher variance | slightly higher redundant calls | slightly higher hallucination | competitive | occasionally strongest peaks but higher variance; similar survivability in easy scenarios |
| **DeepSeek-V3** — trails | notably higher | notably higher | notably higher **missing-call rate** | **notably higher hallucination**, grows with horizon; status-effect & resource errors dominate | **competitive persona density** | trails on efficiency / resource conservation |
| gpt-oss-120b | — | — | — | — | — | omitted (failed identity consistency; pre-training/tuning mismatch, not just scale) |

> **Reading:** lower is better for the three error-rate columns; higher is better for A / O / F1.
> Hallucination grows with horizon on all models even after removing late-game entity-state errors;
> entity-state confusion is rare but high-rate when it occurs. Resource trade-offs diverge:
> easy scenarios similar survivability while Haiku is more aggressive; hard scenarios that aggression
> yields best combat efficiency at cost of conservation.
>
> Heuristic `A`/`O` in this repo are lightweight proxies (`metrics.py:39,92`); paper's full
> human-judged persona diversity and combat-efficiency/remaining-resource curves require LLM
> judges. Use the `eval` / `eval --use-llm` paths above for an apples-to-apples replication;
> the design is seed-identical so traces are directly comparable.

## License

MIT — implementation only; paper © authors.
