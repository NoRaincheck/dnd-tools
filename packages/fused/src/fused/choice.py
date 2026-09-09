"""Choice engine — Triple-O + Blades Position/Effect + Burning Wheel Say Yes.

Campaign unfolding is a sequence of Choices. At each dilemma the LLM proposes
three branches via Triple-O (Obvious/Option/Odd, 1d6). Before rolling, stakes are
assessed via Position/Effect. If trivial (controlled, limited/standard, no clock
threat, not belief-critical), Say Yes auto-resolves to Obvious with a visible
trivial flag — no dice consumed, deterministic sequence preserved.

This satisfies:
- choices derived by LLM (Triple-O proposal is LLM-authored)
- Blades gate remains hard (cannot soften without Position)
- Burning Wheel Say Yes handles low-risk auto-resolve while still logging
- GUMSHOE core-clue spirit: automatic if you are capable and stakes are nil
"""

from __future__ import annotations

from typing import Any

from triple_o.core import TripleO

from .models import Choice

TRIVIAL_POSITION = "controlled"
TRIVIAL_EFFECTS = {"limited", "standard", "zero"}


def assess_trivial(
    position: str,
    effect: str,
    situation: str,
    actor_traits: list[str] | None = None,
    scene_threat: str | None = None,
    clock_ticks_remaining: int | None = None,
) -> tuple[bool, str]:
    """Rule-based trivial assessment for Say Yes.

    Burning Wheel heuristic: Say Yes if failure has no interesting consequence.
    Heuristic signals:
    - Position controlled (not risky/desperate)
    - Effect limited/standard/zero (not great/extreme)
    - Situation wording signals low stakes (no threat clock, no enemy, no belief challenge)
    - Scene threat is 'none' / 'unknown' / empty
    """
    pos = position.lower()
    eff = effect.lower()
    trivial = False
    reasons: list[str] = []
    low_text = (situation or "").lower()
    explicit_trivial = "trivial" in low_text or "low risk" in low_text or "easy" in low_text
    if pos == TRIVIAL_POSITION and eff in TRIVIAL_EFFECTS:
        # require low threat or explicit tag for standard to be trivial
        if eff == "limited":
            trivial = True
            reasons.append("position=controlled")
            reasons.append(f"effect={eff}")
        elif eff in ("standard", "zero"):
            if explicit_trivial:
                trivial = True
                reasons.append("position=controlled")
                reasons.append(f"effect={eff}")
                reasons.append("explicit trivial tag")
            elif not scene_threat or scene_threat.lower() in ("none", "unknown", ""):
                trivial = True
                reasons.append("position=controlled")
                reasons.append(f"effect={eff}")
                reasons.append("no threat")
            else:
                trivial = False
        else:
            trivial = False
    # downgrade trivial if threat/clock suggests stakes via keywords
    high_stakes_keywords = ["ambush", "combat", "trap", "dying", "ritual", "boss", "dragon", "doom", "desperate"]
    has_high = any(k in low_text for k in high_stakes_keywords)
    if has_high and trivial and eff != "limited":
        trivial = False
        reasons.append("high-stakes keywords override → not trivial")
    if trivial:
        return True, "Say Yes — trivial stakes: " + ", ".join(reasons)
    # also allow explicit 'trivial' tag for effects outside TRIVIAL_EFFECTS (e.g. great with controlled) — fallback
    # but do not re-enable if high-stakes already downgraded a standard/zero trivial
    if explicit_trivial and pos == TRIVIAL_POSITION and eff not in TRIVIAL_EFFECTS:
        return True, "Say Yes — situation tagged trivial/low-risk"
    return False, ""


class ChoiceResolver:
    """Resolves a Choice via Triple-O + trivial gate. Deterministic via seeded TripleO."""

    def __init__(self, seed: int = 0, triple_o: TripleO | None = None):
        self.seed = seed
        self.triple_o = triple_o or TripleO(seed=seed)
        self.history: list[dict[str, Any]] = []

    def propose(
        self,
        choice_id: str,
        scene_id: str,
        actor: str,
        situation: str,
        obvious: str,
        option: str,
        odd: str,
        traits: list[str] | None = None,
        position: str = "risky",
        effect: str = "standard",
    ) -> Choice:
        for label, val in [("obvious", obvious), ("option", option), ("odd", odd)]:
            if not val or not val.strip():
                raise ValueError(f"{label} must be non-empty")
            if len(val) > 500:
                raise ValueError(f"{label} too long (max 500)")
        c = Choice(
            choice_id=choice_id,
            scene_id=scene_id,
            actor=actor,
            situation=situation,
            obvious=obvious.strip(),
            option=option.strip(),
            odd=odd.strip(),
            traits=list(traits or []),
            position=position.lower(),
            effect=effect.lower(),
        )
        return c

    def resolve(
        self,
        choice: Choice,
        scene_threat: str | None = None,
        clock_ticks_remaining: int | None = None,
        advantage: str | None = None,
        force_roll: bool = False,
    ) -> Choice:
        trivial, reason = assess_trivial(
            choice.position, choice.effect, choice.situation, choice.traits, scene_threat, clock_ticks_remaining
        )
        if trivial and not force_roll:
            choice.trivial = True
            choice.trivial_reason = reason
            choice.category = "obvious"
            choice.choice_text = choice.obvious
            choice.resolved_via = "say_yes"
            choice.rolls = []
            choice.roll = None
            choice.ticks = 0 if choice.effect == "zero" else 1
            choice.payload = {"say_yes": True, "reason": reason, "position": choice.position, "effect": choice.effect}
            self.history.append({"event": "say_yes", "choice_id": choice.choice_id, "reason": reason})
            return choice
        # non-trivial: roll Triple-O 1d6 (or 2d6 advantage)
        adv = advantage if advantage in ("advantage", "disadvantage") else None
        roll_res = self.triple_o.roll(advantage=adv)  # type: ignore[arg-type]
        category = roll_res.category
        choice.roll = roll_res.roll
        choice.rolls = list(roll_res.rolls)
        choice.category = category
        if category == "obvious":
            choice.choice_text = choice.obvious
        elif category == "option":
            choice.choice_text = choice.option
        else:
            choice.choice_text = choice.odd
        choice.trivial = False
        choice.resolved_via = "rolled"
        # ticks via Blades EFFECT_TICKS (limited1/standard2/great3)
        from .models import EFFECT_TICKS

        base = EFFECT_TICKS.get(choice.effect, 2)
        if category == "odd" and choice.effect == "great":
            base = min(5, base + 1)
        choice.ticks = base
        choice.payload = {
            "roll": choice.roll,
            "rolls": choice.rolls,
            "category": category,
            "position": choice.position,
            "effect": choice.effect,
            "advantage": adv,
        }
        self.history.append(
            {"event": "resolve", "choice_id": choice.choice_id, "category": category, "roll": choice.roll}
        )
        return choice
