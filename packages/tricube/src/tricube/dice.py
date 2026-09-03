"""Deterministic Tricube dice — 1-3d6 vs difficulty.

Wraps dnd_tools.dice seeded RNG so TricubeState.seed controls it.
"""

from __future__ import annotations

import dnd_tools.dice as _base_dice

# Re-export seed so callers can centralise
seed = _base_dice.seed


def _rng():
    # dnd_tools.dice._rng is a random.Random ; access via its module
    return _base_dice._rng  # type: ignore[attr-defined]


def roll_tricube(dice_count: int, difficulty: int) -> dict:
    """Roll dice_count d6, evaluate vs difficulty.

    Returns dict with rolls, successes, success, exceptional, critical_failure, effort_removed.
    dice_count is clamped to 1..3 by caller (models already does).
    """
    if dice_count < 1 or dice_count > 3:
        raise ValueError(f"dice_count must be 1..3, got {dice_count}")
    if difficulty < 2 or difficulty > 7:
        # Tricube raw difficulty can exceed 6 via quirks/rank; still allow
        # but treat normally (need die >= diff). diff>6 impossible with 1 die.
        pass
    rng = _rng()
    rolls = [rng.randint(1, 6) for _ in range(dice_count)]
    successes = sum(1 for r in rolls if r >= difficulty)
    success = successes >= 1
    exceptional = successes >= 2
    critical_failure = all(r == 1 for r in rolls)
    return {
        "dice_count": dice_count,
        "difficulty": difficulty,
        "rolls": rolls,
        "successes": successes,
        "success": success,
        "exceptional": exceptional,
        "critical_failure": critical_failure,
        "effort_removed": successes,
    }


def reevaluate_with_difficulty(rolls: list[int], new_difficulty: int) -> dict:
    """Recompute successes after karma reduces difficulty by 1."""
    successes = sum(1 for r in rolls if r >= new_difficulty)
    return {
        "rolls": list(rolls),
        "difficulty": new_difficulty,
        "successes": successes,
        "success": successes >= 1,
        "exceptional": successes >= 2,
        "critical_failure": all(r == 1 for r in rolls),
        "effort_removed": successes,
    }


def opposed_result(a_rolls: list[int], b_rolls: list[int]) -> dict:
    """Opposed challenge: each treats other's highest die as difficulty.

    Tie-break: most dice matching difficulty wins as normal success.
    Both crit failures -> both suffer.
    Returns winner ('a'|'b'|'tie'|'both_crit').
    """
    a_crit = all(r == 1 for r in a_rolls)
    b_crit = all(r == 1 for r in b_rolls)
    if a_crit and b_crit:
        return {"winner": "both_crit", "a_high": max(a_rolls), "b_high": max(b_rolls)}
    if a_crit:
        return {"winner": "b", "reason": "a critical failure"}
    if b_crit:
        return {"winner": "a", "reason": "b critical failure"}
    a_high = max(a_rolls)
    b_high = max(b_rolls)
    # Each needs to beat other's high; count matches
    a_successes = sum(1 for r in a_rolls if r >= b_high)
    b_successes = sum(1 for r in b_rolls if r >= a_high)
    a_success = a_successes >= 1
    b_success = b_successes >= 1
    if a_success and not b_success:
        return {
            "winner": "a",
            "a_successes": a_successes,
            "b_successes": b_successes,
            "a_high": a_high,
            "b_high": b_high,
        }
    if b_success and not a_success:
        return {
            "winner": "b",
            "a_successes": a_successes,
            "b_successes": b_successes,
            "a_high": a_high,
            "b_high": b_high,
        }
    if a_success and b_success:
        # tie-break: most dice matching difficulty
        if a_successes > b_successes:
            return {
                "winner": "a",
                "tie_break": "more dice matched",
                "a_successes": a_successes,
                "b_successes": b_successes,
            }
        if b_successes > a_successes:
            return {
                "winner": "b",
                "tie_break": "more dice matched",
                "a_successes": a_successes,
                "b_successes": b_successes,
            }
        return {"winner": "tie", "note": "equal matches — interpret as equally favourable"}
    # neither succeeded
    return {"winner": "none", "a_successes": a_successes, "b_successes": b_successes}
