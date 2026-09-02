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

> Original paper tables (Table 2 automated / Table 3 human-judged) are paraphrased below because the
> workshop PDF is not tracked verbatim in this repo (see `ref/31_Setting_the_DC_Synthesis.md:100`).
> The numeric reproduction that *is* auditable in this codebase is the deterministic heuristic baseline
> over the identical 3×3×3 design (27 scenarios, 10 turns, seed 42). Run it with `dnd-tools eval`.

### How to reproduce (this repo)

```bash
# 1. Generate the 27 scenarios (3 party-groups × 3 tiers × 3 monster–map sets)
uv run dnd-tools gen-scenarios --seed 42 --out scenarios

# 2. Heuristic baseline — deterministic, no LLM (what the tables below report)
uv run dnd-tools eval scenarios --turns 10
# => Aggregated — O 0.795 | A 0.552 | func_err 2.1% | n=27

# 3. Per-model LLM reproduction (requires an OpenAI-compatible endpoint)
#    Swap --use-llm per model to mirror paper Table 2/3:
uv run dnd-tools eval scenarios --use-llm --model claude-3-5-haiku --base-url https://api.anthropic.com/v1
uv run dnd-tools eval scenarios --use-llm --model gpt-4o --base-url https://api.openai.com/v1
uv run dnd-tools eval scenarios --use-llm --model deepseek-v3 --base-url https://api.deepseek.com/v1
# Local open-weight via LMStudio:
uv run dnd-tools eval scenarios --use-llm --model qwen3.6-35b-a3b-mtp --base-url http://127.0.0.1:1234/v1

# 4. Single-scenario drill-down
uv run dnd-tools run-scenario scenarios/scenario_01.json --turns 10
```

Metrics are `src/dnd_tools/metrics.py:8` (`function_usage`, `parameter_fidelity`, `acting_quality`,
`tactical_optimality`, `state_tracking`, `function_efficiency`) evaluated via `evaluate_all` on
`transcript` + `tool_trace`. See paper §4 / `ref/31_Setting_the_DC_Synthesis.md:60`.

### Paper-reported results (paraphrased, §6)

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

### Reproduced results — heuristic baseline (this repo, auditable)

Deterministic greedy policy `src/dnd_tools/agents.py:276` (`heuristic_player_turn`), no LLM,
`seed=42`, `max_turns=10`, `n=27` scenarios, avg tool calls 93.6 / episode, avg rounds 2.0.
Hallucination is 0% by construction (authoritative `Tools` dispatch); remaining errors are
non-critical `out_of_range` / redundant `check_*` calls intrinsic to the greedy policy.

#### Table 1 — 6-axis aggregate (micro-averaged over 27 scenarios)

| Metric | Source | Value | Interpretation |
|---|---|---|---|
| **Function Usage** — incorrect function % | `metrics.py:8` | **2.11%** (57 / 2526 calls) | wrong tool / unsatisfied preconditions (`valid=false`) |
| **Parameter Fidelity** — incorrect params % | `metrics.py:27` | **0.00%** | `out_of_range` args |
| **Function Efficiency** — unnecessary % | `metrics.py:125` | **12.66%** | repeated identical `check_*` without state change |
| **State Tracking** — hallucination rate | `metrics.py:117` | **0.000** | `error` in tool result |
| **Acting Quality** — A = 0.5·density + 0.5·diversity | `metrics.py:39` | **0.552** (density 0.460, diversity 0.644) | persona density + trait coverage, Tmax=5, capped at 1 |
| **Tactical Optimality** — O (mean turn reward) | `metrics.py:92` | **0.795** (windows=11) | 1.0 attack/spell, 0.5 move-only, else 0, micro-averaged |

Reference run: `uv run dnd-tools eval scenarios --turns 10` → `O 0.795 | A 0.552 | func_err 2.1%`.

#### Table 2 — Breakdown by tier / map / party group

