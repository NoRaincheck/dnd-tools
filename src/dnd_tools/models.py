"""Core data models for D&D simulation — 5e-compatible, lightweight."""

from __future__ import annotations

import dataclasses
import enum

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DamageType(str, enum.Enum):
    bludgeoning = "bludgeoning"
    piercing = "piercing"
    slashing = "slashing"
    fire = "fire"
    cold = "cold"
    radiant = "radiant"
    necrotic = "necrotic"
    psychic = "psychic"
    poison = "poison"
    acid = "acid"
    force = "force"
    lightning = "lightning"
    thunder = "thunder"


class WeaponCategory(str, enum.Enum):
    melee = "melee"
    ranged = "ranged"


class SpellRangeKind(str, enum.Enum):
    self_ = "self"
    touch = "touch"
    feet = "feet"


# ---------------------------------------------------------------------------
# Weapon / Spell data-bases
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Weapon:
    name: str
    category: WeaponCategory
    damage_dice: str  # e.g. "1d8"
    damage_type: DamageType
    range_normal: int = 5  # feet, 5 = melee
    range_long: int | None = None
    properties: tuple[str, ...] = ()
    modifier_stat: str = "strength"  # or dexterity for finesse/range


MELEE_WEAPONS: dict[str, Weapon] = {
    "club": Weapon("club", WeaponCategory.melee, "1d4", DamageType.bludgeoning),
    "quarterstaff": Weapon(
        "quarterstaff",
        WeaponCategory.melee,
        "1d6",
        DamageType.bludgeoning,
        properties=("versatile",),
    ),
    "shortsword": Weapon(
        "shortsword",
        WeaponCategory.melee,
        "1d6",
        DamageType.piercing,
        properties=("finesse",),
        modifier_stat="dexterity",
    ),
    "longsword": Weapon(
        "longsword",
        WeaponCategory.melee,
        "1d8",
        DamageType.slashing,
        properties=("versatile",),
    ),
    "greatsword": Weapon("greatsword", WeaponCategory.melee, "2d6", DamageType.slashing),
    "dagger": Weapon(
        "dagger",
        WeaponCategory.melee,
        "1d4",
        DamageType.piercing,
        properties=("finesse", "thrown"),
        range_normal=20,
        range_long=60,
    ),
    "mace": Weapon("mace", WeaponCategory.melee, "1d6", DamageType.bludgeoning),
}

RANGED_WEAPONS: dict[str, Weapon] = {
    "short bow": Weapon(
        "Short Bow",
        WeaponCategory.ranged,
        "1d6",
        DamageType.piercing,
        range_normal=80,
        range_long=320,
        modifier_stat="dexterity",
    ),
    "longbow": Weapon(
        "Longbow",
        WeaponCategory.ranged,
        "1d8",
        DamageType.piercing,
        range_normal=150,
        range_long=600,
        modifier_stat="dexterity",
    ),
    "light crossbow": Weapon(
        "Light Crossbow",
        WeaponCategory.ranged,
        "1d8",
        DamageType.piercing,
        range_normal=80,
        range_long=320,
        modifier_stat="dexterity",
    ),
    "heavy crossbow": Weapon(
        "Heavy Crossbow",
        WeaponCategory.ranged,
        "1d10",
        DamageType.piercing,
        range_normal=100,
        range_long=400,
        modifier_stat="dexterity",
    ),
}

# Unified lookups (case-insensitive)
ALL_WEAPONS: dict[str, Weapon] = {k.lower(): v for k, v in {**MELEE_WEAPONS, **RANGED_WEAPONS}.items()}
MELEE_SET = set(MELEE_WEAPONS.keys())
RANGED_SET = set(RANGED_WEAPONS.keys())

# ---------------------------------------------------------------------------
# Spell definitions (subset from paper appendix — 19 canonical)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SpellDef:
    name: str
    cost_action: int = 1  # 0/1 action
    cost_bonus: int = 0
    cost_slot: int = 0  # 0 = cantrip
    range_kind: SpellRangeKind = SpellRangeKind.feet
    range_feet: int = 30
    damage_dice: str | None = None
    damage_type: DamageType | None = None
    concentration: bool = False
    save_ability: str | None = None  # e.g. "dexterity"
    attack_roll: bool = True  # True = spell attack, False = save
    effect: str = ""
    higher_slot_dice: str | None = None  # extra dice per slot above base


def _s(name, **kw) -> SpellDef:
    return SpellDef(name=name, **kw)


