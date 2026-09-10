#!/usr/bin/env python3
"""Render ref/burning-wheel.liquid → ref/burning-wheel.html via python-liquid."""

from __future__ import annotations

import datetime
import pathlib

try:
    from liquid import Template
except ImportError as e:
    raise SystemExit("Missing python-liquid. Install with: uv add --group dev python-liquid") from e

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "ref" / "burning-wheel.liquid"
OUTPUT_PATH = ROOT / "ref" / "burning-wheel.html"


def build_context() -> dict:
    now = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    try:
        import importlib.metadata as im

        lv = im.version("python-liquid")
    except Exception:
        lv = "2.x"
    return {
        "title": "Burning Wheel Gold — Core System Rules (Implementation Condensed)",
        "subtitle": "Tool-Grounded Implementation Reference · Hub & Spokes + BITs + Let It Ride · For LLM + dnd-tools + dnd-campaign",
        "description": "Condensed Burning Wheel Gold reference for LLM tool-grounded implementation — BITs, Intent & Task, Say Yes/Let It Ride, shades, PTGS, Duel of Wits.",
        "callout_title": "Burning Wheel Gold © 2002–2011 Luke Crane / Burning Wheel HQ",
        "callout_body": "Condensed for LLM + tool-grounded implementation from Hub & Spokes, Rim, Character Burner and public summaries. No open CC SRD — fair-use synthesis, not verbatim reproduction.",
        "version": "1.0.0",
        "render_date": now,
        "liquid_version": lv,
        "thresholds": {"black": "B≥4", "grey": "G≥3", "white": "W≥2"},
        "sections": [
            {"id": "overview", "number": 1, "label": "Overview"},
            {"id": "characters", "number": 2, "label": "Characters"},
            {"id": "core", "number": 3, "label": "Core Mechanics"},
            {"id": "running", "number": 4, "label": "Running"},
            {"id": "advancement", "number": 5, "label": "Advancement"},
            {"id": "example", "number": 6, "label": "Example"},
        ],
        "stocks": ["Man", "Dwarf", "Elf", "Orc"],
        "stats": [
            {"name": "Will", "tests": "Social, Steel, DoW body", "root": "Social skills (Persuasion, Oratory)"},
            {"name": "Perception", "tests": "Observation, search", "root": "Perception skills"},
            {"name": "Agility", "tests": "Quickness, fine motor", "root": "Agility skills (Brawling, Throwing)"},
            {"name": "Speed", "tests": "Initiative, reflexes", "root": "Speed skills (Stealth, Climbing)"},
            {"name": "Power", "tests": "Raw strength", "root": "Power skills"},
            {"name": "Forte", "tests": "Health, endurance", "root": "Forte skills"},
        ],
        "attributes": [
            {"name": "Health", "exp": "Forte + Will /2", "purpose": "Wound recovery, resist"},
            {"name": "Steel", "exp": "Will + Forte", "purpose": "Hesitation vs fear/pain"},
            {"name": "Circles", "exp": "Will-based + LP", "purpose": "Find NPCs"},
            {"name": "Resources", "exp": "Generic + LP + property", "purpose": "Buy gear; Tax on fail"},
            {"name": "Reflexes", "exp": "(Agi+Spd+Per)/3", "purpose": "Ordering (Fight! only)"},
        ],
        "trait_kinds": [
            {
                "kind": "Character trait",
                "effect": "Narrative (Curious, Stubborn). Guides RP, Fate when complicates.",
                "cost": "1 pt",
            },
            {"kind": "Call-on trait", "effect": "1/session reroll/swap or break tie. e.g. Linguist", "cost": "2–3 pts"},
            {
                "kind": "Die trait",
                "effect": "Alters roll: +1D, shade, advantage. e.g. Gifted, Faithful",
                "cost": "3–5 pts",
            },
        ],
        "artha": [
            {
                "name": "Fate",
                "abbr": "F",
                "earn": "Play BIT even though it hurts; embody trait",
                "spend": "Open-ended: each 6 explodes recursively",
            },
            {
                "name": "Persona",
                "abbr": "P",
                "earn": "Moldbreaker / Workhorse / Embodiment; resolve Belief",
                "spend": "+1D per Persona (max 3) before roll",
            },
            {
                "name": "Deeds",
                "abbr": "D",
                "earn": "Heroic act beyond self, group-voted",
                "spend": "Double dice for one test",
            },
        ],
        "wounds": [
            {"class": "Superficial", "code": "Su", "penalty": "+1 Ob next", "margin": "1–2 over PTGS"},
            {"class": "Light", "code": "Li", "penalty": "−1D", "margin": "3–4"},
            {"class": "Midi", "code": "Mi", "penalty": "−1D (stacks)", "margin": "5–6"},
            {"class": "Severe", "code": "Se", "penalty": "−2D", "margin": "7–8"},
            {"class": "Traumatic", "code": "Tr", "penalty": "−4D", "margin": "9–10"},
            {"class": "Mortal", "code": "Mo", "penalty": "Dead w/o 2 Persona", "margin": "11+"},
        ],
        "obstacles": [
            {"ob": "1", "label": "Easy", "use": "Everyday, aided"},
            {"ob": "2", "label": "Routine", "use": "Professional with right tool"},
            {"ob": "3", "label": "Difficult", "use": "Default for Versus"},
            {"ob": "4–5", "label": "Hard", "use": "Interesting but nonessential"},
            {"ob": "6+", "label": "Extreme", "use": "Reserve for 3-pt spends"},
            {"ob": "7–8", "label": "Legendary", "use": "Cap; use staged tests"},
        ],
        "test_classes": [
            {"class": "Routine", "cond": "Ob ≤ Dice rolled"},
            {"class": "Difficult", "cond": "Ob > Dice by 1–2"},
            {"class": "Challenging", "cond": "Ob > Dice by 3+"},
        ],
        "advancement": [
            {"exp": "B2", "needs": "2R / — / —"},
            {"exp": "B3", "needs": "3R / 1D / 1C"},
            {"exp": "B4", "needs": "4R / 2D / 1C"},
            {"exp": "B5", "needs": "5R / 2D / 2C"},
            {"exp": "B6", "needs": "6R / 3D / 2C"},
        ],
        "tools": [
            {
                "name": "declare_intent",
                "purpose": "Gate: Intent+Task+belief_ref",
                "params": "character, intent, task, skill, belief_ref",
            },
            {"name": "set_ob", "purpose": "GM sets Ob 1–10", "params": "character, ob, kind"},
            {"name": "declare_help", "purpose": "+1D per helper (cap 3)", "params": "leader, helper, skill, narration"},
            {"name": "declare_fork", "purpose": "FoRK +1D (cap 2)", "params": "character, fork_skill"},
            {
                "name": "spend_artha",
                "purpose": "Fate open / Persona +1–3D / Deeds double",
                "params": "character, type, amount",
            },
            {"name": "roll_test", "purpose": "Authoritative Nd6 vs shade Ob", "params": "character, skill, ob, shade?"},
            {"name": "versus_test", "purpose": "Symmetric vs roll", "params": "a, a_skill, b, b_skill"},
            {
                "name": "bloody_versus",
                "purpose": "One-exchange brawl → wound",
                "params": "attacker, defender, skills, ims?",
            },
            {
                "name": "circles_test",
                "purpose": "Find NPC (fail=hostile)",
                "params": "character, npc_power, disposition",
            },
            {"name": "resources_test", "purpose": "Buy (fail=Tax)", "params": "character, price_ob"},
            {"name": "steel_test", "purpose": "Hesitation", "params": "character, ob"},
            {"name": "apply_wound", "purpose": "PTGS mapping", "params": "target, kind/margin"},
            {
                "name": "dow_script / dow_resolve",
                "purpose": "Duel of Wits",
                "params": "volley, action, skill / exchange",
            },
        ],
    }


def main() -> None:
    if not TEMPLATE_PATH.exists():
        raise SystemExit(f"Template not found: {TEMPLATE_PATH}")
    src = TEMPLATE_PATH.read_text(encoding="utf-8")
    tmpl = Template(src)
    ctx = build_context()
    out = tmpl.render(**ctx)
    OUTPUT_PATH.write_text(out, encoding="utf-8")
    print(f"Rendered {TEMPLATE_PATH} -> {OUTPUT_PATH} ({len(out)} bytes)")


if __name__ == "__main__":
    main()
