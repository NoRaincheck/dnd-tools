"""CLI for fused — does NOT touch dnd_tools/dnd_campaign/triple_o CLIs."""

from __future__ import annotations

import argparse
import json
import pathlib
from pathlib import Path

from dnd_tools.simulation import create_player

from .models import CharacterTraits
from .session import FusedSession
from .state import FusedState
from .tools import FusedTools


def cmd_demo(args: argparse.Namespace) -> None:
    bundle_root = Path(args.bundle) if args.bundle else Path("knowledge/fused-demo")
    fstate = FusedState(seed_val=args.seed, bundle_root=bundle_root)
    ftools = FusedTools(fstate)
    sess = FusedSession(fstate, ftools)

    default_traits = [
        CharacterTraits(
            name="Elaria",
            ancestry="elf",
            background="tracker",
            archetype="ranger",
            traits=["Suspicious of authority", "Always ready to fight"],
            flaws=["Vindictive"],
            favored_skills=["stealth"],
            bonds=["Protect the wilds"],
        ),
        CharacterTraits(
            name="Briana",
            ancestry="human",
            background="sage",
            archetype="wizard",
            traits=["Inquisitive / Curious"],
            flaws=["Arrogant"],
            favored_skills=["arcana"],
            bonds=["Seek Lǎo Mei"],
        ),
        CharacterTraits(
            name="Thalion",
            ancestry="human",
            background="soldier",
            archetype="fighter",
            traits=["Helpful / Cooperative"],
            flaws=["Stubborn"],
            favored_skills=["athletics"],
            bonds=["Loyalty to Guild"],
        ),
        CharacterTraits(
            name="Mira",
            ancestry="dwarf",
            background="cleric",
            archetype="cleric",
            traits=["Cautious / Defensive"],
            flaws=["Peg leg"],
            favored_skills=["insight"],
            bonds=["Duty to the Conclave"],
        ),
    ]
    sess.register_party_traits(default_traits)

    for tr in default_traits:
        cls = (
            tr.archetype
            if tr.archetype
            in ("fighter", "wizard", "cleric", "ranger", "rogue", "paladin", "barbarian", "bard", "druid")
            else "fighter"
        )
        ch = create_player(tr.name, cls, tier="medium")
        fstate.campaign.inner.add_player(ch, (0, 0, 0))

    scenes = [
        {
            "scene_id": "scene-01-goblin-ambush",
            "title": "Goblin Ambush",
            "objective": "Survive the ambush on the road to Tanglewood",
            "location": "Wilderlands",
            "patron": "Lord Garrington",
            "threat": "Goblin raiders",
            "beats": ["Patrol sets out", "Ambushed on road", "Hold or flee"],
            "cast": [t.name for t in default_traits],
            "monsters": ["goblin", "goblin", "goblin"],
            "map": "outdoor",
        },
        {
            "scene_id": "scene-02-kennel",
            "title": "The Kennel",
            "objective": "Clear the kennels and recover Wyldfyre",
            "location": "Undercity",
            "patron": "Wizard Nimdronde",
            "threat": "Cultists",
            "beats": ["Enter kennels", "Rescue hostage", "Escape with Wyldfyre"],
            "cast": [t.name for t in default_traits],
            "monsters": ["wolf", "wolf", "goblin"],
            "map": "indoor",
        },
    ]
    results = sess.run_campaign(scenes, max_turns_per_scene=args.turns, use_triple_o=not args.no_triple_o)
    for i, r in enumerate(results, 1):
        print(f"\n=== SCENE {i} ===")
        for line in r["transcript"][-12:]:
            print(line)
        print(json.dumps({k: r[k] for k in ("players", "monsters", "rounds")}, indent=2))
    print("\n=== EVENT LOG (canonical) ===")
    print(f"Log: {fstate.event_log_path}  ({len(fstate.effects)} events)")
    print(f"Snapshots: {fstate.snapshots_dir}")
    print(f"Manifest: {fstate.manifest_path}")
    # rebuild projection idempotently
    db = fstate.rebuild_projection()
    print(f"Projection (derived, idempotent): {db}")
    print(f"Traits registered (separate): {list(fstate.traits_registry.keys())}")
    for eff in fstate.effects[-5:]:
        print(f"  - {eff.effect_id}: {eff.summary}")
    # cheap jq examples
    print("\nCheap queries (no LLM):")
    print(f"  jq -c 'select(.type==\"fused.effect.recorded\")' {fstate.event_log_path}")
    print(f'  sqlite3 {db} "SELECT subject, kind, summary FROM events ORDER BY seq DESC LIMIT 5"')
    if args.save:
        out = Path(args.save)
        out.write_text(json.dumps([r["tool_trace"] for r in results], indent=2))
        fstate.save(Path(args.save).with_suffix(".fused.json"))
        print(f"saved traces to {args.save}")

    print("\n=== AGENT TRAVERSAL DEMO (get_context for Elaria) ===")
    ctx = ftools.get_context("Elaria", last_n=5)
    print(json.dumps(ctx, indent=2, default=str))