SPELLS: dict[str, SpellDef] = {
    "fire bolt": _s(
        "Fire Bolt",
        cost_action=1,
        range_kind=SpellRangeKind.feet,
        range_feet=120,
        damage_dice="1d10",
        damage_type=DamageType.fire,
        attack_roll=True,
    ),
    "ray of frost": _s(
        "Ray of Frost",
        cost_action=1,
        range_kind=SpellRangeKind.feet,
        range_feet=60,
        damage_dice="1d8",
        damage_type=DamageType.cold,
        attack_roll=True,
        effect="speed -10 until next turn",
    ),
    "true strike": _s(
        "True Strike",
        cost_action=1,
        range_kind=SpellRangeKind.feet,
        range_feet=30,
        concentration=True,
        attack_roll=False,
        effect="advantage next attack",
    ),
    "sacred flame": _s(
        "Sacred Flame",
        cost_action=1,
        range_kind=SpellRangeKind.feet,
        range_feet=60,
        damage_dice="1d8",
        damage_type=DamageType.radiant,
        save_ability="dexterity",
        attack_roll=False,
    ),
    "chill touch": _s(
        "Chill Touch",
        cost_action=1,
        range_kind=SpellRangeKind.feet,
        range_feet=120,
        damage_dice="1d8",
        damage_type=DamageType.necrotic,
        attack_roll=True,
        effect="no heal + disadv vs undead",
    ),
    "vicious mockery": _s(
        "Vicious Mockery",
        cost_action=1,
        range_kind=SpellRangeKind.feet,
        range_feet=60,
        damage_dice="1d4",
        damage_type=DamageType.psychic,
        save_ability="wisdom",
        attack_roll=False,
        effect="disadv next attack",
    ),
    "resistance": _s(
        "Resistance",
        cost_action=1,
        range_kind=SpellRangeKind.touch,
        concentration=True,
        attack_roll=False,
        effect="+1d4 to one save within 10 turns",
    ),
    "poison spray": _s(
        "Poison Spray",
        cost_action=1,
        range_kind=SpellRangeKind.feet,
        range_feet=10,
        damage_dice="1d12",
        damage_type=DamageType.poison,
        save_ability="constitution",
        attack_roll=False,
    ),
    "acid splash": _s(
        "Acid Splash",
        cost_action=1,
        range_kind=SpellRangeKind.feet,
        range_feet=60,
        damage_dice="1d6",
        damage_type=DamageType.acid,
        save_ability="dexterity",
        attack_roll=False,
        effect="1 or 2 targets within 5ft",
    ),
    "eldritch blast": _s(
        "Eldritch Blast",
        cost_action=1,
        range_kind=SpellRangeKind.feet,
        range_feet=120,
        damage_dice="1d10",
        damage_type=DamageType.force,
        attack_roll=True,
    ),
    "blade ward": _s(
        "Blade Ward",
        cost_action=1,
        range_kind=SpellRangeKind.self_,
        attack_roll=False,
        effect="resistance bludg/pierce/slash weapon",
    ),
    "shocking grasp": _s(
        "Shocking Grasp",
        cost_action=1,
        range_kind=SpellRangeKind.touch,
        damage_dice="1d8",
        damage_type=DamageType.lightning,
        attack_roll=True,
        effect="no reactions; adv vs metal",
    ),
    "produce flame": _s(
        "Produce Flame",
        cost_action=1,
        range_kind=SpellRangeKind.self_,
        attack_roll=False,
        effect="hurl 30ft 1d8 fire next turns",
    ),
    "shillelagh": _s(
        "Shillelagh",
        cost_bonus=1,
        range_kind=SpellRangeKind.touch,
        attack_roll=False,
        effect="club/qstaff magical 1d8 with spell mod",
    ),
    "thorn whip": _s(
        "Thorn Whip",
        cost_action=1,
        range_kind=SpellRangeKind.feet,
        range_feet=30,
        damage_dice="1d6",
        damage_type=DamageType.piercing,
        attack_roll=True,
        effect="pull 10ft if large or smaller",
    ),
    "guiding bolt": _s(
        "Guiding Bolt",
        cost_action=1,
        cost_slot=1,
        range_kind=SpellRangeKind.feet,
        range_feet=120,
        damage_dice="4d6",
        damage_type=DamageType.radiant,
        attack_roll=True,
        effect="next attack adv",
        higher_slot_dice="1d6",
    ),
    "animal friendship": _s(
        "Animal Friendship",
        cost_action=1,
        cost_slot=1,
        range_kind=SpellRangeKind.feet,
        range_feet=30,
        save_ability="wisdom",
        attack_roll=False,
        effect="charm beast INT<4",
    ),
    "thunderous smite": _s(
        "Thunderous Smite",
        cost_bonus=1,
        cost_slot=1,
        range_kind=SpellRangeKind.self_,
        concentration=True,
        effect="+2d6 thunder + STR save or push 10 + prone",
    ),
}

