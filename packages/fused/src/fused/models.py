"""Fused models — traits separate from event state, scenes as narrative structure.

Per GH issue #4: character traits are maintained separate to the event state
so an Agent can traverse history without conflating stable traits with
transient effects. Scenes provide narrative structure; Triple-O provides
creativity inside that structure; OKF bundle records effects for traversal.
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

    A campaign is a sequence of scenes; each scene has beats and an OKF concept.
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
class CampaignBundleMeta:
    name: str = "fused-campaign"
    description: str = "Fused TTRPG campaign — Triple-O + scenes + OKF event bundle"
    seed: int = 0
    scenes: int = 0
    effects: int = 0
