"""CLI for dnd_campaign — does NOT touch dnd_tools.cli."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from dnd_tools.simulation import create_player

from .session import CampaignSession
from .state import CampaignState
from .tools import CampaignTools


def cmd_demo(args: argparse.Namespace) -> None:
    random.seed(args.seed)
    cstate = CampaignState(seed_val=args.seed)
    # default party if none
    players = [
        create_player("Elaria", "ranger", tier="medium"),
        create_player("Briana", "wizard", tier="medium"),
        create_player("Thalion", "fighter", tier="medium"),
        create_player("Mira", "cleric", tier="medium"),
    ]
    # seed inner players so add_encounter can keep them
    for p in players:
        cstate.inner.add_player(p, (0, 0, 0))
    ctools = CampaignTools(cstate)
    sess = CampaignSession(cstate, ctools)
    encounters = [
        {"monsters": ["goblin", "goblin", "goblin"], "map": "outdoor"},
        {"monsters": ["wolf", "wolf", "goblin"], "map": "indoor"},
    ]
    results = sess.run_campaign(encounters, max_turns_per_encounter=args.turns)
    for i, r in enumerate(results, 1):
        print(f"\n=== ENCOUNTER {i} ===")
        for line in r["transcript"][-10:]:
            print(line)
        print(json.dumps({k: r[k] for k in ("players", "monsters", "rounds")}, indent=2))
    if args.save:
        Path(args.save).write_text(json.dumps([r["tool_trace"] for r in results], indent=2))
        # also save campaign snapshot
        cstate.save(Path(args.save).with_suffix(".campaign.json"))
        print(f"saved to {args.save}")


def main() -> None:
    p = argparse.ArgumentParser(prog="dnd-campaign")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo", help="Run 2-encounter campaign demo")
    d.add_argument("--seed", type=int, default=42)
    d.add_argument("--turns", type=int, default=15)
    d.add_argument("--save", type=str, default="")
    args = p.parse_args()
    if args.cmd == "demo":
        cmd_demo(args)


if __name__ == "__main__":
    main()
