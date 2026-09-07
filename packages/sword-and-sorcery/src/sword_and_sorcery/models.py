"""Swords & Sorcery data models — S&S number, HP/SP/WD/EN, spells, monsters.

Derived directly from ref/sword-and-sorcery.md (v1.1, 2020).
"""

from __future__ import annotations

import dataclasses
import enum
import random

# ---------------------------------------------------------------------------
# Enumerations / tables from the one-pager
# ---------------------------------------------------------------------------

ANCESTRIES: list[str] = ["Human", "Elf", "Dwarf", "Gnome", "Orc", "Catfolk"]
BACKGROUNDS: list[str] = ["Noble", "Sage", "Thief", "Soldier", "Tracker", "Entertainer"]

PATRONS: list[str] = [
    "Mage-King Tholex XI",
    "Lord Garrington",
    "The Hunters' Guild",
    "Wizard Nimdronde",
    "The Thieves' Guild",
    "The Conclave",
]

QUESTS: list[str] = [
    "Slay the Helvella Dragon",
    "Destroy the ancient seal",
    "Investigate a murder",
    "Recover the Lǎo Mei",
    "Deliver some Wyldfyre",
    "Capture the bandits",
]

LOCATIONS: list[str] = [
    "The Wilderlands",
    "The Undercity",
    "Tanglewood",
    "The Planegate",
    "Fröstfell",
    "The Fissure",
]

THREATS: list[str] = [
    "The Necromancer",
    "Cultists",
    "Archduke Tallan",
    "The Queen of Wasps",
    "The One-Eyed Prince",
    "The Great Old One",
]

SPELL_TABLE: dict[int, list[str]] = {
    0: ["Illuminate", "Telepathy", "Mend", "Minor Illusion"],
    1: ["Beast-Speak", "Icebolt", "Friendship", "Grease"],
    2: ["Heal", "Invisibility", "Fireball", "Resize", "Animate"],
    3: ["Flight", "Darkness", "Lightning Storm", "Summon"],
}

ALL_SPELLS: list[str] = [s for spells in SPELL_TABLE.values() for s in spells]

MONSTER_TABLE: dict[str, dict[str, int]] = {
    "Easy": {"HP": 5, "DMG": 2},
    "Medium": {"HP": 10, "DMG": 3},
    "Hard": {"HP": 20, "DMG": 4},
    "Deadly": {"HP": 30, "DMG": 6},
}

# Reverse lookup for validation
SPELL_LEVEL: dict[str, int] = {spell.lower(): lvl for lvl, spells in SPELL_TABLE.items() for spell in spells}


class Ability(str, enum.Enum):
    swords = "swords"
    sorcery = "sorcery"


# ---------------------------------------------------------------------------
# Helpers — derived attributes
# ---------------------------------------------------------------------------


def derived_hp(sns: int) -> int:
    return 3 * sns


def derived_sp(sns: int) -> int:
    return 10 - (2 * sns)


def derived_wd(sns: int) -> int:
    return sns - 1


def derived_en(sns: int) -> int:
    return sns + 3


def roll_sns_number(rng: random.Random | None = None) -> int:
    """Roll 1d6 reroll 1s and 6s → 2-5 (S&S number)."""
    r = rng or random
    while True:
        v = r.randint(1, 6)
        if 2 <= v <= 5:
            return v


# ---------------------------------------------------------------------------
# SnSCharacter — player adventurer
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SnSCharacter:
    name: str
    ancestry: str = "Human"
    background: str = "Soldier"
    sns: int = 3  # 2-5
    hp: int = 0
    hp_max: int = 0
    sp: int = 0
    sp_max: int = 0
    wd: int = 0
    en: int = 0
    spells_known: list[str] = dataclasses.field(default_factory=list)
    inventory: list[str] = dataclasses.field(default_factory=list)
    # map/runtime
    pos: tuple[int, int, int] = (0, 0, 0)
    alive: bool = True
    is_player: bool = True
    unconscious: bool = False  # 0 HP — one chance to save before death
    # per-roll gate: helping bonus for next roll, karma quirk stuff needs?
    _help_bonus: int = 0
    _pending_help_from: str | None = None

    def __post_init__(self) -> None:
        if not 2 <= self.sns <= 5:
            raise ValueError(f"S&S number must be 2-5, got {self.sns}")
        if self.hp_max == 0:
            self.hp_max = derived_hp(self.sns)
        if self.hp == 0:
            self.hp = self.hp_max
        if self.sp_max == 0:
            self.sp_max = derived_sp(self.sns)
        if self.sp == 0:
            self.sp = self.sp_max
        if self.wd == 0:
            self.wd = derived_wd(self.sns)
        if self.en == 0:
            self.en = derived_en(self.sns)
        # normalize spells: if not set, pick from table based on SP budget
        if not self.spells_known and self.sp_max > 0:
            # assign up to sp_max spells, prioritising low levels
            pool = []
            for lvl in sorted(SPELL_TABLE):
                pool.extend(SPELL_TABLE[lvl])
            # simple deterministic selection: take first sp_max
            self.spells_known = pool[: self.sp_max]

    @property
    def retired(self) -> bool:
        return not self.alive


# ---------------------------------------------------------------------------
# Monster — HP + DMG only per one-pager
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SnSMonster:
    name: str
    threat: str = "Medium"  # Easy|Medium|Hard|Deadly
    hp: int = 0
    hp_max: int = 0
    dmg: int = 0
    pos: tuple[int, int, int] = (0, 0, 0)
    alive: bool = True
    is_player: bool = False

    def __post_init__(self) -> None:
        if self.threat not in MONSTER_TABLE:
            raise ValueError(f"threat must be one of {list(MONSTER_TABLE)}, got {self.threat}")
        if self.hp_max == 0:
            self.hp_max = MONSTER_TABLE[self.threat]["HP"]
        if self.hp == 0:
            self.hp = self.hp_max
        if self.dmg == 0:
            self.dmg = MONSTER_TABLE[self.threat]["DMG"]


# ---------------------------------------------------------------------------
# Adventure generation helpers
# ---------------------------------------------------------------------------


def roll_adventure(rng: random.Random | None = None) -> dict[str, str]:
    r = rng or random
    return {
        "patron": r.choice(PATRONS),
        "quest": r.choice(QUESTS),
        "location": r.choice(LOCATIONS),
        "threat": r.choice(THREATS),
    }
