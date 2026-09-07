"""CLI for triple-o — demos of middleware-driven creativity."""

from __future__ import annotations

import argparse


def cmd_demo(args: argparse.Namespace) -> None:
    from .core import TripleO
    from .middleware import TripleOMiddleware, make_triple_o_provider
    from .tools import TripleOTools

    engine = TripleO(seed=args.seed)
    tools = TripleOTools(engine)
    mw = TripleOMiddleware(engine, tools)

    if args.use_llm:
        provider = make_triple_o_provider(base_url=args.base_url)
        scenarios = [
            ("Lyra", ["keen eye", "reckless"], "Goblin horde blocks the gate; party must breach"),
            ("Borin", ["stubborn", "brave"], "A trapped corridor hisses — do they search for traps?"),
            ("Party", ["brave", "cautious", "reckless"], "Party must choose: hold, negotiate, or flee the dragon"),
        ]
        for name, traits, sit in scenarios:
            if name == "Party":
                # group decision via tools directly
                res = tools.group_triple_o(traits, ["hold position", "negotiate", "flee into tunnels"])
                print(f"\n--- Group {traits} ---\nRoll {res['roll']} ({res['category']}) → {res['choice']}")
            else:
                out = mw.run_turn_sync(
                    player_name=name, traits=traits, situation=sit, provider=provider, model=args.model
                )
                print(f"\n--- {name} ---\nSituation: {sit}\nChosen: {out['roll']}\nNarration: {out['text']}")
        print(f"\nTool traces: {len(tools.tool_trace)} — deterministic seed {args.seed}")
    else:
        # heuristic demo: propose→roll→spark without LLM
        cases = [
            (
                "Lyra",
                "ambush at gate",
                "snipe from rooftop (agile, keen eye)",
                "flank via alley (crafty)",
                "charge shouting (odd)",
            ),
            ("Borin", "pit trap ahead", "probe with pole", "step carefully around edge", "leap over the pit"),
            ("Mira", "rune on altar", "study the text", "touch it with mage hand", "smash it with staff"),
        ]
        for char, sit, ob, op, od in cases:
            out = mw.run_heuristic(player_name=char, traits="stubborn", situation=sit, obvious=ob, option=op, odd=od)
            print(
                f"\n{char} — {sit}\n  roll {out['roll']['roll']} → {out['roll']['category']}: {out['roll']['choice']}"
            )
            print(f"  spark: {out['spark']['disposition']} → {out['spark']['action']} via {out['spark']['method']}")
        # also show questions + group
        print("\n--- GM Question ---")
        q = tools.ask_triple_o("Do they search for traps?", yes_is_obvious=True)
        print(f"  {q['question']} → {q['category']} ({q['roll']}) → {q['answer']}")
        print("\n--- Group Decision ---")
        g = tools.group_triple_o(["brave", "cautious", "reckless"], ["hold", "negotiate", "flee"])
        print(f"  traits {g['traits']} → roll {g['roll']} {g['category']} → {g['choice']}")
        print(f"\nTool traces: {len(tools.tool_trace)} — heuristic mode (seed {args.seed})")


def cmd_spark(args: argparse.Namespace) -> None:
    from .core import TripleO
    from .spark import roll_spark

    engine = TripleO(seed=args.seed)
    _ = engine
    for i in range(args.times):
        s = roll_spark()
        print(
            f"{i + 1:02d}: disposition {s['disposition_roll']} {s['disposition']} / {s['motivation']} — "
            f"action {s['action_roll']} {s['action']} via {s['method']}"
        )


def main() -> None:
    p = argparse.ArgumentParser(prog="triple-o", description="Triple-O middleware demos")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="Propose→roll→spark creativity demo (heuristic by default, --use-llm for Tau)")
    d.add_argument("--seed", type=int, default=42)
    d.add_argument("--use-llm", action="store_true", help="use LMStudio :1234")
    d.add_argument("--model", type=str, default="qwen3.6-35b-a3b-mtp")
    d.add_argument("--base-url", type=str, default="http://127.0.0.1:1234/v1")
    d.set_defaults(func=cmd_demo)

    s = sub.add_parser("spark", help="Roll spark tables")
    s.add_argument("--seed", type=int, default=42)
    s.add_argument("--times", type=int, default=5)
    s.set_defaults(func=cmd_spark)

    args = p.parse_args()
    args.func(args)
