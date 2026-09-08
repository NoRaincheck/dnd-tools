"""fused — Fused TTRPG: scenes + Triple-O creativity + OKF event bundle.

Implements GH issue #4 (fused ruleset):

- **Creativity via Triple-O** (Obvious/Option/Odd, 1d6 seeded) as middleware that
  constrains LLM option space while injecting randomness — reduces
  hallucinatory freedom, forces trait-driven branches.
- **Narrative structure via scenes** — a campaign is a sequence of scenes with
  objectives, patrons, threats, beats, and cast. Scenes are OKF concepts.
- **OKF event bundle** (https://okf.md/spec) — every effect/event is an
  append-only concept (type: Effect) in an OKF bundle; traits are kept in a
  separate store (type: Trait) so agents can traverse history without
  conflating stable traits with transient event state. Bundle is
  git-cloneable markdown+YAML, traversable via `traverse_history` /
  `get_context` tools.
- **Deterministic, tool-grounded** — all rolls via seeded dnd_tools.dice;
  authoritative state via dnd_campaign.CampaignState; no raw LLM strings as truth.

Paper code in ``dnd_tools`` and ``dnd_campaign`` remains untouched.
``FusedState`` wraps ``CampaignState`` and adds traits_registry + scenes +
effects + OKF export. ``FusedTools`` exposes a unified schema for the
harness. ``FusedSession`` orchestrates multi-scene campaigns.

Quickstart::

    uv sync
    uv run fused demo --seed 42 --turns 12
    cat knowledge/fused-demo/index.md
    uv run fused demo --seed 42 --bundle /tmp/my-bundle && cat /tmp/my-bundle/log.md
"""

from __future__ import annotations

from .memory import build_agent_context, compact_fused_transcript, summarize_fused
from .models import CampaignBundleMeta, CharacterTraits, Effect, Scene, SceneStatus
from .okf import OKFBundle
from .session import FusedSession
from .state import FusedState
from .tools import FusedTools

__all__ = [
    "CampaignBundleMeta",
    "CharacterTraits",
    "Effect",
    "FusedSession",
    "FusedState",
    "FusedTools",
    "OKFBundle",
    "Scene",
    "SceneStatus",
    "build_agent_context",
    "compact_fused_transcript",
    "summarize_fused",
]
