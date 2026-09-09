"""fused — Fused TTRPG: scenes + Triple-O creativity + JSONL event log.

Implements GH issues #4 + #8 (fused ruleset + canonical log):

- **Creativity via Triple-O** (Obvious/Option/Odd, 1d6 seeded) as middleware that
  constrains LLM option space while injecting randomness.
- **Narrative structure via scenes** — a campaign is a sequence of scenes with
  objectives, patrons, threats, beats, and cast.
- **Canonical JSONL event log** (``events.jsonl``, CloudEvents-compatible) +
  periodic **snapshots** (``snapshots/<seq>.json``) + **manifest** — single stream
  that is jq/duckdb/sqlite-queryable and replayable into ``FusedState``.
  Traits are kept in a separate store so agents can traverse history without
  conflating stable traits with transient event state.
- **Idempotent SQLite projection** (``projections/campaign.db``) — rebuildable
  from log + snapshots, never committed, ``build_projection`` is idempotent.
- **Deterministic, tool-grounded** — all rolls via seeded dnd_tools.dice;
  authoritative state via dnd_campaign.CampaignState; no raw LLM strings as truth.

Paper code in ``dnd_tools`` and ``dnd_campaign`` remains untouched.
``FusedState`` wraps ``CampaignState`` and adds traits_registry + scenes +
effects + event log. ``FusedTools`` exposes a unified schema for the
harness. ``FusedSession`` orchestrates multi-scene campaigns.

Quickstart::

    uv sync
    uv run fused demo --seed 42 --turns 12
    cat knowledge/fused-demo/events.jsonl | jq .
    uv run fused validate --log knowledge/fused-demo/events.jsonl
    uv run fused build-projection --log knowledge/fused-demo/events.jsonl --db /tmp/campaign.db
"""

from __future__ import annotations

from .events import append_event, iter_events, validate_event, validate_log
from .memory import build_agent_context, compact_fused_transcript, summarize_fused
from .models import CampaignBundleMeta, CharacterTraits, Effect, Scene, SceneStatus
from .projection import build_projection
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
    "Scene",
    "SceneStatus",
    "append_event",
    "build_agent_context",
    "build_projection",
    "compact_fused_transcript",
    "iter_events",
    "summarize_fused",
    "validate_event",
    "validate_log",
]
