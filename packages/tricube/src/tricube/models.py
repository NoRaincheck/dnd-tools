"""Tricube Tales data models — karma/resolve/afflictions/rank/trait.

Uses dnd_tools.models.Cell for map compat; otherwise independent of 5e HP/AC.
"""

from __future__ import annotations

import dataclasses
import enum

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Trait(str, enum.Enum):
    agile = "agile"
    brawny = "brawny"
    crafty = "crafty"


class CombatStyle(str, enum.Enum):
    melee = "melee"
    ranged = "ranged"
    mental = "mental"


# Trait → default combat style
TRAIT_DEFAULT_STYLE: dict[str, str] = {
    Trait.agile.value: CombatStyle.ranged.value,
    Trait.brawny.value: CombatStyle.melee.value,
    Trait.crafty.value: CombatStyle.mental.value,
}


# ---------------------------------------------------------------------------
# Affliction
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Affliction:
    name: str
    permanent: bool = False
    recovery: str = "scene"  # scene|hours|days|weeks|months|years|permanent
    location: str | None = None
    source: str | None = None


# ---------------------------------------------------------------------------
# TricubeCharacter
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class TricubeCharacter:
    name: str
    trait: str  # agile|brawny|crafty
    concept: str  # e.g. "elven ranger"
    combat_style: str = ""  # melee|ranged|mental (frozen at creation)
    perks: list[str] = dataclasses.field(default_factory=list)
    quirks: list[str] = dataclasses.field(default_factory=list)
    afflictions: list[Affliction] = dataclasses.field(default_factory=list)
    karma: int = 3
    karma_max: int = 3
    resolve: int = 3
    resolve_max: int = 3
    rank: int = 1  # 1..6
    advances: int = 0
    xp: int = 0
    # map/runtime
    pos: tuple[int, int, int] = (0, 0, 0)
    initiative: int = 0
    alive: bool = True  # false when retired (>3 afflictions) or eliminated
    is_player: bool = True
    # active-quirk/karma gate: set by tools during a challenge
    _pending_quirk: str | None = None
    _karma_spent_this_challenge: bool = False
    # transient effort init (not persisted)
    _effort_init: int | None = None

    def __post_init__(self) -> None:
        if not self.combat_style:
            self.combat_style = TRAIT_DEFAULT_STYLE.get(self.trait, CombatStyle.melee.value)
        self.trait = self.trait.lower()
        self.combat_style = self.combat_style.lower()

    def dice_count_for(self, required_trait: str, *, out_of_scope: bool = False) -> int:
        """Tales archetype rule: 3d6 if trait matches, 2d6 else, −1 if out-of-scope (min 1)."""
        base = 3 if self.trait == required_trait.lower() else 2
        if out_of_scope:
            base = max(1, base - 1)
        return base

    @property
    def retired(self) -> bool:
        return len(self.afflictions) > 3


# ---------------------------------------------------------------------------
# Rank / Effort helpers (Hack-and-Slash)
# ---------------------------------------------------------------------------


def rank_from_advances(advances: int) -> int:
    """PC rank: 1 + floor(advances/4), max 6."""
    return min(6, 1 + advances // 4)


BESTIARY: dict[str, dict] = {
    "bear": {"rank": 2, "traits": ["brawny"]},
    "dragon": {"rank": 5, "traits": ["brawny", "crafty"]},
    "goblin": {"rank": 1, "traits": ["agile", "weak"]},
    "golem": {"rank": 3, "traits": ["brawny", "stupid"]},
    "lich": {"rank": 4, "traits": ["crafty"]},
    "ogre": {"rank": 2, "traits": ["brawny", "stupid"]},
    "kobold": {"rank": 1, "traits": ["stupid", "weak"]},
    "skeleton": {"rank": 1, "traits": ["stupid"]},
    "troll": {"rank": 2, "traits": ["brawny", "stupid"]},
    "vampire": {"rank": 3, "traits": ["agile"]},
    "wolf": {"rank": 1, "traits": []},
    "wraith": {"rank": 2, "traits": []},
    "yeti": {"rank": 2, "traits": ["brawny"]},
    "zombie": {"rank": 1, "traits": ["clumsy", "stupid"]},
}


def effort_for_rank(rank: int, *, is_boss: bool = False) -> int:
    """Most monsters = rank effort; boss = 2*rank."""
    return (2 * rank) if is_boss else rank


# keep small helpers for tools
TRAITS = {t.value for t in Trait}