| Slice | n | incorrect fn % | incorrect params % | unnecessary % | A | O | avg tool calls |
|---|---|---|---|---|---|---|---|
| **Overall** | 27 | 2.11 | 0.00 | 12.66 | 0.552 | 0.795 | 93.6 |
| Tier **low** (stats 8–12) | 9 | 1.68 | 0.00 | 13.43 | 0.536 | 0.818 | 94.7 |
| Tier **medium** (10–16) | 9 | 2.75 | 0.00 | 11.85 | 0.554 | 0.737 | 89.9 |
| Tier **high** (14–18) | 9 | 1.90 | 0.00 | 12.71 | 0.567 | 0.828 | 96.1 |
| Map **Goblin Ambush** (outdoor) | 9 | 0.37 | 0.00 | 12.65 | 0.561 | 0.859 | 97.7 |
| Map **Kennel** (indoor) | 9 | 3.51 | 0.00 | 13.22 | 0.551 | 0.737 | 89.3 |
| Map **Klarg's Cave** (indoor) | 9 | 2.45 | 0.00 | 12.12 | 0.544 | 0.788 | 93.7 |
| Group **fighter/wizard/cleric/rogue** | 9 | 1.56 | 0.00 | 12.73 | 0.200 | 0.818 | 95.2 |
| Group **ranger/paladin/bard/druid** | 9 | 1.84 | 0.00 | 11.80 | 0.961 | 0.808 | 93.7 |
| Group **barbarian/monk/sorcerer/warlock** | 9 | 2.93 | 0.00 | 13.46 | 0.496 | 0.758 | 91.8 |

Notes: A varies strongly by group because `metrics.py:46` keyword heuristics trigger on
`ranger/paladin/bard/druid` flavor text (density 0.94) vs generic `fighter` group (0.00).
Indoor maps (Kennel/Klarg) show higher incorrect-function rates than outdoor — consistent with
paper's height-aware LoS gating being the bottleneck (`check_valid_attack_line:16`).

#### Table 3 — Per-scenario (27 = 3×3×3, seed 42+sid)

