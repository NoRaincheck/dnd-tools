"""CLI — run demo simulation, optionally with LLM via Tau (LMStudio/OpenAI-compatible)."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from .agents import LLMClient
from .metrics import evaluate_all
from .simulation import (
    Simulation,
    create_monster,
    create_player,
    generate_scenarios,
    initialize_encounter,
    load_scenario,
)
from .state import GameState
from .tools import Tools


def cmd_demo(args):
    # simple demo without LLM or with heuristic / Tau
    seed = args.seed
    random.seed(seed)
    state = GameState(seed_val=seed)
    # 4 players vs 4 goblins as in paper Fig5
    players = [
        create_player("Elaria", "ranger", tier="medium"),
        create_player("Briana", "wizard", tier="medium"),
        create_player("Thalion", "fighter", tier="medium"),
        create_player("Mira", "cleric", tier="medium"),
    ]
    monsters = [create_monster(f"Goblin {i + 1}", "goblin") for i in range(4)]
    initialize_encounter(state, players, monsters, map_kind="outdoor", seed=seed)
    tools = Tools(state)
    llm = None
    use_heuristic = True
    if args.use_llm:
        # Tau-native OpenAI-compatible provider (LMStudio default) — no subprocess, pure python
        llm = LLMClient(base_url=args.base_url, model=args.model)
        use_heuristic = False
        print(f"[using Tau LLM {args.model} at {args.base_url}]")
    sim = Simulation(state, tools, llm=llm, use_heuristic=use_heuristic, max_turns=args.turns)
    result = sim.run()
    print("\n=== TRANSCRIPT ===")
    for line in result["transcript"]:
        print(line)
    print("\n=== RESULT ===")
    print(
        json.dumps(
            {
                "players": result["players"],
                "monsters": result["monsters"],
                "death": result["death"],
            },
            indent=2,
        )
    )
    print("\n=== METRICS (6 axes) ===")
    metrics = evaluate_all(result["transcript"], result["tool_trace"])
    print(json.dumps(metrics, indent=2))
    # optionally save
    if args.save:
        out = Path(args.save)
        out.write_text(
            json.dumps(
                {
                    "transcript": result["transcript"],
                    "tool_trace": result["tool_trace"],
                    "metrics": metrics,
                    "result": result,
                },
                indent=2,
            )
        )
        print(f"\nSaved to {out}")
    # also show tool trace efficiency
    print(f"\nTool Calls: {len(result['tool_trace'])}")


def main():
    parser = argparse.ArgumentParser(prog="dnd-tools")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_demo = sub.add_parser("demo", help="Run a demo encounter")
    p_demo.add_argument("--seed", type=int, default=42)
    p_demo.add_argument("--turns", type=int, default=10, help="max turns per paper (10)")
    p_demo.add_argument(
        "--use-llm",
        action="store_true",
        help="Use Tau LLM (LMStudio/OpenAI-compatible) instead of heuristic",
    )
    p_demo.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p_demo.add_argument("--model", default="qwen3.6-35b-a3b-mtp")
    p_demo.add_argument("--save", type=str, default="")

    p_scen = sub.add_parser("gen-scenarios", help="Generate 27 seeded scenarios (3x3x3)")
    p_scen.add_argument("--seed", type=int, default=42)
    p_scen.add_argument("--out", type=str, default="scenarios")

    p_run = sub.add_parser("run-scenario", help="Run a scenario file")
    p_run.add_argument("path", type=str)
    p_run.add_argument("--use-llm", action="store_true", help="Use Tau LLM instead of heuristic")
    p_run.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p_run.add_argument("--model", default="qwen3.6-35b-a3b-mtp")
    p_run.add_argument("--turns", type=int, default=10)

    p_eval = sub.add_parser("eval", help="Evaluate all scenarios in a dir (heuristic or LLM)")
    p_eval.add_argument("scenarios_dir", type=str, help="dir containing scenario_*.json")
    p_eval.add_argument("--use-llm", action="store_true", help="Use Tau LLM")
    p_eval.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p_eval.add_argument("--model", default="qwen3.6-35b-a3b-mtp")
    p_eval.add_argument("--turns", type=int, default=10)
    p_eval.add_argument("--out", type=str, default="")

    args = parser.parse_args()
    if args.cmd == "demo":
        cmd_demo(args)
    elif args.cmd == "gen-scenarios":
        paths = generate_scenarios(seed=args.seed, out_dir=args.out)
        print(f"Generated {len(paths)} scenarios in {args.out}")
        for p in paths:
            print(p)
    elif args.cmd == "run-scenario":
        state, tools = load_scenario(args.path)
        llm = LLMClient(base_url=args.base_url, model=args.model) if args.use_llm else None
        sim = Simulation(state, tools, llm=llm, use_heuristic=not args.use_llm, max_turns=args.turns)
        res = sim.run()
        print("\n".join(res["transcript"]))
        print(json.dumps(evaluate_all(res["transcript"], res["tool_trace"]), indent=2))
    elif args.cmd == "eval":
        import glob

        files = sorted(glob.glob(str(Path(args.scenarios_dir) / "*.json")))
        print(f"Evaluating {len(files)} scenarios ({'LLM ' + args.model if args.use_llm else 'heuristic'})")
        all_metrics = []
        for f in files:
            state, tools = load_scenario(f)
            llm = LLMClient(base_url=args.base_url, model=args.model) if args.use_llm else None
            sim = Simulation(
                state,
                tools,
                llm=llm,
                use_heuristic=not args.use_llm,
                max_turns=args.turns,
            )
            res = sim.run()
            m = evaluate_all(res["transcript"], res["tool_trace"])
            all_metrics.append(m)
            print(
                f"{Path(f).name}: O={m['tactical_optimality']['O']:.3f} A={m['acting_quality']['A']:.3f} err={m['function_usage']['incorrect_function_pct']:.1f}%"
            )
        if all_metrics:
            avg_O = sum(m["tactical_optimality"]["O"] for m in all_metrics) / len(all_metrics)
            avg_A = sum(m["acting_quality"]["A"] for m in all_metrics) / len(all_metrics)
            avg_err = sum(m["function_usage"]["incorrect_function_pct"] for m in all_metrics) / len(all_metrics)
            print(f"\nAggregated — O {avg_O:.3f} | A {avg_A:.3f} | func_err {avg_err:.1f}% | n={len(all_metrics)}")
            if args.out:
                Path(args.out).write_text(json.dumps(all_metrics, indent=2))
                print(f"Saved metrics to {args.out}")


if __name__ == "__main__":
    main()
