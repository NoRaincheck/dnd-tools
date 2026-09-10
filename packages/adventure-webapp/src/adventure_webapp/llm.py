"""Narrator — LLM when available, heuristic otherwise."""

from __future__ import annotations

from typing import Any

_TEMPLATE_FLAVOR: dict[str, dict[str, str]] = {
    "veiled-archive": {
        "critical": " The ward flares, almost approving.",
        "partial": " You gain ground, but pay for it.",
        "failure": " The archive shudders. A new obstacle appears.",
        "completed": " The archive's ward chimes — the prize is yours.",
    },
    "goblin-ambush": {
        "critical": " Steel sings — the line holds.",
        "partial": " You gain ground, but the press is heavy.",
        "failure": " War-horns answer from the treeline. A new threat emerges.",
        "completed": " The pass is held — the road is yours.",
    },
    "starlit-heist": {
        "critical": " Moonlight catches the sigil perfectly.",
        "partial": " You slip, but a ward flickers.",
        "failure": " A bell jingles somewhere above. Guards stir.",
        "completed": " The sigil is yours — you vanish into the night.",
    },
}

_GENERIC_FLAVOR: dict[str, str] = {
    "critical": " Fortune favours the bold.",
    "partial": " You gain ground, but pay for it.",
    "failure": " It goes awry. A new obstacle appears.",
    "completed": " The objective is secured.",
}


def _flavor(template_id: str, key: str) -> str:
    tpl = _TEMPLATE_FLAVOR.get(template_id)
    if tpl and key in tpl:
        return tpl[key]
    return _GENERIC_FLAVOR.get(key, "")


def _heuristic_narration(
    actor: str,
    beat_title: str,
    pick_text: str,
    outcome: str,
    position: str,
    effect: str,
    consequence: list[str],
    ticks: int,
    completed: bool,
    template_id: str = "veiled-archive",
) -> str:
    verb = {
        "critical": "with startling grace",
        "success": "cleanly",
        "partial": "at a cost",
        "failure": "and it goes wrong",
    }.get(outcome, outcome)
    cons = ""
    if consequence:
        cons = " — " + "; ".join(consequence[:2])
    extra = ""
    if outcome == "critical":
        extra = _flavor(template_id, "critical")
    elif outcome == "partial":
        extra = _flavor(template_id, "partial")
    elif outcome == "failure":
        extra = _flavor(template_id, "failure")
    if completed:
        extra += _flavor(template_id, "completed")
    return (
        f"{actor} chose: “{pick_text}” — {verb} ({position}/{effect}, ticks {ticks}){cons}.{extra} "
        f"[{beat_title.strip()}]"
    )


def _heuristic_choices_for_beat(template_id: str, beat_idx: int) -> dict[str, Any]:
    from .scenes import BEAT_CHOICES

    presets = BEAT_CHOICES.get(template_id) or BEAT_CHOICES.get("veiled-archive", [])
    if 0 <= beat_idx < len(presets):
        return dict(presets[beat_idx])
    return {
        "obvious": "Press on carefully by the obvious route",
        "option": "Try a lateral approach around the obstacle",
        "odd": "Do something impulsive and unexpected",
        "situation": f"Beat {beat_idx + 1} — choose your path",
        "position": "risky",
        "effect": "standard",
    }


def narrate_outcome(
    actor: str,
    beat_title: str,
    pick_text: str,
    action_roll: dict[str, Any],
    clock_completed: bool,
    template_id: str = "veiled-archive",
) -> str:
    outcome = str(action_roll.get("outcome", "partial"))
    position = str(action_roll.get("position", "risky"))
    effect = str(action_roll.get("effect", "standard"))
    cons = list(action_roll.get("consequence", []) or [])
    ticks = int(action_roll.get("ticks", 0) or 0)
    # Try LLM if tau is configured — best-effort, never block.
    llm_text = _try_llm_narration(actor, pick_text, outcome, position, consequence=cons)
    if llm_text:
        return llm_text + (f" [ticks {ticks}]" if ticks else "")
    return _heuristic_narration(
        actor, beat_title, pick_text, outcome, position, effect, cons, ticks, clock_completed, template_id
    )


def _try_llm_narration(actor: str, pick_text: str, outcome: str, position: str, consequence: list[str]) -> str | None:
    try:
        import os

        base = os.environ.get("ADVENTURE_LLM_BASE", "")
        if not base:
            return None
        # Lazy import tau — not a hard dep unless env says so.
        from dnd_tools.agents import LLMClient  # type: ignore[import-untyped]

        prompt = (
            f"You narrate 1-2 sentences for {actor} who attempted “{pick_text}” "
            f"and got outcome={outcome} position={position} consequence={'; '.join(consequence)[:160]}. "
            "Be concise, cross-link action to fiction, do not soften consequence."
        )
        client = LLMClient(model=os.environ.get("ADVENTURE_LLM_MODEL", "qwen3-6b"), base_url=base)  # type: ignore[call-arg]
        # best-effort single turn — timeout quickly
        txt = getattr(client, "complete", lambda *a, **kw: None)(prompt, max_tokens=120)  # type: ignore[operator]
        if isinstance(txt, str) and txt.strip():
            return txt.strip()[:420]
    except Exception:
        return None
    return None


def generate_beat_choices(llm_available: bool, template_id: str, beat_idx: int, actor: str) -> dict[str, Any]:
    # Future: ask LLM to author fresh obvious/option/odd; for now heuristic is deterministic & testable.
    _ = llm_available, actor
    return _heuristic_choices_for_beat(template_id, beat_idx)
