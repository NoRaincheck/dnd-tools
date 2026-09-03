"""Minimal encounter — dnd-tools paper core without campaign layer.

Shows the low-level API that `full_campaign.py` wraps. Use this when you want a single
deterministic fight (e.g. for unit tests or paper reproduction), not a multi-encounter
campaign.

Run:
    uv run python scripts/minimal_encounter.py --seed 42 --turns 5
    uv run python scripts/minimal_encounter.py --seed 42 --turns 5 --use-llm

Example output (seed 42, 1 encounter, 5 turns, heuristic):
```
[setup] GameState seed=42 map=20x20
[party] Elaria(ranger) vs Goblin 1(humanoid)
[tools] 39 tools available — e.g. roll_attack, check_valid_attack_line, move_player
[check] distance=30ft LoS=False speed=30

[transcript]
Initiative: [{'name': 'Elaria', 'initiative': 4}, {'name': 'Goblin 1', 'initiative': 3}]
<End Turn/>
--- Player Turn: Elaria (round 1) ---
Elaria attacks Goblin 1 with short bow — MISS. <DM/>
<End Turn/>
--- Monster Turn: Goblin 1 (round 1) ---
Goblin 1 (monster) attacks Elaria: roll 9 vs AC 10 -> MISS
<End Turn/>
--- Player Turn: Elaria (round 2) ---
Elaria attacks Goblin 1 with short bow — MISS. <DM/>
<End Turn/>
Combat ended after 5 turns. Deaths: {'log': []}

[result] players={'Elaria': {'hp': 10, 'max': 10, 'alive': True}} monsters={'Goblin 1': {'hp': 7, 'max': 7, 'alive': True}}
[visualize]
......#...#.........
....................
...
[metrics] tool_calls=43 rounds=3
```

With `--use-llm`, the `Elaria` turn is driven by tau-ai (`make_tau_provider` →
`_tools_to_agent_tools` → `AgentHarness`), same trace shape but LLM narration.
"""

from __future__ import annotations

import argparse
import random

from dnd_tools.simulation import create_monster, create_player, initialize_encounter
from dnd_tools.state import GameState
from dnd_tools.tools import Tools


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--turns", type=int, default=5)
    parser.add_argument("--use-llm", action="store_true", help="try tau-ai LLM (fallback to heuristic)")
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", type=str, default="qwen3.6-35b-a3b-mtp")
    args = parser.parse_args()

    random.seed(args.seed)
    state = GameState(seed_val=args.seed, map_w=20, map_h=20)
    # single player vs single monster — simplest scene
    player = create_player("Elaria", "ranger", tier="medium")
    monster = create_monster("Goblin 1", "goblin")
    initialize_encounter(state, [player], [monster], map_kind="outdoor", seed=args.seed)
    tools = Tools(state)
    print(f"[setup] GameState seed={args.seed} map={state.map_size()[0]}x{state.map_size()[1]}")
    print(f"[party] {player.name}({player.char_class}) vs {monster.name}({monster.monster_type})")
    print(
        f"[tools] {len(tools.tool_schemas())} tools available — e.g. roll_attack, check_valid_attack_line, move_player"
    )
    # demo low-level tool: check distance + LoS before combat
    try:
        d = state.distance_feet(player.name, monster.name)
        los = tools.check_valid_attack_line(player.name, monster.name)
        print(f"[check] distance={d:.0f}ft LoS={los} speed={player.speed_remaining}")
    except Exception as e:
        print(f"[check] {e}")

    # choose heuristic vs tau
    use_heuristic = True
    llm = None
    if args.use_llm:
        try:
            from dnd_tools.agents import LLMClient

            llm = LLMClient(base_url=args.base_url, model=args.model)
            use_heuristic = False
            print(f"[tau] provider {args.base_url} model={args.model}")
        except Exception as e:
            print(f"[tau] fallback to heuristic ({e})")

    # run the paper's Simulation loop (Fig. 1: query → move → validate → resolve → bookkeep)
    from dnd_tools.simulation import Simulation

    sim = Simulation(state, tools, llm=llm, use_heuristic=use_heuristic, max_turns=args.turns)
    res = sim.run()
    print("\n[transcript]")
    for line in res["transcript"]:
        print(line)
    print(f"\n[result] players={res['players']} monsters={res['monsters']}")
    print("\n[visualize]")
    print(tools.visualize_map()[:500])
    print(f"\n[metrics] tool_calls={len(res['tool_trace'])} rounds={res['rounds']}")


if __name__ == "__main__":
    main()
