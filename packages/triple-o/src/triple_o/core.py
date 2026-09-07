"""Core Triple-O engine — deterministic 1d6 with Obvious/Option/Odd semantics.

Uses dnd_tools.dice seeded RNG so ``TripleO(seed=...)`` is reproducible.
Mirrors the gist spec:
  Obvious (4,5,6)  — default expected action
  Option  (2,3)    — reasonable alternative
  Odd     (1)      — left-field / impulsive

Double Down (advantage/disadvantage):
  roll 2d6 and pick result most favouring established behaviour.
  Advantage → higher die (favours Obvious); Disadvantage → lower die (favours Odd).
  Alternative explicit flag ``favour`` lets caller pick literal category bias.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import dnd_tools.dice as _base_dice

Category = Literal["obvious", "option", "odd"]
Advantage = Literal["advantage", "disadvantage"] | None


def _category_for_roll(roll: int) -> Category:
    if roll in (4, 5, 6):
        return "obvious"
    if roll in (2, 3):
        return "option"
    return "odd"  # 1


CATEGORY_LABELS: dict[Category, str] = {
    "obvious": "Obvious (4-6) — most predictable given Traits",
    "option": "Option (2-3) — reasonable alternative",
    "odd": "Odd (1) — unexpected / atypical",
}


@dataclass
class TripleORoll:
    roll: int
    category: Category
    rolls: list[int]
    advantage: Advantage = None
    description: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "roll": self.roll,
            "category": self.category,
            "rolls": self.rolls,
            "advantage": self.advantage,
            "description": CATEGORY_LABELS[self.category],
        }


@dataclass
class Proposal:
    character: str
    situation: str
    obvious: str
    option: str
    odd: str
    traits: list[str] = field(default_factory=list)

    def choice_for(self, category: Category) -> str:
        return {"obvious": self.obvious, "option": self.option, "odd": self.odd}[category]

    def as_dict(self) -> dict[str, Any]:
        return {
            "character": self.character,
            "situation": self.situation,
            "obvious": self.obvious,
            "option": self.option,
            "odd": self.odd,
            "traits": self.traits,
        }


class TripleO:
    """Deterministic Triple-O engine.

    Parameters
    ----------
    seed:
        Seed for underlying ``dnd_tools.dice`` RNG. Each TripleO instance
        seeds globally (matching GameState/TricubeState pattern). For isolated
        sequences prefer creating a new instance per scene.
    """

    def __init__(self, seed: int = 0):
        self.seed = seed
        _base_dice.seed(seed)
        self.history: list[dict[str, Any]] = []

    def reseed(self, seed: int) -> None:
        self.seed = seed
        _base_dice.seed(seed)

    # ------------------------------------------------------------------
    # low-level rolls
    # ------------------------------------------------------------------
    def roll_die(self) -> int:
        """Single 1d6 via seeded RNG."""
        return _base_dice.roll_dice("1d6")

    def roll(self, advantage: Advantage = None) -> TripleORoll:
        """Roll 1d6 (or 2d6 with advantage/disadvantage) and map to category.

        advantage:
            None — single die
            "advantage" — 2d6 keep higher (favours Obvious)
            "disadvantage" — 2d6 keep lower (favours Odd)
        """
        if advantage is None:
            r = self.roll_die()
            cat = _category_for_roll(r)
            res = TripleORoll(roll=r, category=cat, rolls=[r], advantage=None)
        elif advantage == "advantage":
            a = self.roll_die()
            b = self.roll_die()
            r = max(a, b)
            cat = _category_for_roll(r)
            res = TripleORoll(roll=r, category=cat, rolls=[a, b], advantage="advantage")
        elif advantage == "disadvantage":
            a = self.roll_die()
            b = self.roll_die()
            r = min(a, b)
            cat = _category_for_roll(r)
            res = TripleORoll(roll=r, category=cat, rolls=[a, b], advantage="disadvantage")
        else:  # pragma: no cover
            raise ValueError(f"unknown advantage {advantage}")
        self.history.append(res.as_dict())
        return res

    # ------------------------------------------------------------------
    # proposal + resolution (middleware core)
    # ------------------------------------------------------------------
    def propose(
        self,
        character: str,
        situation: str,
        obvious: str,
        option: str,
        odd: str,
        traits: list[str] | None = None,
    ) -> Proposal:
        """Validate and store a three-way proposal."""
        for label, val in [("obvious", obvious), ("option", option), ("odd", odd)]:
            if not val or not val.strip():
                raise ValueError(f"{label} must be non-empty")
            if len(val) > 500:
                raise ValueError(f"{label} too long (max 500)")
        p = Proposal(
            character=character,
            situation=situation,
            obvious=obvious.strip(),
            option=option.strip(),
            odd=odd.strip(),
            traits=list(traits or []),
        )
        self.history.append({"event": "propose", **p.as_dict()})
        return p

    def resolve(self, proposal: Proposal, advantage: Advantage = None) -> dict[str, Any]:
        """Roll and select one of the three proposed branches."""
        roll_res = self.roll(advantage=advantage)
        choice = proposal.choice_for(roll_res.category)
        out: dict[str, Any] = {
            "character": proposal.character,
            "situation": proposal.situation,
            "traits": proposal.traits,
            "roll": roll_res.roll,
            "rolls": roll_res.rolls,
            "category": roll_res.category,
            "advantage": advantage,
            "choice": choice,
            "proposal": proposal.as_dict(),
        }
        self.history.append({"event": "resolve", **out})
        return out

    # ------------------------------------------------------------------
    # Group decision helper
    # ------------------------------------------------------------------
    def group_resolve(
        self,
        traits: list[str],
        plans: list[str],
        assignment: Literal["auto", "given"] = "auto",
        obvious_plan: str | None = None,
        option_plan: str | None = None,
        odd_plan: str | None = None,
        advantage: Advantage = None,
    ) -> dict[str, Any]:
        """Resolve a party-level dilemma.

        Either supply ``plans`` (len 3, auto-assigned: 0→obvious,1→option,2→odd)
        or supply explicit ``obvious_plan``/``option_plan``/``odd_plan``.
        """
        if assignment == "auto":
            if len(plans) != 3:
                raise ValueError("group_resolve auto needs exactly 3 plans")
            mapping: dict[Category, str] = {"obvious": plans[0], "option": plans[1], "odd": plans[2]}
        else:
            if not (obvious_plan and option_plan and odd_plan):
                raise ValueError("group_resolve given needs all three plans")
            mapping = {"obvious": obvious_plan, "option": option_plan, "odd": odd_plan}
        roll_res = self.roll(advantage=advantage)
        choice = mapping[roll_res.category]
        out: dict[str, Any] = {
            "traits": traits,
            "plans": mapping,
            "roll": roll_res.roll,
            "rolls": roll_res.rolls,
            "category": roll_res.category,
            "choice": choice,
            "advantage": advantage,
        }
        self.history.append({"event": "group_resolve", **out})
        return out

    # ------------------------------------------------------------------
    # Question resolution helper (Do they search for traps? etc.)
    # ------------------------------------------------------------------
    def question(self, question: str, yes_is_obvious: bool = True, advantage: Advantage = None) -> dict[str, Any]:
        """Answer a GM question via Triple-O.

        Returns qualitative guidance:
          obvious → Yes, thoroughly
          option  → Partial / compromise
          odd     → No / ignore & rush in
        The boolean ``yes_is_obvious`` flips mapping if the expected answer
        is "no" (e.g. for suspicious characters "no" may be obvious).
        """
        roll_res = self.roll(advantage=advantage)
        # Map category to answer flavour
        if roll_res.category == "obvious":
            answer = "Yes, thoroughly" if yes_is_obvious else "No — as Traits predict"
        elif roll_res.category == "option":
            answer = "Partial / compromise"
        else:
            answer = "No / rush in" if yes_is_obvious else "Yes — unexpected / impulsive"
        out = {
            "question": question,
            "roll": roll_res.roll,
            "rolls": roll_res.rolls,
            "category": roll_res.category,
            "answer": answer,
            "yes_is_obvious": yes_is_obvious,
        }
        self.history.append({"event": "question", **out})
        return out