| # | Tier | Monster Set | Party (abbr) | fn err | param err | unnec. | halluc. | A | O | calls |
|---|---|---|---|---|---|---|---|---|---|---|
| 01 | low | Goblin Ambush | fig,wiz,cle,rog | 0.0% | 0.0% | 12.7% | 0.0% | 0.200 | 0.909 | 102 |
| 02 | low | Kennel | fig,wiz,cle,rog | 2.3% | 0.0% | 12.8% | 0.0% | 0.200 | 0.727 | 86 |
| 03 | low | Klarg's Cave | fig,wiz,cle,rog | 0.0% | 0.0% | 14.4% | 0.0% | 0.200 | 0.909 | 97 |
| 04 | medium | Goblin Ambush | fig,wiz,cle,rog | 1.1% | 0.0% | 11.7% | 0.0% | 0.200 | 0.818 | 94 |
| 05 | medium | Kennel | fig,wiz,cle,rog | 2.2% | 0.0% | 13.0% | 0.0% | 0.200 | 0.727 | 92 |
| 06 | medium | Klarg's Cave | fig,wiz,cle,rog | 5.6% | 0.0% | 14.4% | 0.0% | 0.200 | 0.636 | 90 |
| 07 | high | Goblin Ambush | fig,wiz,cle,rog | 0.0% | 0.0% | 13.0% | 0.0% | 0.200 | 0.909 | 100 |
| 08 | high | Kennel | fig,wiz,cle,rog | 0.0% | 0.0% | 10.6% | 0.0% | 0.200 | 0.909 | 94 |
| 09 | high | Klarg's Cave | fig,wiz,cle,rog | 2.9% | 0.0% | 11.8% | 0.0% | 0.200 | 0.818 | 102 |
| 10 | low | Goblin Ambush | ran,pal,bar,dru | 0.0% | 0.0% | 13.3% | 0.0% | 0.962 | 0.727 | 90 |
| 11 | low | Kennel | ran,pal,bar,dru | 0.0% | 0.0% | 14.0% | 0.0% | 0.967 | 0.909 | 93 |
| 12 | low | Klarg's Cave | ran,pal,bar,dru | 0.0% | 0.0% | 12.6% | 0.0% | 0.967 | 0.909 | 103 |
| 13 | medium | Goblin Ambush | ran,pal,bar,dru | 0.0% | 0.0% | 10.8% | 0.0% | 1.000 | 0.909 | 102 |
| 14 | medium | Kennel | ran,pal,bar,dru | 0.0% | 0.0% | 13.4% | 0.0% | 0.969 | 0.909 | 97 |
| 15 | medium | Klarg's Cave | ran,pal,bar,dru | 2.4% | 0.0% | 3.5% | 0.0% | 1.000 | 0.818 | 85 |
| 16 | high | Goblin Ambush | ran,pal,bar,dru | 0.0% | 0.0% | 12.6% | 0.0% | 0.967 | 0.909 | 103 |
| 17 | high | Kennel | ran,pal,bar,dru | 10.7% | 0.0% | 13.1% | 0.0% | 0.858 | 0.455 | 84 |
| 18 | high | Klarg's Cave | ran,pal,bar,dru | 3.5% | 0.0% | 12.8% | 0.0% | 0.958 | 0.727 | 86 |
| 19 | low | Goblin Ambush | bar,mon,sor,war | 0.0% | 0.0% | 13.1% | 0.0% | 0.487 | 0.909 | 107 |
| 20 | low | Kennel | bar,mon,sor,war | 12.8% | 0.0% | 15.4% | 0.0% | 0.367 | 0.455 | 78 |
| 21 | low | Klarg's Cave | bar,mon,sor,war | 0.0% | 0.0% | 12.5% | 0.0% | 0.479 | 0.909 | 96 |
| 22 | medium | Goblin Ambush | bar,mon,sor,war | 2.3% | 0.0% | 13.8% | 0.0% | 0.467 | 0.727 | 87 |
| 23 | medium | Kennel | bar,mon,sor,war | 3.6% | 0.0% | 13.1% | 0.0% | 0.621 | 0.636 | 84 |
| 24 | medium | Klarg's Cave | bar,mon,sor,war | 7.7% | 0.0% | 12.8% | 0.0% | 0.325 | 0.455 | 78 |
| 25 | high | Goblin Ambush | bar,mon,sor,war | 0.0% | 0.0% | 12.8% | 0.0% | 0.569 | 0.909 | 94 |
| 26 | high | Kennel | bar,mon,sor,war | 0.0% | 0.0% | 13.5% | 0.0% | 0.581 | 0.909 | 96 |
| 27 | high | Klarg's Cave | bar,mon,sor,war | 0.0% | 0.0% | 14.2% | 0.0% | 0.565 | 0.909 | 106 |

Generate this table locally:

```bash
uv run python -c "
from pathlib import Path
from dnd_tools.simulation import load_scenario, Simulation
from dnd_tools.metrics import evaluate_all
import json
for p in sorted(Path('scenarios').glob('scenario_*.json')):
    s,t = load_scenario(p)
    r = Simulation(s,t, use_heuristic=True, max_turns=10).run()
    m = evaluate_all(r['transcript'], r['tool_trace'])
    print(p.name, m['tactical_optimality']['O'], m['acting_quality']['A'])
"
```

> **Limitations vs paper:** heuristic `A`/`O` are lightweight proxies (`metrics.py:39,92`) —
> paper's full human-judged persona diversity and combat-efficiency/remaining-resource curves
> require LLM judges; hallucination is zero here but paper reports non-zero for all LLMs,
> growing with horizon. Use the `eval --use-llm` path for an apples-to-apples replication when an
> endpoint is available; the design is seed-identical so traces are directly comparable.

## License

MIT — implementation only; paper © authors.
