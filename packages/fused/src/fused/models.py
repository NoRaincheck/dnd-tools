"""Fused models — traits separate from event state, scenes as narrative structure.

Per GH issue #4: character traits are maintained separate to the event state
so an Agent can traverse history without conflating stable traits with
transient effects. Scenes provide narrative structure; Triple-O provides
creativity inside that structure; Clocks + Position/Effect impose the
Blades-grade gate (“cannot soften the blow”) per GH #11 joint SRD.

Follows ``ref/blades-in-the-dark.md`` (§3 Position/Effect, §4.2 Clocks) for
Position/Effect/consequence and ticks (archived synthesis; logic now folded
into this package).
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib


class SceneStatus(str, enum.Enum):
    planned = "planned"
    active = "active"
    resolved = "resolved"
    archived = "archived"


class Position(str, enum.Enum):
    controlled = "controlled"
    risky = "risky"
    desperate = "desperate"


class EffectLevel(str, enum.Enum):
    zero = "zero"
    limited = "limited"
    standard = "standard"
    great = "great"
    extreme = "extreme"


# Effect → clock ticks (SRD §Effect; extreme = 5 house rule) — see ref/blades-in-the-dark.md §4.2
EFFECT_TICKS: dict[str, int] = {"zero": 0, "limited": 1, "standard": 2, "great": 3, "extreme": 5}

# Consequence table verbatim (controlled/risky/desperate × partial/failure) — see ref/blades-in-the-dark.md §3.1
CONSEQUENCE_TABLE: dict[str, dict[str, list[str]]] = {
    "controlled": {
        "partial": [
            "minor complication occurs",
            "reduced effect (−1 tick or effect downgrade)",
            "lesser harm (level 1)",
            "fall to risky position",
        ],
        "failure": [
            "falter: press on by seizing a risky opportunity, or withdraw and try a different approach",
        ],
    },
    "risky": {
        "partial": [
            "harm (level 1-2)",
            "complication occurs",
            "reduced effect",
            "fall to desperate position",
        ],
        "failure": [
            "harm (level 1-2)",
            "complication occurs",
            "fall to desperate position",
            "lose this opportunity",
        ],
    },
    "desperate": {
        "partial": [
            "severe harm (level 2-3)",
            "serious complication occurs",
            "reduced effect",
        ],
        "failure": [
            "severe harm (level 2-3)",
            "serious complication occurs",
            "lose this opportunity for action",
        ],
    },
}


@dataclasses.dataclass
class Clock:
    """Progress clock — beats are ticks on a segmented track."""

    name: str
    segments: int = 6  # 4/6/8 common (blades)
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


@dataclasses.dataclass
class CharacterTraits:
    """Stable character traits — the engine for Triple-O decisions.

    Kept separate from event/effect state (HP/pos/effects) per issue #4.
    Maps to an OKF concept of type Trait / Character.
    """

    name: str
    ancestry: str = "human"
    background: str = "adventurer"
    archetype: str = "fighter"  # dnd class or tricube trait shorthand
    alignment: str = "neutral"
    # Triple-O relevant traits
    traits: list[str] = dataclasses.field(default_factory=list)
    # e.g. ["Always ready to fight", "Suspicious of authority"]
    flaws: list[str] = dataclasses.field(default_factory=list)
    fears: list[str] = dataclasses.field(default_factory=list)
    favored_skills: list[str] = dataclasses.field(default_factory=list)
    bonds: list[str] = dataclasses.field(default_factory=list)
    ideals: list[str] = dataclasses.field(default_factory=list)
    # mirrors for OKF link
    concept: str = ""  # free-form short snippet if perks/quirks not structured
    perk: str = ""
    quirk: str = ""

    def trait_summary(self) -> str:
        parts = [self.archetype, self.background, self.ancestry]
        if self.traits:
            parts.extend(self.traits)
        return ", ".join(parts)

    def okf_id(self) -> str:
        # slug for bundle path: traits/<name>.md
        slug = self.name.lower().replace(" ", "-").replace("/", "-")
        return f"traits/{slug}"

    def to_okf_frontmatter(self) -> dict[str, object]:
        return {
            "type": "Trait",
            "title": self.name,
            "description": self.trait_summary(),
            "tags": ["trait", self.archetype, self.background],
            "archetype": self.archetype,
            "ancestry": self.ancestry,
            "background": self.background,
            "alignment": self.alignment,
        }


@dataclasses.dataclass
class Scene:
    """Narrative scene — the unit of campaign structure.

    A campaign is a sequence of scenes; each scene has beats (strings, for
    backward compat) and/or explicit Clocks (progress tracks, per joint SRD).
    Beats auto-seed a default ``<scene_id>-progress`` 6-clock if no clocks
    are supplied — beats are shorthand, clocks are authoritative.
    """

    scene_id: str
    title: str
    objective: str
    location: str = "wilderlands"
    patron: str = "Guild"
    threat: str = "unknown"
    status: SceneStatus = SceneStatus.planned
    beats: list[str] = dataclasses.field(default_factory=list)
    # who participates (names must have traits registered)
    cast: list[str] = dataclasses.field(default_factory=list)
    # explicit clocks (authoritative progress); if empty and beats non-empty, a default clock is lazily created
    clocks: list[Clock] = dataclasses.field(default_factory=list)  # type: ignore[type-arg]
    # effect ids within this scene (filled by FusedState)
    effect_ids: list[str] = dataclasses.field(default_factory=list)
    seed: int = 0

    def okf_id(self) -> str:
        return f"scenes/{self.scene_id}"

    def to_okf_frontmatter(self) -> dict[str, object]:
        return {
            "type": "Scene",
            "title": self.title,
            "description": self.objective,
            "tags": ["scene", self.location, self.threat],
            "location": self.location,
            "patron": self.patron,
            "threat": self.threat,
            "status": self.status.value,
            "seed": self.seed,
        }


@dataclasses.dataclass
class Effect:
    """An effect/event recorded in the campaign — the OKF 'event state'.

    Separate from CharacterTraits per issue. Effects are append-only and
    together form traversable history.
    """

    effect_id: str
    scene_id: str
    actor: str
    kind: str  # move, attack, spell, save, buff, trait-application, triple-o, rest
    summary: str
    round: int = 0
    turn_actor: str | None = None
    payload: dict[str, object] = dataclasses.field(default_factory=dict)
    # deterministic hash for id stability
    timestamp: str = ""  # ISO8601, optional

    def okf_id(self) -> str:
        return f"events/{self.effect_id}"

    def to_okf_frontmatter(self) -> dict[str, object]:
        return {
            "type": "Effect",
            "title": f"{self.kind}: {self.actor}",
            "description": self.summary[:200],
            "tags": ["effect", self.kind, self.scene_id],
            "scene": self.scene_id,
            "actor": self.actor,
            "kind": self.kind,
            "round": self.round,
        }

    @staticmethod
    def make_id(scene_id: str, counter: int, kind: str, actor: str) -> str:
        base = f"{scene_id}-{counter:04d}-{kind}-{actor}"
        h = hashlib.sha256(base.encode()).hexdigest()[:8]
        return f"{scene_id}-{counter:04d}-{h}"


@dataclasses.dataclass
class Choice:
    """A campaign-level choice — LLM-proposed Triple-O branches + risk assessment.

    Mirrors Burning Wheel `Say Yes or Roll` and GUMSHOE core-clue automaticity:
    if stakes are trivial (Position=controlled, no clock/threat, not belief-critical)
    the Obvious branch auto-resolves via Say Yes — but still appears as a logged
    choice with reason, satisfying 'show it appeared as trivial'.
    """

    choice_id: str
    scene_id: str
    actor: str
    situation: str
    obvious: str
    option: str
    odd: str
    traits: list[str] = dataclasses.field(default_factory=list)
    # risk gate (Blades Position/Effect)
    position: str = "risky"
    effect: str = "standard"
    # assessment
    trivial: bool = False
    trivial_reason: str = ""
    # resolution
    roll: int | None = None
    rolls: list[int] = dataclasses.field(default_factory=list)
    category: str | None = None  # obvious/option/odd
    choice_text: str | None = None
    resolved_via: str = "rolled"  # rolled | say_yes | auto_trivial
    ticks: int = 0
    payload: dict[str, object] = dataclasses.field(default_factory=dict)

    @staticmethod
    def make_id(scene_id: str, counter: int, actor: str) -> str:
        base = f"{scene_id}-{counter:04d}-choice-{actor}"
        h = hashlib.sha256(base.encode()).hexdigest()[:8]
        return f"{scene_id}-choice-{counter:04d}-{h}"


@dataclasses.dataclass
class CampaignBundleMeta:
    name: str = "fused-campaign"
    description: str = "Fused TTRPG campaign — Triple-O + scenes + OKF event bundle"
    seed: int = 0
    scenes: int = 0
    effects: int = 0
