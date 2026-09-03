"""Memory helpers for Tricube — bounded context for LLM."""

from __future__ import annotations

from typing import Any

from .state import TricubeCampaignState


def summarize_state(cstate: TricubeCampaignState) -> dict[str, Any]:
    inner = cstate.inner
    players = {
        n: {
            "trait": c.trait,
            "concept": c.concept,
            "karma": f"{c.karma}/{c.karma_max}",
            "resolve": f"{c.resolve}/{c.resolve_max}",
            "rank": c.rank,
            "pos": inner.players_pos.get(n),
            "afflictions": len(c.afflictions),
            "retired": c.retired,
        }
        for n, c in inner.players.items()
    }
    monsters = {
        n: {
            "resolve": f"{c.resolve}/{c.resolve_max}",
            "pos": inner.monster_pos.get(n),
            "effort": inner.effort_pools.get(n, 0),
            "alive": c.alive,
        }
        for n, c in inner.monsters.items()
    }
    # include pooled challenges that are not monster-named
    extra_effort = {k: v for k, v in inner.effort_pools.items() if k not in inner.monsters}
    return {
        "round": inner.round,
        "turn": inner.current_actor(),
        "players": players,
        "monsters": monsters,
        "effort_pools": extra_effort,
        "affliction_log": inner.affliction_log[-5:],
        "meta": dict(cstate.campaign_meta),
    }


def compact_transcript(cstate: TricubeCampaignState, keep_last: int = 40) -> str:
    t = cstate.inner.transcript
    if len(t) <= keep_last + 10:
        return "\n".join(t)
    head = "\n".join(t[:5])
    tail = "\n".join(t[-keep_last:])
    return head + f"\n... ({len(t) - keep_last - 5} lines omitted) ...\n" + tail
