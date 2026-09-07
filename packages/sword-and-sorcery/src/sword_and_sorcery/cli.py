"""CLI for sword-and-sorcery — scene + campaign demos, tau LLM optional."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from .agents import LLMClient
from .session import SnSSession
from .simulation import SnSSimulation, create_sns_monster, create_sns_player, initialize_sns_scene
from .state import SnSCampaignState, SnSState
from .tools import SnSCampaignTools, SnSTools


def cmd_scene(args: argparse.Namespace) -> None:
    random.seed(args.seed)
    state = SnSState(seed_val=args.seed)
    players = [
        create_sns_player("Gunther the Brave", ancestry="Human", background="Soldier", sns=5),
        create_sns_player("Lyriel Starweave", ancestry="Elf", background="Sage", sns=2),
        create_sns_player("Borin Ironfoot", ancestry="Dwarf", background="Noble", sns=4),
        create_sns_player("Pip Quickfingers", ancestry="Gnome", background="Thief", sns=3),
    ]
    monsters = [
        create_sns_monster("Goblin1", threat="Easy"),
        create_sns_monster("Goblin2", threat="Easy"),
        create_sns_monster("Ogre", threat="Medium"),
    ]
    initialize_sns_scene(state, players, monsters, map_kind="outdoor", seed=args.seed)
    tools = SnSTools(state)
    llm = LLMClient(base_url=args.base_url, model=args.model) if args.use_llm else None
    sim = SnSSimulation(state, tools, llm=llm, use_heuristic=not args.use_llm, max_turns=args.turns)
    result = sim.run()
    print("\n=== TRANSCRIPT ===")
    for line in result["transcript"]:
        print(line)
    print("\n=== RESULT ===")
    print(
        json.dumps(
            {"players": result["players"], "monsters": result["monsters"], "adventure": result["adventure"]}, indent=2
        )
    )
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
    cstate = SnSCampaignState(seed_val=args.seed)
    players = [
        create_sns_player("Gunther the Brave", ancestry="Human", background="Soldier", sns=5),
        create_sns_player("Lyriel Starweave", ancestry="Elf", background="Sage", sns=2),
        create_sns_player("Borin Ironfoot", ancestry="Dwarf", background="Noble", sns=4),
        create_sns_player("Pip Quickfingers", ancestry="Gnome", background="Thief", sns=3),
    ]
    for p in players:
        cstate.inner.add_player(p, (0, 0, 0))
    ctools = SnSCampaignTools(cstate)
    sess = SnSSession(cstate, ctools)
    llm = LLMClient(base_url=args.base_url, model=args.model) if args.use_llm else None
    scenes = [
        {"monsters": [("Goblin1", "Easy"), ("Goblin2", "Easy"), ("Goblin3", "Easy")], "map": "outdoor"},
        {"monsters": [("Cultist1", "Medium"), ("Cultist2", "Medium")], "map": "indoor"},
        {"monsters": [("Necromancer", "Hard"), ("Skeleton1", "Easy")], "map": "indoor"},
    ]
    results = sess.run_campaign(scenes, max_turns_per_scene=args.turns, use_heuristic=not args.use_llm, llm=llm)
    for i, r in enumerate(results, 1):
        print(f"\n=== SCENE {i} ===")
        for line in r["transcript"][-16:]:
            print(line)
        print(json.dumps({"players": r["players"], "monsters": r["monsters"], "rounds": r["rounds"]}, indent=2))
    summary = ctools.get_summary()
    print("\n=== CAMPAIGN SUMMARY ===")
    print(json.dumps(summary, indent=2))
    if args.save:
        out = Path(args.save)
        out.write_text(json.dumps([r["tool_trace"] for r in results], indent=2))
        cstate.save(Path(args.save).with_suffix(".campaign.json"))
        print(f"saved to {args.save}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="sword-and-sorcery")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_scene = sub.add_parser("scene", help="Run a single S&S scene (heuristic or LLM)")
    p_scene.add_argument("--seed", type=int, default=42)
    p_scene.add_argument("--turns", type=int, default=10, help="max turns")
    p_scene.add_argument("--use-llm", action="store_true", help="Use Tau LLM (LMStudio) instead of heuristic")
    p_scene.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p_scene.add_argument("--model", default="qwen3.6-35b-a3b-mtp")
    p_scene.add_argument("--save", type=str, default="")

    p_camp = sub.add_parser("campaign", help="Run 3-scene campaign demo")
    p_camp.add_argument("--seed", type=int, default=42)
    p_camp.add_argument("--turns", type=int, default=10, help="max turns per scene")
    p_camp.add_argument("--use-llm", action="store_true", help="Use Tau LLM")
    p_camp.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p_camp.add_argument("--model", default="qwen3.6-35b-a3b-mtp")
    p_camp.add_argument("--save", type=str, default="")

    p_gen = sub.add_parser("gen-scenarios", help="Generate S&S scenarios")
    p_gen.add_argument("--seed", type=int, default=42)
    p_gen.add_argument("--out", type=str, default="scenarios")

    p_run = sub.add_parser("run-scenario", help="Run a scenario file")
    p_run.add_argument("path", type=str)
    p_run.add_argument("--turns", type=int, default=10)
    p_run.add_argument("--use-llm", action="store_true")
    p_run.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p_run.add_argument("--model", default="qwen3.6-35b-a3b-mtp")

    args = parser.parse_args()
    if args.cmd == "scene":
        cmd_scene(args)
    elif args.cmd == "campaign":
        cmd_campaign(args)
    elif args.cmd == "gen-scenarios":
        from .simulation import generate_sns_scenarios

        paths = generate_sns_scenarios(seed=args.seed, out_dir=args.out)
        print(f"Generated {len(paths)} scenarios in {args.out}")
        for p in paths:
            print(p)
    elif args.cmd == "run-scenario":
        from .simulation import load_sns_scenario

        state, tools = load_sns_scenario(args.path)
        llm = LLMClient(base_url=args.base_url, model=args.model) if args.use_llm else None
        sim = SnSSimulation(state, tools, llm=llm, use_heuristic=not args.use_llm, max_turns=args.turns)
        res = sim.run()
        print("\n".join(res["transcript"]))
        print(json.dumps({"players": res["players"], "monsters": res["monsters"]}, indent=2))


if __name__ == "__main__":
    main()
