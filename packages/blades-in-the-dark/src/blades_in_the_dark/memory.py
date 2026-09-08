"""Memory helpers — summarize state and compact transcript for bounded LLM context."""

from __future__ import annotations

from typing import Any

from .state import BladesCampaignState


def summarize_state(cstate: BladesCampaignState) -> dict[str, Any]:
    inner = cstate.inner
    players: dict[str, Any] = {}
    for name, ch in inner.players.items():
        players[name] = {
            "playbook": ch.playbook,
            "actions": {k: v for k, v in ch.actions.items() if v > 0},
            "stress": f"{ch.stress}/{ch.stress_max}",
            "trauma": list(ch.trauma),
            "harm": [{"level": h.level, "name": h.name} for h in ch.harm],
            "vice": ch.vice,
            "pos": list(ch.pos),
            "alive": ch.alive,
            "retired": ch.retired,
        }
    clocks = {
        k: {"ticks": v.ticks, "segments": v.segments, "completed": v.completed, "kind": v.kind}
        for k, v in inner.clocks.items()
    }
    return {
        "seed": inner.seed,
        "round": inner.round,
        "turn": inner.current_actor(),
        "players": players,
        "clocks": clocks,
        "crew": {
            "name": inner.crew.name,
            "type": inner.crew.crew_type,
            "tier": inner.crew.tier,
            "heat": inner.crew.heat,
            "wanted": inner.crew.wanted_level,
            "coin": inner.crew.coin,
        },
        "trauma_log": inner.trauma_log[-5:],
        "harm_log": inner.harm_log[-5:],
        "meta": dict(cstate.campaign_meta),
    }


def compact_transcript(transcript: list[str], keep_first: int = 10, keep_last: int = 120) -> list[str]:
    if len(transcript) <= keep_first + keep_last:
        return list(transcript)
    return (
        transcript[:keep_first]
        + [f"... [{len(transcript) - keep_first - keep_last} lines omitted] ..."]
        + transcript[-keep_last:]
    )
