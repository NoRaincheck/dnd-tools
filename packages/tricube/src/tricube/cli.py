"""CLI for tricube — scene + campaign demos, tau LLM optional."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from .agents import LLMClient
from .session import TricubeSession
from .simulation import TricubeSimulation, create_tricube_monster, create_tricube_player, initialize_tricube_scene
from .state import TricubeCampaignState, TricubeState
from .tools import TricubeCampaignTools, TricubeTools


def cmd_scene(args: argparse.Namespace) -> None:
    random.seed(args.seed)
    state = TricubeState(seed_val=args.seed)
    players = [
        create_tricube_player("Lyra", trait="agile", concept="ranger", perk="keen eye", quirk="reckless"),
        create_tricube_player("Borin", trait="brawny", concept="knight", perk="shield master", quirk="stubborn"),
        create_tricube_player("Mira", trait="crafty", concept="mage", perk="pyromancy", quirk="arrogant"),
        create_tricube_player("Fenn", trait="crafty", concept="scholar", perk="lore", quirk="timid"),
    ]
    monsters = [
        create_tricube_monster("Goblin1", trait="agile", concept="goblin", rank=1),
        create_tricube_monster("Goblin2", trait="agile", concept="goblin", rank=1),
        create_tricube_monster("Ogre", trait="brawny", concept="ogre", rank=2, is_boss=False),
    ]
    initialize_tricube_scene(state, players, monsters, map_kind="outdoor", seed=args.seed)
    tools = TricubeTools(state)
    llm = LLMClient(base_url=args.base_url, model=args.model) if args.use_llm else None
    sim = TricubeSimulation(state, tools, llm=llm, use_heuristic=not args.use_llm, max_turns=args.turns)
    result = sim.run()
    print("\n=== TRANSCRIPT ===")
    for line in result["transcript"]:
        print(line)
    print("\n=== RESULT ===")
    print(json.dumps({"players": result["players"], "effort_pools": result["effort_pools"]}, indent=2))
    print(f"\nTool Calls: {len(result['tool_trace'])}")
    if args.save:
        out = Path(args.save)
        out.write_text(
            json.dumps(
                {"transcript": result["transcript"], "tool_trace": result["tool_trace"], "result": result}, indent=2
            )
        )
        print(f"Saved to {out}")


def cmd_campaign(args: argparse.Namespace) -> None:
    random.seed(args.seed)
    cstate = TricubeCampaignState(seed_val=args.seed)
    # seed initial players for campaign
    players = [
        create_tricube_player("Lyra", trait="agile", concept="ranger", perk="keen eye", quirk="reckless"),
        create_tricube_player("Borin", trait="brawny", concept="knight", perk="shield master", quirk="stubborn"),
        create_tricube_player("Mira", trait="crafty", concept="mage", perk="pyromancy", quirk="arrogant"),
        create_tricube_player("Fenn", trait="crafty", concept="scholar", perk="lore", quirk="timid"),
    ]
    for p in players:
        cstate.inner.add_player(p, (0, 0, 0))
    ctools = TricubeCampaignTools(cstate)
    sess = TricubeSession(cstate, ctools)
    # optionally use llm for scenes
    llm = LLMClient(base_url=args.base_url, model=args.model) if args.use_llm else None
    scenes = [
        {
            "monsters": [
                ("Goblin1", "agile", 1, False),
                ("Goblin2", "agile", 1, False),
                ("Goblin3", "agile", 1, False),
            ],
            "map": "outdoor",
        },
        {"monsters": [("Wolf1", "brawny", 1, False), ("Wolf2", "brawny", 1, False)], "map": "indoor"},
        {
            "monsters": [("Ogre", "brawny", 2, True), ("Goblin1", "agile", 1, False)],
            "map": "indoor",
            "effort_pools": {"Horde": 4},
        },
    ]
    results = sess.run_campaign(scenes, max_turns_per_scene=args.turns, use_heuristic=not args.use_llm, llm=llm)
    for i, r in enumerate(results, 1):
        print(f"\n=== SCENE {i} ===")
        for line in r["transcript"][-12:]:
            print(line)
        print(json.dumps({"players": r["players"], "effort_pools": r["effort_pools"], "rounds": r["rounds"]}, indent=2))
    # summary via tool
    summary = ctools.get_summary()
    print("\n=== CAMPAIGN SUMMARY ===")
    print(json.dumps(summary, indent=2))
    if args.save:
        out = Path(args.save)
        out.write_text(json.dumps([r["tool_trace"] for r in results], indent=2))
        cstate.save(Path(args.save).with_suffix(".campaign.json"))
        print(f"saved to {args.save}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="tricube")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_scene = sub.add_parser("scene", help="Run a single Tricube scene (heuristic or LLM)")
    p_scene.add_argument("--seed", type=int, default=42)
    p_scene.add_argument("--turns", type=int, default=12, help="max turns")
    p_scene.add_argument("--use-llm", action="store_true", help="Use Tau LLM (LMStudio) instead of heuristic")
    p_scene.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p_scene.add_argument("--model", default="qwen3.6-35b-a3b-mtp")
    p_scene.add_argument("--save", type=str, default="")

    p_camp = sub.add_parser("campaign", help="Run 3-scene campaign demo")
    p_camp.add_argument("--seed", type=int, default=42)
    p_camp.add_argument("--turns", type=int, default=12, help="max turns per scene")
    p_camp.add_argument("--use-llm", action="store_true", help="Use Tau LLM")
    p_camp.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p_camp.add_argument("--model", default="qwen3.6-35b-a3b-mtp")
    p_camp.add_argument("--save", type=str, default="")

    p_gen = sub.add_parser("gen-scenarios", help="Generate tricube scenarios")
    p_gen.add_argument("--seed", type=int, default=42)
    p_gen.add_argument("--out", type=str, default="scenarios")

    args = parser.parse_args()
    if args.cmd == "scene":
        cmd_scene(args)
    elif args.cmd == "campaign":
        cmd_campaign(args)
    elif args.cmd == "gen-scenarios":
        from .simulation import generate_tricube_scenarios

        paths = generate_tricube_scenarios(seed=args.seed, out_dir=args.out)
        print(f"Generated {len(paths)} scenarios in {args.out}")
        for p in paths:
            print(p)


if __name__ == "__main__":
    main()
