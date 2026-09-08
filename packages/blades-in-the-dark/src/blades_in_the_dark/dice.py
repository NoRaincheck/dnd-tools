"""Deterministic dice for Blades — action / resistance / fortune.

Wraps dnd_tools.dice seeded RNG so BladesState.seed controls it.
SRD-accurate: highest die determines tier; zero dice => 2d6 keep lowest;
critical if 2+ sixes (except zero dice). Resistance stress = 6 - high; crit clears 1.
"""

from __future__ import annotations

import dnd_tools.dice as _base_dice

seed = _base_dice.seed


def _rng():
    return _base_dice._rng  # type: ignore[attr-defined]


def _highest_and_crit(rolls: list[int], pool: int) -> tuple[int, bool]:
    if not rolls:
        return 0, False
    if pool <= 0:
        high = min(rolls)
        crit = False  # zero dice cannot crit (SRD: take lowest of 2d6, no crit)
    else:
        high = max(rolls)
        crit = rolls.count(6) >= 2
    return high, crit


def roll_action(pool: int) -> dict:
    """Roll action pool. Returns dict with rolls/highest/outcome/critical."""
    n = int(pool)
    if n <= 0:
        rng = _rng()
        rolls = [rng.randint(1, 6) for _ in range(2)]
        high = min(rolls)
        crit = False
        outcome = "critical" if False else ("success" if high == 6 else ("partial" if 4 <= high <= 5 else "failure"))
        # zero-dice never critical; highest 1-3 is failure even with zero mod
    else:
        rng = _rng()
        rolls = [rng.randint(1, 6) for _ in range(n)]
        high, crit = _highest_and_crit(rolls, n)
        if crit:
            outcome = "critical"
        elif high == 6:
            outcome = "success"
        elif 4 <= high <= 5:
            outcome = "partial"
        else:
            outcome = "failure"
    return {
        "pool": n,
        "rolls": rolls,
        "highest": high if n > 0 else min(rolls) if rolls else 0,
        "critical": crit,
        "outcome": outcome,  # critical/success/partial/failure
        # SRD aliases: 6, 4/5, 1-3
        "is_critical": crit,
        "is_success": outcome in ("critical", "success"),
        "is_partial": outcome == "partial",
        "is_failure": outcome == "failure",
    }


def roll_resistance(attr_rating: int) -> dict:
    """Roll resistance attribute. Stress = 6 - high; crit clears 1 stress."""
    n = int(attr_rating)
    if n <= 0:
        rng = _rng()
        rolls = [rng.randint(1, 6) for _ in range(2)]
        high = min(rolls)
        crit = False
    else:
        rng = _rng()
        rolls = [rng.randint(1, 6) for _ in range(n)]
        high, crit = _highest_and_crit(rolls, n)
    stress_cost = 6 - high
    # stress cost floor 0 (SRD says 0 on 6; 6-6=0)
    stress_cost = max(0, stress_cost)
    return {
        "pool": n,
        "rolls": rolls,
        "highest": high,
        "critical": crit,
        "stress_cost": stress_cost,
        "clears_one": bool(crit),
    }


def roll_fortune(dice: int) -> dict:
    """Fortune roll — similar tiers to action but used for engagement/payoff."""
    n = int(dice)
    if n <= 0:
        rng = _rng()
        rolls = [rng.randint(1, 6) for _ in range(2)]
        high = min(rolls)
        crit = False
    else:
        rng = _rng()
        rolls = [rng.randint(1, 6) for _ in range(n)]
        high, crit = _highest_and_crit(rolls, n)
        # fortune crit is still 2 sixes
    if crit:
        tier = "critical"
    elif high == 6:
        tier = "excellent"
    elif 4 <= high <= 5:
        tier = "good"
    else:
        tier = "poor"
    return {
        "dice": n,
        "rolls": rolls,
        "highest": high,
        "critical": crit,
        "tier": tier,  # critical/excellent/good/poor
    }
