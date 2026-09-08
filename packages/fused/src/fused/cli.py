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

    # default party with explicit traits (separate from event state)
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

    # ensure players exist in inner state
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
    # OKF bundle already exported; show bundle info
    bundle_path = fstate.bundle_root or bundle_root
    print("\n=== OKF BUNDLE ===")
    print(f"Bundle at: {bundle_path}")
    print(f"Traits registered (separate): {list(fstate.traits_registry.keys())}")
    print(f"Effects (event state): {len(fstate.effects)}")
    # list concepts
    for eff in fstate.effects[-5:]:
        print(f"  - {eff.effect_id}: {eff.summary}")
    if args.save:
        out = Path(args.save)
        out.write_text(json.dumps([r["tool_trace"] for r in results], indent=2))
        fstate.save(Path(args.save).with_suffix(".fused.json"))
        print(f"saved traces to {args.save}")

    # traversal demo: agent loading context before acting
    print("\n=== AGENT TRAVERSAL DEMO (get_context for Elaria) ===")
    ctx = ftools.get_context("Elaria", last_n=5)
    print(json.dumps(ctx, indent=2, default=str))


def main() -> None:
    p = argparse.ArgumentParser(prog="fused")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo", help="Run 2-scene fused campaign demo (scenes + Triple-O + OKF bundle)")
    d.add_argument("--seed", type=int, default=42)
    d.add_argument("--turns", type=int, default=12)
    d.add_argument("--bundle", type=str, default="", help="OKF bundle root (default knowledge/fused-demo)")
    d.add_argument("--no-triple-o", action="store_true", help="Disable Triple-O creativity harness")
    d.add_argument("--save", type=str, default="")
    d.add_argument("--use-llm", action="store_true", help="Use Tau LLM (requires LMStudio at :1234)")
    d.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    d.add_argument("--model", default="qwen3.6-35b-a3b-mtp")

    d2 = sub.add_parser("export", help="Export existing fused save as OKF bundle")
    d2.add_argument("save", type=str, help="Path to .fused.json save")
    d2.add_argument("--bundle", type=str, default="knowledge/fused")
    args = p.parse_args()
    if args.cmd == "demo":
        # wire LLM if requested — reuse Triple-O / dnd-tools LLM plumbing
        if args.use_llm:
            from dnd_tools.agents import LLMClient as TauLLM  # type: ignore[import-untyped]

            # not wired into heuristic path yet; show hint
            _ = TauLLM
            print(
                f"[fused] --use-llm requested (model {args.model} at {args.base_url}) — demo runs heuristic+Triple-O; wire via session.run_scene(llm=...)"
            )
        cmd_demo(args)
    elif args.cmd == "export":
        fs = FusedState.load(args.save)
        out = fs.export_okf(bundle_root=args.bundle)
        print(f"Exported OKF bundle to {out}")
        # also write index validation
        from .okf import OKFBundle

        errs = OKFBundle.validate_bundle(out)
        print(f"Validation: {'OK' if not errs else errs}")

    # ensure pathlib is available for any future use
    _ = pathlib


if __name__ == "__main__":
    main()
