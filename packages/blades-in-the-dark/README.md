# blades-in-the-dark — Blades in the Dark (Forged in the Dark) tool-grounded implementation

> **LLM-verified via `tau-ai` / `tau_agent` (LMStudio `:1234`) — heuristic fallback when no LLM**

Implements the **Position & Effect + Stress** framework from Blades in the Dark (SRD, CC BY 3.0) as a tool-grounded simulation — the *"AI Fix"* for LLM leniency. Every roll requires explicit `position` (Controlled/Risky/Desperate) and `effect` (Limited/Standard/Great) agreement, and every `4-5`/`1-3` outcome maps to a position-gated consequence that must be taken or resisted via Stress.

Uses `dnd-tools` + `dnd-campaign` as foundations (mapgen, seeded dice, tau harness, snapshot/campaign plumbing) — paper implementation (`packages/dnd-tools`) stays frozen.

- **Single score** (`BladesState` + `BladesTools` + `BladesSimulation`) — one score with deterministic `1-6d6` action rolls (highest-die + critical on 2+ sixes), bonus dice gates (assist / push / Devil's Bargain), engagement roll, and progress clocks.
- **Multiple scores with context** (`BladesCampaignState` + `BladesCampaignTools` + `BladesSession`) — bounded history, checkpoints, `get_summary`/`prune_traces`, vice/recovery between scores.
- **Whole campaign** (`run_campaign`) — sequence of scores with inter-score downtime.
- **LLM** via `tau-ai` / `tau_agent` (LMStudio `:1234` by default), with heuristic fallback.

## Why Position & Effect + Stress (The AI Fix)

> "I am attempting this in a **Desperate** position with **Limited** effect. I rolled a 3 (Failure). Give me a harsh consequence and ask me how I mark Stress to avoid the worst of it."

- Before any `action_roll`, `set_position_and_effect` must be called — the position/effect pair is logged and validated.
- The consequence table is **position-dependent**: Desperate `4-5` → *severe harm / serious complication / reduced effect*; `1-3` → *severe harm + serious complication + lost opportunity*. The framework prevents the AI from softening.
- On any consequence the player may `resistance_roll` (`6 − high die` stress, critical clears 1) or `use_armor` — always effective but always costly.

## Quickstart

```bash
uv sync
# single score (heuristic, no LLM)
uv run blades scene --seed 42 --turns 10
# single score via LLM (requires LMStudio at :1234)
uv run blades scene --seed 42 --turns 6 --use-llm --model qwen3.6-35b-a3b-mtp
# multi-score campaign
uv run blades campaign --seed 42 --turns 8
# generate scenarios
uv run blades gen-scenarios --out /tmp/blades_test_scen
uv run pytest
```

## Tool surface (LLM-visible)

`set_position_and_effect`, `action_roll`, `push_yourself`, `assist`, `devil_bargain`, `resistance_roll`, `mark_stress/clear_stress`, `apply_harm/heal_harm/use_armor`, `set_clock/tick_clock/check_clock`, `engage_roll`, `gather_information`, `flashback`, `check_character`, `visualize_clocks` + campaign helpers (`long_rest`/`indulge_vice`, `checkpoint`, `get_summary`, `prune_traces`).

## References

- SRD: https://bladesinthedark.com/action-roll, /effect, /setting-position-effect, /resistance-armor (+ https://github.com/amazingrando/blades-in-the-dark-srd-content)
- Condensed reference: `ref/blades-in-the-dark.md`
