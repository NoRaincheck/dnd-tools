"""Spark Tables — two 1d6 tables from the Triple-O gist.

Disposition & Motivation (1d6):
 1 Aggressive/Greed, 2 Cautious/Survival, 3 Inquisitive/Knowledge,
 4 Helpful/Loyalty, 5 Aloof/Pride, 6 Erratic/Justice

Action & Method (1d6):
 1 Investigate/Stealth, 2 Attack/Brute Force, 3 Defend/Diplomacy,
 4 Negotiate/Agility, 5 Manipulate/Magic, 6 Flee/Deception
"""

from __future__ import annotations

from typing import Any

import dnd_tools.dice as _base_dice

DISPOSITION_TABLE: dict[int, dict[str, str]] = {
    1: {"disposition": "Aggressive / Confrontational", "motivation": "Greed / Wealth"},
    2: {"disposition": "Cautious / Defensive", "motivation": "Survival / Safety"},
    3: {"disposition": "Inquisitive / Curious", "motivation": "Knowledge / Discovery"},
    4: {"disposition": "Helpful / Cooperative", "motivation": "Loyalty / Duty"},
    5: {"disposition": "Aloof / Dismissive", "motivation": "Pride / Glory"},
    6: {"disposition": "Erratic / Impulsive", "motivation": "Justice / Vengeance"},
}

ACTION_TABLE: dict[int, dict[str, str]] = {
    1: {"action": "Investigate the surroundings", "method": "Stealth / Subterfuge"},
    2: {"action": "Attack or confront the obstacle", "method": "Brute Force / Violence"},
    3: {"action": "Defend or fortify a position", "method": "Diplomacy / Charm"},
    4: {"action": "Negotiate or speak with NPCs", "method": "Agility / Speed"},
    5: {"action": "Manipulate an object or device", "method": "Magic / Technology"},
    6: {"action": "Flee, reposition, or hide", "method": "Deception / Trickery"},
}


def roll_disposition() -> dict[str, Any]:
    r = _base_dice.roll_dice("1d6")
    row = DISPOSITION_TABLE[r]
    return {"roll": r, **row}


def roll_action() -> dict[str, Any]:
    r = _base_dice.roll_dice("1d6")
    row = ACTION_TABLE[r]
    return {"roll": r, **row}


def roll_spark() -> dict[str, Any]:
    """Roll both spark tables and return combined flavour."""
    d = roll_disposition()
    a = roll_action()
    return {
        "disposition_roll": d["roll"],
        "disposition": d["disposition"],
        "motivation": d["motivation"],
        "action_roll": a["roll"],
        "action": a["action"],
        "method": a["method"],
    }


def spark_text(collapsed: bool = False) -> str:
    """One-line text descriptor for LLM injection."""
    s = roll_spark()
    if collapsed:
        return f"{s['disposition']} ({s['motivation']}) → {s['action']} via {s['method']}"
    return (
        f"Disposition: {s['disposition']} | Motivation: {s['motivation']} — "
        f"Action: {s['action']} | Method: {s['method']}"
    )