# normalised key
SPELLS_NORM = {k.lower(): v for k, v in SPELLS.items()}

# ---------------------------------------------------------------------------
# Character
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Buff:
    name: str
    remaining_turns: int  # -1 = until removed
    description: str = ""


@dataclasses.dataclass
class ResistEntry:
    damage_type: str
    kind: str  # resist/immune/vulner
    remaining_turns: int = -1


@dataclasses.dataclass
class Character:
    name: str
    max_hp: int
    hp: int
    ac: int
    speed: int = 30
    speed_remaining: int = 30
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10
    pb: int = 2
    level: int = 1
    char_class: str = "fighter"
    size: str = "medium"
    monster_type: str = "humanoid"  # humanoid, beast, undead, etc.
    equipped_mainhand: str = "club"
    inventory: list[str] = dataclasses.field(default_factory=list)
    spell_list: list[str] = dataclasses.field(default_factory=list)
    spell_slots: dict[int, int] = dataclasses.field(default_factory=dict)  # level -> slots remaining
    spell_slots_max: dict[int, int] = dataclasses.field(default_factory=dict)
    num_of_action: int = 1
    num_of_bonus_action: int = 1
    num_of_reaction: int = 1
    initiative: int = 0
    pos: tuple[int, int, int] = (0, 0, 0)  # x,y,z
    buffs: list[Buff] = dataclasses.field(default_factory=list)
    resists: list[ResistEntry] = dataclasses.field(default_factory=list)
    concentration: str | None = None
    concentration_turns: int = 0
    temp_hp: int = 0
    is_player: bool = True
    alive: bool = True

    def ability_mod(self, ability: str) -> int:
        val = getattr(self, ability, 10)
        return (val - 10) // 2

    def spellcasting_mod(self) -> int:
        # simplified mapping per paper
        if self.char_class in ("sorcerer", "bard", "warlock", "paladin"):
            return self.ability_mod("charisma")
        if self.char_class in ("wizard", "rogue"):
            return self.ability_mod("intelligence")
        if self.char_class in ("cleric", "druid", "ranger"):
            return self.ability_mod("wisdom")
        return self.ability_mod("charisma")

    def spell_save_dc(self) -> int:
        return 8 + self.pb + self.spellcasting_mod()


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Cell:
    x: int
    y: int
    z: int  # height
    valid: bool = True


# Map is 2D list: map[y][x] -> Cell

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CLASSES = [
    "fighter",
    "wizard",
    "cleric",
    "rogue",
    "ranger",
    "paladin",
    "barbarian",
    "bard",
    "druid",
    "monk",
    "sorcerer",
    "warlock",
]

MONSTER_TEMPLATES: dict[str, dict] = {
    "goblin": {
        "max_hp": 7,
        "ac": 15,
        "speed": 30,
        "str": 8,
        "dex": 14,
        "con": 10,
        "int": 10,
        "wis": 8,
        "cha": 8,
        "weapon": "club",
        "type": "humanoid",
        "size": "small",
    },
    "bugbear": {
        "max_hp": 27,
        "ac": 16,
        "speed": 30,
        "str": 15,
        "dex": 14,
        "con": 13,
        "int": 8,
        "wis": 11,
        "cha": 9,
        "weapon": "mace",
        "type": "humanoid",
        "size": "medium",
    },
    "wolf": {
        "max_hp": 11,
        "ac": 13,
        "speed": 40,
        "str": 12,
        "dex": 15,
        "con": 12,
        "int": 3,
        "wis": 12,
        "cha": 6,
        "weapon": "club",
        "type": "beast",
        "size": "medium",
    },
    "klarg": {
        "max_hp": 35,
        "ac": 15,
        "speed": 30,
        "str": 16,
        "dex": 12,
        "con": 14,
        "int": 7,
        "wis": 10,
        "cha": 9,
        "weapon": "mace",
        "type": "humanoid",
        "size": "medium",
    },
}
