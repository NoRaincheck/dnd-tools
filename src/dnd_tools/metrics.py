"""Six-axis evaluation — Function Usage, Parameter Fidelity, Acting Quality, Tactical Optimality, State Tracking, Function Efficiency."""

from __future__ import annotations

import re


def function_usage(trace: list[dict]) -> dict:
    """Automated checker: incorrect function (%) = tool error rate."""
    if not trace:
        return {"incorrect_function": 0.0, "total": 0}

    def _err(t):
        r = t.get("result")
        if not isinstance(r, dict):
            return False
        return (r.get("valid") is False and "out_of_range" not in r) or "error" in r

    errors = sum(1 for t in trace if _err(t))
    return {
        "incorrect_function_pct": 100 * errors / max(1, len(trace)),
        "total": len(trace),
        "errors": errors,
    }


def parameter_fidelity(trace: list[dict]) -> dict:
    """Check incorrect params: valid False due to param / out_of_range without recovery could count."""

    # Simplify: count out_of_range as param error
    def _is_bad(t):
        r = t.get("result")
        return isinstance(r, dict) and r.get("out_of_range")

    bad = sum(1 for t in trace if _is_bad(t))
    return {"incorrect_params_pct": 100 * bad / max(1, len(trace)), "bad": bad}


def acting_quality(transcript: list[str]) -> dict:
    """Paper's A score: persona density + trait coverage."""
    # Keep narrative sentences (speaker text, not DM/tool)
    narrative = [l for l in transcript if not l.startswith("FUNC") and "<End Turn" not in l and "---" not in l]
    # filter digits/dice
    filtered = [s for s in narrative if not re.search(r"\d+d\d+", s)]
    # persona if contains first-person beats or class-flavor keywords
    persona_keywords = [
        "I ",
        "valor",
        "ranger",
        "warlock",
        "druid",
        "bard",
        "paladin",
        "Get them",
        "taunt",
        "dart",
        "lunge",
        "chant",
    ]
    persona = sum(
        1 for s in filtered if any(k.lower() in s.lower() for k in persona_keywords) or s.strip().startswith("I ")
    )
    density = persona / max(1, len(filtered))
    # trait diversity: count distinct archetypes mentioned
    traits = set()
    trait_map = {
        "paladin": "valor",
        "ranger": "poise",
        "warlock": "edge",
        "druid": "calm",
        "bard": "wit",
        "monster": "taunt",
    }
    for s in narrative:
        low = s.lower()
        for k, v in trait_map.items():
            if k in low or v in low:
                traits.add(k)
    # Tmax = Nplayers+Nmonster types+1 ; approximate 5
    Tmax = 5
    diversity = min(len(traits) / Tmax, 1)
    A = 0.5 * density + 0.5 * diversity
    return {
        "A": A,
        "density": density,
        "diversity": diversity,
        "persona": persona,
        "narrative": len(narrative),
    }


def tactical_optimality(transcript: list[str]) -> dict:
    """rt: 1 if attack/spell, 0.5 if only move, else 0. O=avg over windows."""
    # segment by <End Turn/>
    windows = []
    cur = []
    for line in transcript:
        cur.append(line)
        if "<End Turn/>" in line:
            windows.append(cur)
            cur = []
    if not windows:
        windows = [transcript]
    rewards = []
    for w in windows:
        text = " ".join(w).lower()
        if "attack" in text or "spell" in text or "hit" in text or "damage" in text:
            rewards.append(1)
        elif "move" in text:
            rewards.append(0.5)
        else:
            rewards.append(0)
    O = sum(rewards) / max(1, len(rewards))
    return {"O": O, "mean_reward": O, "windows": len(windows)}


def state_tracking(trace: list[dict]) -> dict:
    """Hallucination categories heuristic: check for attacks on dead/unknown, positional."""
    # naive: error if tool result had error key
    errors = sum(1 for t in trace if "error" in str(t.get("result")))
    total = max(1, len(trace))
    return {"hallucination_rate": errors / total, "errors": errors}


def function_efficiency(trace: list[dict]) -> dict:
    """Redundant checks: unnecessary function calls ratio."""
    # Count repeated identical query without state change
    seen = {}
    unnecessary = 0
    for t in trace:
        key = (t["tool"], tuple(sorted(t.get("args", {}).items())))
        if key in seen and t["tool"].startswith("check_"):
            unnecessary += 1
        seen[key] = True
    return {
        "unnecessary_pct": 100 * unnecessary / max(1, len(trace)),
        "unnecessary": unnecessary,
    }


def evaluate_all(transcript: list[str], trace: list[dict]) -> dict:
    return {
        "function_usage": function_usage(trace),
        "parameter_fidelity": parameter_fidelity(trace),
        "acting_quality": acting_quality(transcript),
        "tactical_optimality": tactical_optimality(transcript),
        "state_tracking": state_tracking(trace),
        "function_efficiency": function_efficiency(trace),
    }