def main() -> None:
    p = argparse.ArgumentParser(prog="fused")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo", help="Run 2-scene fused campaign demo (scenes + Triple-O + JSONL event log)")
    d.add_argument("--seed", type=int, default=42)
    d.add_argument("--turns", type=int, default=12)
    d.add_argument(
        "--bundle", type=str, default="", help="Campaign root (default knowledge/fused-demo) — holds events.jsonl"
    )
    d.add_argument("--no-triple-o", action="store_true", help="Disable Triple-O creativity harness")
    d.add_argument("--save", type=str, default="")
    d.add_argument("--use-llm", action="store_true", help="Use Tau LLM (requires LMStudio at :1234)")
    d.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    d.add_argument("--model", default="qwen3.6-35b-a3b-mtp")

    d2 = sub.add_parser("validate", help="Validate canonical event log")
    d2.add_argument("--log", type=str, default="knowledge/fused-demo/events.jsonl")

    d3 = sub.add_parser("build-projection", help="Rebuild SQLite projection from event log (idempotent)")
    d3.add_argument("--log", type=str, default="knowledge/fused-demo/events.jsonl")
    d3.add_argument("--db", type=str, default="knowledge/fused-demo/projections/campaign.db")

    d4 = sub.add_parser("replay", help="Replay event log into state (snapshot + events)")
    d4.add_argument("--log", type=str, default="knowledge/fused-demo/events.jsonl")
    d4.add_argument("--at-seq", type=int, default=None, help="Replay until seq (exclusive)")

    args = p.parse_args()
    if args.cmd == "demo":
        if args.use_llm:
            from dnd_tools.agents import LLMClient as TauLLM  # type: ignore[import-untyped]

            _ = TauLLM
            print(
                f"[fused] --use-llm requested (model {args.model} at {args.base_url}) — demo runs heuristic+Triple-O; wire via session.run_scene(llm=...)"
            )
        cmd_demo(args)
    elif args.cmd == "validate":
        from .events import validate_log

        errs = validate_log(args.log)
        if errs:
            print("INVALID:")
            for e in errs:
                print(f"  - {e}")
            raise SystemExit(1)
        print(f"OK — {args.log} valid")
    elif args.cmd == "build-projection":
        from .projection import build_projection

        out = build_projection(args.log, args.db)
        print(f"Projection (re)built at {out} — idempotent, delete and rerun to verify")
    elif args.cmd == "replay":
        fs = FusedState.from_log(args.log, at_seq=args.at_seq)
        print(f"Replayed to seq {args.at_seq or len(fs.effects)} — {len(fs.effects)} effects, {len(fs.scenes)} scenes")

    _ = pathlib


if __name__ == "__main__":
    main()
