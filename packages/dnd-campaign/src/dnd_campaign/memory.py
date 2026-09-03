"""Memory helpers — keep LLM context bounded over long horizons."""

from __future__ import annotations

from typing import Any

from .state import CampaignState


def summarize_state(cstate: CampaignState) -> dict[str, Any]:
    inner = cstate.inner
    players = {
        n: {
            "hp": c.hp,
            "max_hp": c.max_hp,
            "ac": c.ac,
            "pos": inner.players_pos.get(n),
            "alive": c.alive,
            "slots": dict(c.spell_slots),
            "buffs": [b.name for b in c.buffs],
        }
        for n, c in inner.players.items()
    }
    monsters = {
        n: {"hp": c.hp, "max_hp": c.max_hp, "pos": inner.monster_pos.get(n), "alive": c.alive}
        for n, c in inner.monsters.items()
    }
    return {
        "round": inner.round,
        "turn": inner.current_actor(),
        "players": players,
        "monsters": monsters,
        "death_log": inner.death_log[-5:],
        "meta": dict(cstate.campaign_meta),
    }


def compact_transcript(cstate: CampaignState, keep_last: int = 40) -> str:
    """Return compact string for LLM prompt (init + tail)."""
    t = cstate.inner.transcript
    if len(t) <= keep_last + 10:
        return "\n".join(t)
    head = "\n".join(t[:5])
    tail = "\n".join(t[-keep_last:])
    return head + f"\n... ({len(t) - keep_last - 5} lines omitted) ...\n" + tail
