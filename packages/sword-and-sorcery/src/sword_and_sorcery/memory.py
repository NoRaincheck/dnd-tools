"""Memory helpers for S&S — bounded context for LLM."""

from __future__ import annotations

from typing import Any

from .state import SnSCampaignState


def summarize_state(cstate: SnSCampaignState) -> dict[str, Any]:
    inner = cstate.inner
    players = {
        n: {
            "ancestry": c.ancestry,
            "background": c.background,
            "sns": c.sns,
            "hp": f"{c.hp}/{c.hp_max}",
            "sp": f"{c.sp}/{c.sp_max}",
            "wd": c.wd,
            "en": c.en,
            "pos": inner.players_pos.get(n),
            "alive": c.alive,
            "unconscious": c.unconscious,
            "spells": c.spells_known[:3],
        }
        for n, c in inner.players.items()
    }
    monsters = {
        n: {
            "threat": m.threat,
            "hp": f"{m.hp}/{m.hp_max}",
            "dmg": m.dmg,
            "pos": inner.monster_pos.get(n),
            "alive": m.alive,
        }
        for n, m in inner.monsters.items()
    }
    return {
        "round": inner.round,
        "turn": inner.current_actor(),
        "players": players,
        "monsters": monsters,
        "adventure": inner.adventure,
        "death_log": inner.death_log[-5:],
        "meta": dict(cstate.campaign_meta),
    }


def compact_transcript(cstate: SnSCampaignState, keep_last: int = 40) -> str:
    t = cstate.inner.transcript
    if len(t) <= keep_last + 10:
        return "\n".join(t)
    head = "\n".join(t[:5])
    tail = "\n".join(t[-keep_last:])
    return head + f"\n... ({len(t) - keep_last - 5} lines omitted) ...\n" + tail
