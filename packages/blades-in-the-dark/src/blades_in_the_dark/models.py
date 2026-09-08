"""Blades in the Dark data models — playbooks, actions, stress/trauma/harm, clocks, crew.

Derived from ref/blades-in-the-dark.md (SRD CC BY 3.0, condensed).
"""

from __future__ import annotations

import dataclasses
import enum

# ---------------------------------------------------------------------------
# Constants from SRD
# ---------------------------------------------------------------------------

ACTIONS: list[str] = [
    "Hunt",
    "Study",
    "Survey",
    "Tinker",  # Insight
    "Finesse",
    "Prowl",
    "Skirmish",
    "Wreck",  # Prowess
    "Attune",
    "Command",
    "Consort",
    "Sway",  # Resolve
]

ACTION_TO_ATTR: dict[str, str] = {
    "Hunt": "Insight",
    "Study": "Insight",
    "Survey": "Insight",
    "Tinker": "Insight",
    "Finesse": "Prowess",
    "Prowl": "Prowess",
    "Skirmish": "Prowess",
    "Wreck": "Prowess",
    "Attune": "Resolve",
    "Command": "Resolve",
    "Consort": "Resolve",
    "Sway": "Resolve",
}

ATTRIBUTES: list[str] = ["Insight", "Prowess", "Resolve"]

PLAYBOOKS: list[str] = ["Cutter", "Hound", "Leech", "Lurk", "Slide", "Spider", "Whisper"]

CREW_TYPES: list[str] = ["Assassins", "Bravos", "Cult", "Hawkers", "Shadows", "Smugglers"]

TRAUMA_NAMES: list[str] = ["Cold", "Haunted", "Obsessed", "Paranoid", "Reckless", "Soft", "Unstable", "Vicious"]

VICES: list[str] = ["Faith", "Gambling", "Luxury", "Obligation", "Pleasure", "Stupor", "Weird"]


class Position(str, enum.Enum):
    controlled = "controlled"
    risky = "risky"
    desperate = "desperate"


class Effect(str, enum.Enum):
    zero = "zero"
    limited = "limited"
    standard = "standard"
    great = "great"
    extreme = "extreme"


# Effect → clock ticks (SRD §Effect; extreme = 5 common house rule)
EFFECT_TICKS: dict[str, int] = {"zero": 0, "limited": 1, "standard": 2, "great": 3, "extreme": 5}


# ---------------------------------------------------------------------------
# Character / Crew
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class HarmEntry:
    level: int  # 1 lesser, 2 moderate, 3 severe, 4 fatal
    name: str
    description: str = ""
    healing_clock: int = 4  # segments for healing this harm (usually 4)


@dataclasses.dataclass
class BladesCharacter:
    name: str
    playbook: str = "Cutter"
    actions: dict[str, int] = dataclasses.field(default_factory=dict)
    stress: int = 0
    stress_max: int = 9
    trauma: list[str] = dataclasses.field(default_factory=list)
    harm: list[HarmEntry] = dataclasses.field(default_factory=list)
    vice: str = "Pleasure"
    vice_purveyor: str = ""
    xp: int = 0
    load: int = 5
    armor: bool = False
    heavy: bool = False
    special_abilities: list[str] = dataclasses.field(default_factory=list)
    friends: list[str] = dataclasses.field(default_factory=list)
    rivals: list[str] = dataclasses.field(default_factory=list)
    # map/runtime
    pos: tuple[int, int, int] = (0, 0, 0)
    alive: bool = True  # false when 4 trauma or fatal harm unresisted
    is_player: bool = True
    # per-roll gate: pending position/effect and bonus dice already accounted?
    _pending_position: str | None = None
    _pending_effect: str | None = None
    _pending_action: str | None = None
    _assist_bonus: int = 0  # +1 if assisted this roll
    _push_bonus: str | None = None  # "dice" or "effect"
    _devil_bargain: str | None = None

    def __post_init__(self) -> None:
        # normalize actions
        if not self.actions:
            # default 1 dot spread like playbook chargen: 3/2/1/1 etc simplified
            self.actions = {a: 0 for a in ACTIONS}
            # give 1 dot to a couple signature actions for playbook flavor
            defaults: dict[str, list[str]] = {
                "Cutter": ["Skirmish", "Wreck"],
                "Hound": ["Hunt", "Survey"],
                "Leech": ["Tinker", "Wreck"],
                "Lurk": ["Prowl", "Finesse"],
                "Slide": ["Sway", "Consort"],
                "Spider": ["Consort", "Command"],
                "Whisper": ["Attune", "Study"],
            }
            for act in defaults.get(self.playbook, ["Skirmish"]):
                self.actions[act] = 1
        # fill missing actions with 0
        for a in ACTIONS:
            self.actions.setdefault(a, 0)
            if not 0 <= self.actions[a] <= 4:
                raise ValueError(f"action {a} must be 0-4, got {self.actions[a]}")
        # normalize trauma check
        if len(self.trauma) >= 4:
            # retain but mark alive false if fatal logic later will handle? keep for now
            pass

    def attr_rating(self, attr: str) -> int:
        """Attribute rating = sum of action dots in that attribute (SRD). Zero → 2d6kL rule."""
        attr = attr.capitalize()
        members = [a for a, at in ACTION_TO_ATTR.items() if at == attr]
        return sum(self.actions.get(m, 0) for m in members)

    def action_rating(self, action: str) -> int:
        return self.actions.get(_norm_action(action), 0)

    @property
    def retired(self) -> bool:
        return len(self.trauma) >= 4 or not self.alive


def _norm_action(a: str) -> str:
    # case-insensitive, title-case first letter
    for cand in ACTIONS:
        if cand.lower() == a.strip().lower():
            return cand
    raise ValueError(f"unknown action '{a}' (expected one of {ACTIONS})")


# ---------------------------------------------------------------------------
# Clock
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class BladesClock:
    name: str
    segments: int = 6  # 4/6/8 usually
    ticks: int = 0
    kind: str = "obstacle"  # obstacle/danger/project/healing/turf

    def add_ticks(self, n: int) -> int:
        self.ticks = max(0, min(self.segments, self.ticks + int(n)))
        return self.ticks

    @property
    def completed(self) -> bool:
        return self.ticks >= self.segments

    @property
    def remaining(self) -> int:
        return max(0, self.segments - self.ticks)


# ---------------------------------------------------------------------------
# Crew (minimal for score)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Crew:
    name: str = "The Crew"
    crew_type: str = "Shadows"
    tier: int = 0  # 0-4
    hold: str = "weak"  # weak/strong
    rep: int = 0
    heat: int = 0  # 0-9
    wanted_level: int = 0  # 0-4
    coin: int = 0
    stash: int = 0
