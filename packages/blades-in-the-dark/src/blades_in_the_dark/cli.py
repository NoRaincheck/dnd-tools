"""CLI for blades — score + campaign demos, tau LLM optional."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from .agents import LLMClient
from .session import BladesSession
from .simulation import BladesSimulation, create_blades_player, initialize_blades_score
from .state import BladesCampaignState, BladesState
from .tools import BladesCampaignTools, BladesTools


def cmd_scene(args: argparse.Namespace) -> None:
    random.seed(args.seed)
    state = BladesState(seed_val=args.seed)
    players = [
        create_blades_player("Silas", playbook="Lurk", actions={"Prowl": 2, "Finesse": 1}),
        create_blades_player("Locke", playbook="Spider", actions={"Consort": 2, "Sway": 1}),
        create_blades_player("Thorn", playbook="Whisper", actions={"Attune": 2, "Study": 1}),
        create_blades_player("Vex", playbook="Cutter", actions={"Skirmish": 2, "Wreck": 1}),
    ]
    initialize_blades_score(
        state,
        players,
        map_kind="indoor",
        seed=args.seed,
        clocks=[("Score Clock", 6, "obstacle"), ("Alert", 4, "danger")],
    )
    tools = BladesTools(state)
    llm = LLMClient(base_url=args.base_url, model=args.model) if args.use_llm else None
    sim = BladesSimulation(
        state,
        tools,
        llm=llm,
        use_heuristic=not args.use_llm,
        max_turns=args.turns,
        plan="infiltration",
        detail="quietly through the canal",
    )
    result = sim.run()
    print("\n=== TRANSCRIPT ===")
    for line in result["transcript"]:
        print(line)
    print("\n=== RESULT ===")
    print(json.dumps({"players": result["players"], "clocks": result["clocks"]}, indent=2))
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
    cstate = BladesCampaignState(seed_val=args.seed)
    players = [
        create_blades_player("Silas", playbook="Lurk", actions={"Prowl": 2, "Finesse": 1}),
        create_blades_player("Locke", playbook="Spider", actions={"Consort": 2, "Sway": 1}),
        create_blades_player("Thorn", playbook="Whisper", actions={"Attune": 2, "Study": 1}),
        create_blades_player("Vex", playbook="Cutter", actions={"Skirmish": 2, "Wreck": 1}),
    ]
    for p in players:
        cstate.inner.add_player(p, (0, 0, 0))
    ctools = BladesCampaignTools(cstate)
    sess = BladesSession(cstate, ctools)
    llm = LLMClient(base_url=args.base_url, model=args.model) if args.use_llm else None
    scores = [
        {
            "plan": "infiltration",
            "detail": "through the canal",
            "clocks": [("Infiltrate", 6, "obstacle"), ("Alert", 4, "danger")],
        },
        {
            "plan": "deception",
            "detail": "as Bluecoats",
            "clocks": [("Ledger", 4, "obstacle"), ("Suspicion", 6, "danger")],
        },
        {"plan": "assault", "detail": "front door", "clocks": [("Vault", 8, "obstacle"), ("Doom", 6, "danger")]},
    ]
    results = sess.run_campaign(scores, max_turns_per_score=args.turns, use_heuristic=not args.use_llm, llm=llm)
    for i, r in enumerate(results, 1):
        print(f"\n=== SCORE {i} ===")
        for line in r["transcript"][-12:]:
            print(line)
        print(json.dumps({"players": r["players"], "clocks": r["clocks"], "rounds": r["rounds"]}, indent=2))
    summary = ctools.get_summary()
    print("\n=== CAMPAIGN SUMMARY ===")
    print(json.dumps(summary, indent=2))
    if args.save:
        out = Path(args.save)
        out.write_text(json.dumps([r["tool_trace"] for r in results], indent=2))
        cstate.save(Path(args.save).with_suffix(".campaign.json"))
        print(f"saved to {args.save}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="blades")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_scene = sub.add_parser("scene", help="Run a single Blades score (heuristic or LLM)")
    p_scene.add_argument("--seed", type=int, default=42)
    p_scene.add_argument("--turns", type=int, default=10, help="max turns")
    p_scene.add_argument("--use-llm", action="store_true", help="Use Tau LLM (LMStudio) instead of heuristic")
    p_scene.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p_scene.add_argument("--model", default="qwen3.6-35b-a3b-mtp")
    p_scene.add_argument("--save", type=str, default="")

    p_camp = sub.add_parser("campaign", help="Run 3-score campaign demo")
    p_camp.add_argument("--seed", type=int, default=42)
    p_camp.add_argument("--turns", type=int, default=10, help="max turns per score")
    p_camp.add_argument("--use-llm", action="store_true", help="Use Tau LLM")
    p_camp.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p_camp.add_argument("--model", default="qwen3.6-35b-a3b-mtp")
    p_camp.add_argument("--save", type=str, default="")

    p_gen = sub.add_parser("gen-scenarios", help="Generate blades scenarios")
    p_gen.add_argument("--seed", type=int, default=42)
    p_gen.add_argument("--out", type=str, default="scenarios")

    args = parser.parse_args()
    if args.cmd == "scene":
        cmd_scene(args)
    elif args.cmd == "campaign":
        cmd_campaign(args)
    elif args.cmd == "gen-scenarios":
        from .simulation import generate_blades_scenarios

        paths = generate_blades_scenarios(seed=args.seed, out_dir=args.out)
        print(f"Generated {len(paths)} scenarios in {args.out}")
        for p in paths:
            print(p)


if __name__ == "__main__":
    main()
