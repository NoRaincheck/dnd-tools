"""Memory helpers — bounded context + OKF traversal for LLM agents."""

from __future__ import annotations

from typing import Any

from .state import FusedState


def summarize_fused(cstate: FusedState) -> dict[str, Any]:
    scene = cstate.current_scene()
    return {
        "seed": cstate.seed,
        "active_scene": {"id": scene.scene_id, "title": scene.title, "objective": scene.objective} if scene else None,
        "scenes_total": len(cstate.scenes),
        "effects_total": len(cstate.effects),
        "traits_registered": list(cstate.traits_registry.keys()),
        "players_alive": [k for k, c in cstate.campaign.inner.players.items() if c.alive],
        "monsters_alive": [k for k, c in cstate.campaign.inner.monsters.items() if c.alive],
        "round": cstate.campaign.inner.round,
        "turn": cstate.campaign.inner.current_actor(),
        "bundle_root": str(cstate.bundle_root) if cstate.bundle_root else None,
    }


def compact_fused_transcript(cstate: FusedState, keep_last: int = 40) -> str:
    t = cstate.campaign.inner.transcript
    if len(t) <= keep_last + 10:
        return "\n".join(t)
    head = "\n".join(t[:5])
    tail = "\n".join(t[-keep_last:])
    return head + f"\n... ({len(t) - keep_last - 5} lines omitted) ...\n" + tail


def build_agent_context(cstate: FusedState, actor: str, last_n: int = 20) -> str:
    """Render a prompt-ready string combining traits + recent effects + scene."""
    ctx = cstate.context_for_actor(actor, last_n=last_n)
    lines = [
        f"Actor: {ctx['actor']}",
        f"Traits: {ctx['traits']}",
        f"Scene: {ctx['active_scene']} — {ctx['scene_objective']}",
        "Recent effects:",
    ]
    for e in ctx["recent_effects"]:
        lines.append(f"  - r{e['round']} {e['actor']} {e['kind']}: {e['summary']}")
    if ctx["traits_detail"]:
        td = ctx["traits_detail"]
        lines.append(f"Trait detail: {td}")
    return "\n".join(lines)
