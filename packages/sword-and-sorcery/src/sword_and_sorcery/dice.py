"""Deterministic S&S dice — 1-3d6 vs S&S number, WD rolls, spell damage.

Wraps dnd_tools.dice seeded RNG so SnSState.seed controls determinism.
"""

from __future__ import annotations

import dnd_tools.dice as _base_dice

seed = _base_dice.seed


def _rng():
    return _base_dice._rng  # type: ignore[attr-defined]


def roll_sns_check(
    sns: int,
    mode: str,
    dice_count: int = 1,
) -> dict:
    """Roll 1-3d6 for S&S. Compare each die to S&S number.

    - SWORDS: roll UNDER sns (strict <)
    - SORCERY: roll OVER sns (strict >)
    - Exactly equal = Divine Intervention (counts as success, but flagged)

    Returns dict with rolls, successes, divine_intervention, outcome.
    Outcome mapping: 0→fail, 1→barely, 2→good, 3→critical.
    """
    if not 2 <= sns <= 5:
        raise ValueError(f"sns must be 2-5, got {sns}")
    mode = mode.lower()
    if mode not in ("swords", "sorcery"):
        raise ValueError(f"mode must be swords/sorcery, got {mode}")
    if dice_count < 1 or dice_count > 3:
        raise ValueError(f"dice_count must be 1-3, got {dice_count}")
    rng = _rng()
    rolls = [rng.randint(1, 6) for _ in range(dice_count)]
    successes = 0
    divine = False
    for r in rolls:
        if r == sns:
            divine = True
            successes += 1  # "Your roll counts as a success"
        elif (mode == "swords" and r < sns) or (mode == "sorcery" and r > sns):
            successes += 1
    # outcome label
    if successes == 0:
        outcome = "fail"
    elif successes == 1:
        outcome = "barely"
    elif successes == 2:
        outcome = "success"
    else:
        outcome = "critical"
    return {
        "rolls": rolls,
        "sns": sns,
        "mode": mode,
        "dice_count": dice_count,
        "successes": successes,
        "success": successes >= 1,
        "divine_intervention": divine,
        "outcome": outcome,
    }


def roll_weapon_damage(wd: int) -> dict:
    """WD = S&S -1. Roll WD d6s, take highest."""
    if wd < 1:
        return {"wd": wd, "rolls": [], "damage": 0}
    rng = _rng()
    rolls = [rng.randint(1, 6) for _ in range(wd)]
    return {"wd": wd, "rolls": rolls, "damage": max(rolls)}


def roll_spell_damage(level: int) -> dict:
    """Spell damage/heal: roll level d6s, highest + 2*level (can split)."""
    if level < 1 or level > 3:
        raise ValueError(f"spell level must be 1-3, got {level}")
    rng = _rng()
    rolls = [rng.randint(1, 6) for _ in range(level)]
    highest = max(rolls)
    total = highest + (2 * level)
    return {"level": level, "rolls": rolls, "highest": highest, "total": total}


def roll_d6(n: int = 1) -> list[int]:
    rng = _rng()
    return [rng.randint(1, 6) for _ in range(n)]
