"""Dice primitives — deterministic given seed."""

from __future__ import annotations

import random
import re

_rng = random.Random()


def seed(s: int) -> None:
    _rng.seed(s)


def roll_dice(expr: str) -> int:
    """Parse dice expressions like '1d20', '2d20kh1', '4d6', '1d8+3'.
    Supports kh/kl (keep highest/lowest) for advantage/disadvantage.
    Example: '2d20kh1' = roll 2d20 keep highest 1.
    """
    expr = expr.strip().replace(" ", "")
    # handle keep
    m = re.match(r"(\d+)d(\d+)(kh|kl)(\d+)([+-]\d+)?$", expr)
    if m:
        n = int(m.group(1))
        sides = int(m.group(2))
        op = m.group(3)
        keep = int(m.group(4))
        mod_s = m.group(5)
        rolls = [_rng.randint(1, sides) for _ in range(n)]
        rolls_sorted = sorted(rolls, reverse=(op == "kh"))
        kept = rolls_sorted[:keep]
        total = sum(kept) + (int(mod_s) if mod_s else 0)
        return total
    m = re.match(r"(\d+)d(\d+)([+-]\d+)?$", expr)
    if m:
        n = int(m.group(1))
        sides = int(m.group(2))
        mod_s = m.group(3)
        total = sum(_rng.randint(1, sides) for _ in range(n))
        if mod_s:
            total += int(mod_s)
        return total
    # plain int
    if re.match(r"-?\d+$", expr):
        return int(expr)
    raise ValueError(f"Unsupported dice expr: {expr}")


def roll_with_parts(expr: str) -> tuple[int, list[int]]:
    """Return total and individual rolls (for logging)."""
    expr = expr.strip().replace(" ", "")
    m = re.match(r"(\d+)d(\d+)([+-]\d+)?$", expr)
    if m:
        n = int(m.group(1))
        sides = int(m.group(2))
        mod_s = m.group(3)
        rolls = [_rng.randint(1, sides) for _ in range(n)]
        total = sum(rolls) + (int(mod_s) if mod_s else 0)
        return total, rolls
    return roll_dice(expr), []


def d20(adv: str = "normal") -> int:
    if adv == "advantage":
        return roll_dice("2d20kh1")
    if adv == "disadvantage":
        return roll_dice("2d20kl1")
    return roll_dice("1d20")
