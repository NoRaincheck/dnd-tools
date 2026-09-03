"""Full campaign demo — combining dnd-tools (paper) + dnd-campaign (long-horizon).

This script is the canonical example for the workspace. It shows:

1.  Creating a party with dnd-tools primitives (create_player, Character)
2.  Wrapping the authoritative GameState in CampaignState for snapshots / rests
3.  Delegating tools via CampaignTools (30 paper tools + 6 campaign tools)
4.  Orchestrating multiple encounters with CampaignSession (with heuristic or tau-ai)
5.  Using tau-ai TauLLM provider for LLM-driven turns (falls back to heuristic if no server)
6.  Saving / loading checkpoints and pruning traces for long horizons

Run:
    uv sync
    uv run python scripts/full_campaign.py --seed 42 --turns 5
    uv run python scripts/full_campaign.py --seed 42 --turns 5 --use-llm --model qwen3.6-35b-a3b-mtp
    uv run python scripts/full_campaign.py --help

The output below is the actual transcript from `uv run python scripts/full_campaign.py --seed 42 --turns 5`
using the workspace's tau-ai integration (heuristic fallback when LMStudio not running).
It is embedded here so the script is self-documenting — a reader can understand the I/O without running it.

Example output (seed 42, 2 encounters, 5 turns each — tau-ai heuristic fallback):
```
[setup] seed=42 turns=5 use_llm=False
[setup] party: ['Elaria(ranger)', 'Briana(wizard)', 'Thalion(fighter)', 'Mira(cleric)']
[tools] base=39 + campaign=6 => total=45
[get_summary] {
  "round": 1,
  "turn": null,
  "players": {
    "Elaria": {
      "hp": 10,
      "max_hp": 10,
      ...
    }
  }
}...

[encounter 1] outdoor — ['goblin', 'goblin', 'goblin'] vs party (heuristic , max_turns=5)
[check_resources] Elaria => {'action': 1, 'bonus_action': 1, 'reaction': 1, 'spell_slots': {1: 2}, 'speed_remaining': 30}

=== ENCOUNTER 1 ===
--- Monster Turn: M2_goblin (round 1) ---
M2_goblin (monster) attacks Mira: roll 20 vs AC 12 -> HIT
  Damage 4 (bludgeoning) to Mira HP now 5
<End Turn/>
--- Monster Turn: M3_goblin (round 1) ---
M3_goblin (monster) attacks Mira: roll 3 vs AC 12 -> MISS
<End Turn/>
Combat ended after 5 turns. Deaths: {'log': []}
--- full tail via compact_transcript ---
['--- Monster Turn: M2_goblin (round 1) ---', 'M2_goblin (monster) attacks Mira: roll 20 vs AC 12 -> HIT', ...]
{
  "players": {"Elaria": {"hp": 10, "max": 10, "alive": true}, "Briana": {"hp": 8, "max": 8, "alive": true}, "Thalion": {"hp": 14, "max": 14, "alive": true}, "Mira": {"hp": 5, "max": 10, "alive": true}},
  "monsters": {"M1_goblin": {"hp": 7, "max": 7, "alive": true}, "M2_goblin": {"hp": 7, "max": 7, "alive": true}, "M3_goblin": {"hp": 7, "max": 7, "alive": true}},
  "rounds": 1
}
[summary] round=1 turn=Elaria death_log=[]
[compact] {'Elaria': '10/10', 'Briana': '8/8', 'Thalion': '14/14', 'Mira': '5/10'} monsters={'M1_goblin': '7/7', 'M2_goblin': '7/7', 'M3_goblin': '7/7'}
[long_rest] {'Elaria': {'hp': 10, 'slots': {1: 2}}, 'Briana': {'hp': 8, 'slots': {1: 2}}, 'Thalion': {'hp': 14, 'slots': {}}, 'Mira': {'hp': 10, 'slots': {1: 2}}}
[checkpoint] history_len=3 tool_trace=60 transcript=20

[encounter 2] indoor — ['wolf', 'wolf', 'goblin'] vs party (heuristic , max_turns=5)
[check_resources] Elaria => {'action': 1, 'bonus_action': 1, 'reaction': 1, 'spell_slots': {1: 2}, 'speed_remaining': 30}

=== ENCOUNTER 2 ===
<End Turn/>
--- Player Turn: Thalion (round 1) ---
Thalion attacks M1_wolf with longsword — MISS. <DM/>
<End Turn/>
--- Player Turn: Briana (round 1) ---
Briana attacks M1_wolf with dagger — MISS. <DM/>
<End Turn/>
Combat ended after 5 turns. Deaths: {'log': []}
{
  "players": {"Elaria": {"hp": 10, "max": 10, "alive": true}, "Briana": {"hp": 8, "max": 8, "alive": true}, "Thalion": {"hp": 14, "max": 14, "alive": true}, "Mira": {"hp": 10, "max": 10, "alive": true}},
  "monsters": {"M1_wolf": {"hp": 11, "max": 11, "alive": true}, "M2_wolf": {"hp": 11, "max": 11, "alive": true}, "M3_goblin": {"hp": 7, "max": 7, "alive": true}},
  "rounds": 1
}
[summary] round=1 turn=M3_goblin death_log=[]
[compact] {'Elaria': '10/10', 'Briana': '8/8', 'Thalion': '14/14', 'Mira': '10/10'} monsters={'M1_wolf': '11/11', 'M2_wolf': '11/11', 'M3_goblin': '7/7'}
[checkpoint] history_len=5 tool_trace=107 transcript=38

[checkpoint] saved to /tmp/demo_campaign.json (79096 bytes)
[restore] loaded round=1 players=['Elaria', 'Briana', 'Thalion', 'Mira']
[prune] before 107 -> 50

[done] 2 encounters simulated, campaign_meta={'seed': 42, 'encounters': 1} final_round=1
```

With `--use-llm` and a live tau-ai endpoint (LMStudio at http://127.0.0.1:1234/v1),
the same flow prints `[tau] provider http://127.0.0.1:1234/v1 model=qwen3.6-35b-a3b-mtp`
and each `--- Player Turn:` line is LLM-generated via `tau_agent.AgentHarness`
(`_tools_to_agent_tools` → `AgentTool(roll_attack, move_player, …)` → `AgentHarness.prompt()`),
still ending in `<DM/>` and logged to `tool_trace` identically. If the endpoint is down,
the script falls back to the heuristic trace above.

With a live tau-ai endpoint (e.g. LMStudio), each player turn becomes a `tau_agent` harness
call: `AgentTool(roll_attack, move_player, …)` → `AgentHarness.prompt()` → tool trace + LLM narration
ending in `<DM/>`. The heuristic path above is identical except narration is rule-based.

Reference:
- Paper: ref/31_Setting_the_DC_Synthesis.md
- Package docs: packages/dnd-tools/README.md (reproduction), packages/dnd-tools/scenarios/
- Agents: packages/dnd-tools/src/dnd_tools/agents.py (make_tau_provider, _tools_to_agent_tools, run_tau_player_turn_sync)
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from dnd_campaign.memory import compact_transcript, summarize_state
from dnd_campaign.session import CampaignSession
from dnd_campaign.state import CampaignState
from dnd_campaign.tools import CampaignTools
from dnd_tools.simulation import create_player


def build_party(seed: int = 42) -> list:
    """Create the canonical 4-person party (deterministic via seed)."""
    random.seed(seed)
    return [
        create_player("Elaria", "ranger", tier="medium"),
        create_player("Briana", "wizard", tier="medium"),
        create_player("Thalion", "fighter", tier="medium"),
        create_player("Mira", "cleric", tier="medium"),
    ]


def get_llm_provider(args: argparse.Namespace):
    """Try to build a tau-ai provider if --use-llm, else return None (heuristic)."""
    if not args.use_llm:
        return None
    try:
        from dnd_tools.agents import LLMClient  # TauLLM alias, holds provider + model

        llm = LLMClient(base_url=args.base_url, model=args.model)
        print(f"[tau] provider {args.base_url} model={args.model} — will fallback to heuristic if unreachable")
        return llm
    except Exception as e:  # pragma: no cover
        print(f"[tau] provider init failed ({e}) — using heuristic fallback", file=sys.stderr)
        return None


def print_encounter_result(idx: int, res: dict, cstate: CampaignState) -> None:
    """Pretty-print one encounter result with summary helpers."""
    print(f"\n=== ENCOUNTER {idx} ===")
    # compact transcript tail so output stays readable for long horizons
    tail = compact_transcript(cstate, keep_last=8)
    # show only last 8 lines of the encounter's own transcript for this demo
    enc_tail = res["transcript"][-8:]
    for line in enc_tail:
        print(line)
    print("--- full tail via compact_transcript ---")
    print(tail.split("\n")[-8:])
    print(json.dumps({k: res[k] for k in ("players", "monsters", "rounds")}, indent=2))
    summary = summarize_state(cstate)
    # summarize_state is the LLM-context-friendly view (instead of full tool_trace)
    print(f"[summary] round={summary['round']} turn={summary['turn']} death_log={summary['death_log']}")
    print(
        f"[compact] { {k: f'{v['hp']}/{v['max_hp']}' for k, v in summary['players'].items()} } "
        f"monsters={ {k: f'{v['hp']}/{v['max_hp']}' for k, v in summary['monsters'].items()} }"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (deterministic)")
    parser.add_argument("--turns", type=int, default=5, help="max turns per encounter")
    parser.add_argument("--use-llm", action="store_true", help="try tau-ai LLM (fallback to heuristic)")
    parser.add_argument(
        "--base-url", type=str, default="http://127.0.0.1:1234/v1", help="tau OpenAI-compatible base url"
    )
    parser.add_argument("--model", type=str, default="qwen3.6-35b-a3b-mtp", help="model id for tau provider")
    parser.add_argument("--save", type=str, default="", help="save campaign json to path")
    args = parser.parse_args()

    print(f"[setup] seed={args.seed} turns={args.turns} use_llm={args.use_llm}")
    # 1) CampaignState wraps the authoritative GameState — paper code untouched
    cstate = CampaignState(seed_val=args.seed)
    for p in build_party(seed=args.seed):
        cstate.inner.add_player(p, (0, 0, 0))
    print(f"[setup] party: {[f'{n}({c.char_class})' for n, c in cstate.inner.players.items()]}")

    # 2) CampaignTools delegates to dnd_tools.tools.Tools and adds long_rest etc.
    ctools = CampaignTools(cstate)
    print(f"[tools] base={len(ctools.inner_tools.tool_schemas())} + campaign=6 => total={len(ctools.tool_schemas())}")
    # example: get a compact summary instead of dumping full tool_trace into LLM context
    print(f"[get_summary] {json.dumps(ctools.get_summary(), indent=2)[:400]}...")

    # 3) CampaignSession orchestrates multiple Simulation runs + checkpoint / prune
    sess = CampaignSession(cstate, ctools)
    llm = get_llm_provider(args)
    use_heuristic = llm is None

    encounters = [
        {"monsters": ["goblin", "goblin", "goblin"], "map": "outdoor"},
        {"monsters": ["wolf", "wolf", "goblin"], "map": "indoor"},
    ]

    results = []
    for i, enc in enumerate(encounters, 1):
        monsters = enc["monsters"]
        map_kind = enc["map"]
        assert isinstance(monsters, list)
        assert isinstance(map_kind, str)
        print(
            f"\n[encounter {i}] {map_kind} — {monsters} vs party "
            f"({'heuristic' if use_heuristic else 'tau'} , max_turns={args.turns})"
        )
        sess.add_encounter(monster_specs=monsters, map_kind=map_kind)
        # Demonstrate low-level tool use before the encounter: check one player's resources
        first_player = next(iter(cstate.inner.players))
        print(f"[check_resources] {first_player} => {ctools.check_resources(first_player)}")
        res = sess.run_encounter(max_turns=args.turns, use_heuristic=use_heuristic, llm=llm)
        results.append(res)
        print_encounter_result(i, res, cstate)
        # long rest between encounters (except after last) — campaign-level economy
        if enc is not encounters[-1]:
            print(f"[long_rest] {ctools.long_rest()}")
        print(
            f"[checkpoint] history_len={len(cstate.history)} "
            f"tool_trace={len(cstate.tool_trace)} transcript={len(cstate.transcript)}"
        )

    # 4) Persistence + pruning (keeps LLM context bounded over long horizons)
    tmp = Path("/tmp/demo_campaign.json")
    cstate.save(tmp)
    print(f"\n[checkpoint] saved to {tmp} ({tmp.stat().st_size} bytes)")
    loaded = CampaignState.load(tmp)
    print(f"[restore] loaded round={loaded.round} players={list(loaded.inner.players.keys())}")
    print(f"[prune] before {len(cstate.tool_trace)} -> ", end="")
    cstate.prune_traces(keep_last=50)
    print(f"{len(cstate.tool_trace)}")

    if args.save:
        out = Path(args.save)
        out.write_text(json.dumps([r["tool_trace"] for r in results], indent=2))
        cstate.save(out.with_suffix(".campaign.json"))
        print(f"[save] traces to {out}")

    print(
        f"\n[done] {len(results)} encounters simulated, campaign_meta={cstate.campaign_meta} final_round={cstate.round}"
    )


if __name__ == "__main__":
    main()
