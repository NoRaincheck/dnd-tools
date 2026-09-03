"""Tricube agents — tau harness + heuristic fallback.

Reuses dnd_tools.agents tau plumbing; LLM is always tool-grounded.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from dnd_campaign.tools import CampaignTools as DndCampaignTools  # pattern reuse
from dnd_tools.agents import make_tau_provider as dnd_make_provider  # reuse tau wiring

from .prompts import PLAYER_PROMPT
from .state import TricubeCampaignState, TricubeState
from .tools import TricubeCampaignTools, TricubeTools

_ = DndCampaignTools
_ = dnd_make_provider

try:
    from tau_agent.harness import AgentHarness, AgentHarnessConfig
    from tau_agent.messages import AssistantMessage, TextContent
    from tau_agent.tools import AgentTool, AgentToolResult
    from tau_ai.env import OpenAICompatibleConfig
    from tau_ai.openai_compatible import OpenAICompatibleProvider

    _TAU_AVAILABLE = True
except Exception:  # pragma: no cover
    _TAU_AVAILABLE = False  # type: ignore


def make_tau_provider(base_url: str = "http://127.0.0.1:1234/v1", api_key: str = "lm-studio"):
    if not _TAU_AVAILABLE:
        raise RuntimeError("tau-ai not installed — run `uv add tau-ai`")
    cfg = OpenAICompatibleConfig(api_key=api_key, base_url=base_url.rstrip("/"), timeout_seconds=60.0, max_retries=1)
    return OpenAICompatibleProvider(cfg)


def _tools_to_agent_tools(tools: TricubeTools | TricubeCampaignTools) -> list[AgentTool]:  # type: ignore[no-untyped-def]
    schemas = {s["function"]["name"]: s["function"] for s in tools.tool_schemas()}
    agent_tools: list[AgentTool] = []
    for name, spec in schemas.items():
        params = spec.get("parameters", {"type": "object", "properties": {}})
        description = spec.get("description", name)

        def _make_exec(_name=name):
            async def _exec(tool_call_id: str, arguments: dict[str, Any], signal=None, on_update=None):
                try:
                    result = tools.dispatch(_name, dict(arguments))
                    text = json.dumps(result, default=str)
                    return AgentToolResult(content=[TextContent(text=text)], details=result)
                except Exception as e:
                    return AgentToolResult(content=[TextContent(text=f"error: {e}")], details={"error": str(e)})

            return _exec

        agent_tools.append(
            AgentTool(name=name, label=name, description=description, parameters=params, execute_fn=_make_exec())
        )
    return agent_tools


async def _run_harness_turn(
    *,
    provider,
    model: str,
    system: str,
    tools: TricubeTools | TricubeCampaignTools,
    user_content: str,
    max_turns: int = 6,
) -> tuple[str, list[dict[str, Any]]]:
    agent_tools = _tools_to_agent_tools(tools)
    harness = AgentHarness(
        AgentHarnessConfig(provider=provider, model=model, system=system, tools=agent_tools, max_turns=max_turns)
    )
    # Tricube tools log to inner state regardless of wrapper
    state = tools.state if hasattr(tools, "state") else tools.cstate.inner  # type: ignore
    before_len = len(state.tool_trace)
    last_text = ""
    async for _event in harness.prompt(user_content):
        pass
    traces: list[dict[str, Any]] = []
    try:
        traces = state.tool_trace[before_len:]
    except Exception:
        traces = []
    for msg in reversed(harness.messages):
        if isinstance(msg, AssistantMessage):
            last_text = "".join(c.text for c in msg.content if isinstance(c, TextContent))
            if last_text.strip():
                break
    if not last_text.strip() and traces:
        last = traces[-1]
        last_text = f"used {last.get('tool')} with {last.get('args')}"
    return last_text, traces


def run_tau_player_turn_sync(
    *,
    player_name: str,
    tools: TricubeTools | TricubeCampaignTools,
    state: TricubeState | TricubeCampaignState,
    provider,
    model: str,
    max_turns: int = 6,
) -> str:
    inner: TricubeState = state.inner if isinstance(state, TricubeCampaignState) else state  # type: ignore
    ch = inner.get_character(player_name)
    if not ch:
        return f"{player_name}: error no character. <DM/>"
    system = PLAYER_PROMPT + f"\nYou are {player_name} the {ch.trait} {ch.concept}."
    alive_m = [
        f"{k} resolve {v.resolve}/{v.resolve_max} effort {inner.effort_pools.get(k, 0)} at {inner.get_pos(k)}"
        for k, v in inner.monsters.items()
        if v.alive
    ]
    ctx = (
        f"Your turn: {player_name} trait {ch.trait} concept {ch.concept} karma {ch.karma}/{ch.karma_max} resolve {ch.resolve}/{ch.resolve_max} rank {ch.rank} perks {ch.perks} quirks {ch.quirks} afflictions {len(ch.afflictions)} at {inner.get_pos(player_name)}. "
        f"Alive players: {[k for k, v in inner.players.items() if v.alive]} Monsters/effort: {alive_m} effort_pools {inner.effort_pools}\n"
        f"Map (ASCII, #=wall, upper=player, lower=monster):\n{tools.visualize_map()}\n"  # type: ignore
        f"Instructions: 1) Call check_karma_resolve and check_effort for your target. "
        f"2) If you want quirk karma, call invoke_quirk BEFORE roll_challenge. "
        f"3) Call roll_challenge with correct trait (agile/brawny/crafty). "
        f"4) If 0 successes and you have karma+perk, call spend_karma with rolls+difficulty. "
        f"Always use tools via function calling. End narration with <DM/>."
    )
    try:
        text, _traces = asyncio.run(
            _run_harness_turn(
                provider=provider, model=model, system=system, tools=tools, user_content=ctx, max_turns=max_turns
            )
        )
        if text.strip():
            return f"{player_name}: {text.strip()} <DM/>"
        if _traces:
            return f"{player_name}: (tau tools {len(_traces)}) {text.strip()} <DM/>"
        return f"{player_name}: (tau no output) <DM/>"
    except Exception as e:
        return f"{player_name}: [tau error {e}] <DM/>"


async def run_tau_harness_async(provider, model: str, system: str, tools, user_content: str, max_turns: int = 6):  # type: ignore[no-untyped-def]
    return await _run_harness_turn(
        provider=provider, model=model, system=system, tools=tools, user_content=user_content, max_turns=max_turns
    )


# ---------------------------------------------------------------------------
# Compat wrapper like dnd_tools LLMClient
# ---------------------------------------------------------------------------


class TauLLM:
    def __init__(
        self, base_url: str = "http://127.0.0.1:1234/v1", model: str = "qwen3.6-35b-a3b-mtp", api_key: str = "lm-studio"
    ):
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self._provider = make_tau_provider(base_url=base_url, api_key=api_key)

    @property
    def provider(self):
        return self._provider


LLMClient = TauLLM


# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------


def heuristic_player_turn(char_name: str, tools: TricubeTools | TricubeCampaignTools, state: Any) -> str:  # type: ignore[no-untyped-def]
    inner: TricubeState = state.inner if hasattr(state, "inner") else state
    ch = inner.get_character(char_name)
    if not ch:
        return f"{char_name}: error. <DM/>"
    # choose nearest monster with effort remaining
    candidates = [(n, c) for n, c in inner.monsters.items() if c.alive and inner.effort_pools.get(n, 0) > 0]
    if not candidates:
        # also check generic effort pools not tied to monster names? e.g. grouped horde
        pooled = [k for k, v in inner.effort_pools.items() if v > 0 and k not in inner.monsters]
        if pooled:
            target_effort = pooled[0]
            # no specific monster, use generic challenge — pick trait from character's forte
            trait = ch.trait
            # optionally invoke quirk if low karma
            if ch.karma < 2 and ch.quirks and not ch._pending_quirk:
                tools.invoke_quirk(char_name, ch.quirks[0])  # type: ignore
            r = tools.roll_challenge(char_name, trait, difficulty=5, effort_target=target_effort)  # type: ignore
            if not r.get("success") and ch.karma > 0 and ch.perks:
                # retro spend
                try:
                    nr = tools.spend_karma(
                        char_name, r.get("rolls"), r.get("effective_difficulty") or r.get("difficulty")
                    )  # type: ignore
                    # recount effort? spend_karma returns new success; we should apply pool delta manually
                    # For heuristic we just note; the earlier pool already deducted old successes — adjust by new successes diff
                    new_success = nr.get("successes", 0) if isinstance(nr, dict) else 0
                    old_success = r.get("successes", 0)
                    diff = new_success - old_success
                    if diff > 0 and target_effort in inner.effort_pools:
                        # spend already deducted? Actually roll_challenge deducted old; need to deduct diff
                        inner.effort_pools[target_effort] = max(0, inner.effort_pools[target_effort] - diff)
                    r = {**r, **nr}
                except Exception:
                    pass
            # quirk recovery now auto-handled in roll_challenge
            # defense-like? For attack, if failed, lose resolve? Actually attack failure costs may be resolve; we treat defense_roll separately. For challenges, failure not auto resolve here — leave to GM. But for combat we treat as attack.
            if r.get("success"):
                leftover = r.get("effort_removed", 0)
                return f"{char_name} tackles challenge {target_effort} ({trait}) roll {r.get('rolls')} vs {r.get('effective_difficulty')} -> {'exceptional ' if r.get('exceptional') else ''}success, -{leftover} effort (remaining {inner.effort_pools.get(target_effort, 0)}). <DM/>"
            else:
                # on failure, pay resolve? For heuristic, simulate failure cost as -1 via defense
                inner.update_resolve(char_name, -1)
                return f"{char_name} attempts {target_effort} ({trait}) roll {r.get('rolls')} vs {r.get('effective_difficulty')} -> fail, loses 1 resolve -> {ch.resolve}/{ch.resolve_max}. <DM/>"
        return f"{char_name}: no effort remaining. <DM/>"
    # pick nearest
    best = None
    best_d = 1e9
    for n, _ in candidates:
        try:
            d = inner.distance_feet(char_name, n)
            if d < best_d:
                best_d = d
                best = n
        except Exception:
            pass
    target = best or candidates[0][0]
    # decide trait: vs traits? Use attacker's forte vs target's weak? Simple: use own trait's combat style mapped trait
    # For now use character's own trait as attack trait (agile->ranged etc)
    trait = ch.trait
    # attempt to close if not LoS
    los = tools.check_valid_attack_line(char_name, target)  # type: ignore
    if not los:
        cur = inner.get_pos(char_name)
        tgt = inner.get_pos(target)
        if cur and tgt:
            nx = cur[0] + (1 if tgt[0] > cur[0] else -1 if tgt[0] < cur[0] else 0)
            ny = cur[1] + (1 if tgt[1] > cur[1] else -1 if tgt[1] < cur[1] else 0)
            try:
                tools.move_player(char_name, nx, ny)  # type: ignore
            except Exception:
                pass
    if ch.karma < 1 and ch.quirks and not ch._pending_quirk:
        try:
            tools.invoke_quirk(char_name, ch.quirks[0])  # type: ignore
        except Exception:
            pass
    r = tools.roll_challenge(char_name, trait, difficulty=5, effort_target=target)  # type: ignore
    # retro karma if failed and we have perk+karma
    if not r.get("success") and ch.karma > 0 and ch.perks:
        try:
            nr = tools.spend_karma(char_name, r.get("rolls"), r.get("effective_difficulty") or r.get("difficulty"))  # type: ignore
            # adjust pool for new successes
            if isinstance(nr, dict) and nr.get("success"):
                diff = nr.get("successes", 0) - r.get("successes", 0)
                if diff > 0 and target in inner.effort_pools:
                    inner.effort_pools[target] = max(0, inner.effort_pools[target] - diff)
                r = {**r, **nr}
        except Exception:
            pass
    # quirk recovery auto-handled in roll_challenge
    # resolve failure cost
    if r.get("critical_failure"):
        inner.update_resolve(char_name, -2)
        # also if fails vs foe, foe not defeated but attacker takes extra
        return f"{char_name} attacks {target} ({trait}) {r.get('rolls')} vs {r.get('effective_difficulty')} -> critical fail! loses 2 resolve -> {ch.resolve}/{ch.resolve_max}. <DM/>"
    if not r.get("success"):
        inner.update_resolve(char_name, -1)
        return f"{char_name} attacks {target} ({trait}) {r.get('rolls')} vs {r.get('effective_difficulty')} -> fail, loses 1 resolve -> {ch.resolve}/{ch.resolve_max}. <DM/>"
    remaining = inner.effort_pools.get(target, 0)
    if r.get("exceptional"):
        return f"{char_name} attacks {target} ({trait}) {r.get('rolls')} vs {r.get('effective_difficulty')} -> exceptional success! -{r.get('effort_removed')} effort (remaining {remaining}). <DM/>"
    return f"{char_name} attacks {target} ({trait}) {r.get('rolls')} vs {r.get('effective_difficulty')} -> success -{r.get('effort_removed')} effort (remaining {remaining}). <DM/>"
