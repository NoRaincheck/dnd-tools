"""CLI for adventure-webapp."""

from __future__ import annotations

import argparse
import json


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("adventure_webapp.app:app", host=args.host, port=args.port, reload=args.reload)


def cmd_demo(args: argparse.Namespace) -> None:
    from .engine import AdventureEngine

    eng = AdventureEngine()
    g = eng.create_game(template_id=args.template, actor=args.actor, seed=args.seed, segments=args.segments)
    print(f"Scene: {g.scene.title} — {g.scene.objective}  seed={g.seed}  game={g.game_id}")
    print(f"Clock: {g.clock()}")
    # auto-play a few turns deterministically picking obvious unless --random
    import random

    random.seed(args.seed)
    picks = ["obvious", "option", "odd"]
    for i in range(args.turns):
        cur = eng.current_turn(g)
        if not cur or g.completed:
            break
        pick = random.choice(picks) if args.random else "obvious"
        mode = "auto(Triple-O)" if args.auto else "manual"
        print(f"\n--- Turn {cur['seq']} beat:{cur['beat_title']} situation:{cur['situation'][:70]}")
        print(
            f" choices: O={cur['choices']['obvious'][:60]} | Opt={cur['choices']['option'][:50]} | Odd={cur['choices']['odd'][:45]}"
        )
        print(f" > request pick: {pick} [{mode}]")
        res = eng.resolve_pick(g.game_id, pick, auto=args.auto)
        t = res.get("turn") or {}
        roll = t.get("roll") or {}
        print(
            f"  resolved pick={t.get('picked')} via {t.get('resolved_via')} outcome={roll.get('outcome')} rolls={roll.get('rolls')} ticks={roll.get('ticks')} cons={roll.get('consequence')}"
        )
        print(f"  narration: {t.get('narration', '')[:220]}")
        print(f"  clock: {res.get('clock')}")
        if res.get("completed"):
            print("\n=== SCENE COMPLETED ===")
            break
    print("\n=== STORY ===")
    print(g.story_text())
    print("\n=== TURNS (json) ===")
    print(json.dumps(g.turns_view(), indent=2))


def main() -> None:
    p = argparse.ArgumentParser(prog="adventure")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="Serve playable webapp")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--reload", action="store_true")
    s.add_argument("--seed", type=int, default=42)

    d = sub.add_parser("demo", help="Headless demo of loop (no browser)")
    d.add_argument("--template", default="veiled-archive", choices=["veiled-archive", "goblin-ambush", "starlit-heist"])
    d.add_argument("--actor", default="Elaria")
    d.add_argument("--seed", type=int, default=42)
    d.add_argument("--segments", type=int, default=6)
    d.add_argument("--turns", type=int, default=8)
    d.add_argument("--auto", action="store_true", help="Auto pick via Triple-O roll distribution")
    d.add_argument("--random", action="store_true", help="Random manual pick (stress roll paths)")

    args = p.parse_args()
    if args.cmd == "serve":
        cmd_serve(args)
    elif args.cmd == "demo":
        cmd_demo(args)


if __name__ == "__main__":
    main()
