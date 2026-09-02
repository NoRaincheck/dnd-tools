"""Agent abstraction — Tau-native (python library) with LMStudio/any OpenAI-compatible endpoint.

Uses `tau_ai` (provider layer) + `tau_agent` (harness + loop) exclusively — no subprocesses, no Pi CLI.
Falls back to heuristic when no LLM is configured or on provider errors.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .prompts import GM_PROMPT, PLAYER_PROMPT
from .state import GameState
from .tools import Tools

# Tau imports are optional at import-time; we fail gracefully to heuristic.
try:
    from tau_agent.harness import AgentHarness, AgentHarnessConfig
    from tau_agent.messages import (
        AssistantMessage,
        TextContent,
    )
    from tau_agent.tools import AgentTool, AgentToolResult
    from tau_ai.env import OpenAICompatibleConfig
    from tau_ai.openai_compatible import OpenAICompatibleProvider

    _TAU_AVAILABLE = True
except Exception:  # pragma: no cover
    _TAU_AVAILABLE = False


# ---------------------------------------------------------------------------
# Provider factory (pure python, no subprocess)
# ---------------------------------------------------------------------------


def make_tau_provider(
    base_url: str = "http://127.0.0.1:1234/v1", api_key: str = "lm-studio"
):
    """Create an OpenAI-compatible Tau provider for LMStudio or any compatible endpoint."""
    if not _TAU_AVAILABLE:
        raise RuntimeError("tau-ai not installed — run `uv add tau-ai`")
    cfg = OpenAICompatibleConfig(
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        timeout_seconds=60.0,
        max_retries=1,
    )
    return OpenAICompatibleProvider(cfg)


def _tools_to_agent_tools(tools: Tools) -> list[AgentTool]:
    """Convert the validated `Tools` surface into Tau AgentTools.

    Each AgentTool is an async executor that dispatches to the authoritative Tools instance
    and returns an AgentToolResult. Schema is taken from Tools.tool_schemas().
    """
    schemas = {s["function"]["name"]: s["function"] for s in tools.tool_schemas()}
    agent_tools: list[AgentTool] = []

    for name, spec in schemas.items():
        params = spec.get("parameters", {"type": "object", "properties": {}})
        description = spec.get("description", name)

        # capture name/spec in closure
        def _make_exec(_name=name):
            async def _exec(
                tool_call_id: str,
                arguments: dict[str, Any],
                signal=None,
                on_update=None,
            ):
                try:
                    # arguments already validated/coerced by provider; pass straight through
                    result = tools.dispatch(_name, dict(arguments))
                    # Tau expects content list; details holds structured result for harness
                    text = json.dumps(result, default=str)
                    return AgentToolResult(
                        content=[TextContent(text=text)], details=result
                    )
                except (
                    Exception
                ) as e:  # tool is isolation boundary — return error result not raise
                    return AgentToolResult(
                        content=[TextContent(text=f"error: {e}")],
                        details={"error": str(e)},
                    )

            return _exec

        agent_tools.append(
            AgentTool(
                name=name,
                label=name,
                description=description,
                parameters=params,
                execute_fn=_make_exec(),
            )
        )
    return agent_tools


# ---------------------------------------------------------------------------
# Tau harness helpers (async, self-contained)
# ---------------------------------------------------------------------------


async def _run_harness_turn(
    *,
    provider,
    model: str,
    system: str,
    tools: Tools,
    user_content: str,
    max_turns: int = 6,
) -> tuple[str, list[dict[str, Any]]]:
    """Run one player/DM turn through Tau. Returns (assistant_text, traces)."""
    agent_tools = _tools_to_agent_tools(tools)
    harness = AgentHarness(
        AgentHarnessConfig(
            provider=provider,
            model=model,
            system=system,
            tools=agent_tools,
            max_turns=max_turns,
        )
    )
    before_len = len(tools.state.tool_trace) if hasattr(tools, "state") else 0
    last_text = ""

    async for _event in harness.prompt(user_content):
        pass

    # Traces = diff of tool_trace (authoritative)
    traces: list[dict[str, Any]] = []
    try:
        traces = tools.state.tool_trace[before_len:]
    except Exception:
        traces = []

    # Extract last assistant message text — prefer last non-empty text, else synthesize from tool use
    for msg in reversed(harness.messages):
        if isinstance(msg, AssistantMessage):
            # concatenate text contents
            last_text = "".join(
                c.text for c in msg.content if isinstance(c, TextContent)
            )
            if last_text.strip():
                break
    if not last_text.strip() and traces:
        # model did tools but no narrative — synthesize minimal narration from traces for transcript
        last = traces[-1]
        last_text = f"used {last.get('tool')} with {last.get('args')}"
    return last_text, traces


def run_tau_player_turn_sync(
    *,
    player_name: str,
    player_class: str,
    tools: Tools,
    state: GameState,
    provider,
    model: str,
    max_turns: int = 6,
) -> str:
    """Synchronous wrapper for one tau-driven player turn. Returns transcript line."""
    ch = state.get_character(player_name)
    if not ch:
        return f"{player_name}: error no character. <DM/>"

    system = PLAYER_PROMPT + f"\nYou are {player_name} the {player_class}."
    # Provide turn context — be explicit to force tool calling (tau harness needs directive)
    alive_monsters = [
        f"{k} HP {v.hp}/{v.max_hp} at {state.get_pos(k)}"
        for k, v in state.monsters.items()
        if v.alive
    ]
    ctx = (
        f"Your turn: {player_name} ({player_class}) HP {ch.hp}/{ch.max_hp} at {state.get_pos(player_name)} speed {ch.speed_remaining} AC {ch.ac} weapon {ch.equipped_mainhand}. "
        f"Alive players: {[k for k, v in state.players.items() if v.alive]} "
        f"Monsters: {alive_monsters}\n"
        f"Map (ASCII, #=wall, upper=player, lower=monster):\n{tools.visualize_map()}\n"
        f"Instructions: 1) Call check_valid_attack_line to see if you can hit a monster. "
        f"2) If false, call move_player towards the nearest monster. "
        f"3) If true, call roll_attack (use weapon {ch.equipped_mainhand}). "
        f"Always use tools via function calling. End narration with <DM/>."
    )
    try:
        text, _traces = asyncio.run(
            _run_harness_turn(
                provider=provider,
                model=model,
                system=system,
                tools=tools,
                user_content=ctx,
                max_turns=max_turns,
            )
        )
        # `_traces` already logged to state.tool_trace via Tools.dispatch; we just return text
        if text.strip():
            return f"{player_name}: {text.strip()} <DM/>"
        if _traces:
            return f"{player_name}: (tau tools {len(_traces)}) {text.strip()} <DM/>"
        return f"{player_name}: (tau no output) <DM/>"
    except Exception as e:
        # Fallback — keep simulation alive
        return f"{player_name}: [tau error {e}] <DM/>"


async def run_tau_harness_async(
    provider,
    model: str,
    system: str,
    tools: Tools,
    user_content: str,
    max_turns: int = 6,
) -> tuple[str, list[dict[str, Any]]]:
    """Public async helper — useful for notebooks or custom loops."""
    return await _run_harness_turn(
        provider=provider,
        model=model,
        system=system,
        tools=tools,
        user_content=user_content,
        max_turns=max_turns,
    )


# ---------------------------------------------------------------------------
# Compatibility shims for old code paths (simulation.py used LLMClient)
# ---------------------------------------------------------------------------


class TauLLM:
    """Thin compat wrapper — holds provider + model for simulation.py.

    simulation.py can pass this as `llm` and the turn handler will use Tau.
    This keeps the constructor signature stable without subprocesses.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:1234/v1",
        model: str = "qwen3.6-35b-a3b-mtp",
        api_key: str = "lm-studio",
    ):
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self._provider = make_tau_provider(base_url=base_url, api_key=api_key)

    @property
    def provider(self):
        return self._provider


# Legacy names expected by older simulation.py — map to TauLLM
LLMClient = TauLLM


class BaseAgent:  # minimal shim for any external import
    def __init__(self, *a, **kw):
        raise RuntimeError(
            "BaseAgent is deprecated — use tau harness via run_tau_player_turn_sync"
        )


class DMAgent:  # shim
    def __init__(self, llm: TauLLM):
        self.llm = llm
        self.system = GM_PROMPT


class PlayerAgent:  # shim
    def __init__(self, name: str, llm: TauLLM, char_class: str = ""):
        self.name = name
        self.llm = llm
        self.system = PLAYER_PROMPT + f"\nYou are {name} the {char_class}."


def execute_tool_loop(
    agent, tools: Tools, max_iters: int = 6
) -> list[dict]:  # pragma: no cover
    raise RuntimeError("execute_tool_loop is deprecated — use tau harness")


# ------------------------------------------------------------------
# Heuristic fallback for when LLM unavailable: rule-based player/monster
# ------------------------------------------------------------------
def heuristic_player_turn(char_name: str, tools: Tools, state: GameState) -> str:
    """Simple greedy policy for offline demo without LLM."""
    enemies = [(n, c) for n, c in state.monsters.items() if c.alive]
    if not enemies:
        return f"{char_name}: no enemies remain. <DM/>"
    best = None
    best_dist = 1e9
    for n, _ in enemies:
        try:
            d = state.distance_feet(char_name, n)
            if d < best_dist:
                best_dist = d
                best = n
        except:
            pass
    target = best or enemies[0][0]
    los = tools.check_valid_attack_line(char_name, target)
    if not los:
        cur = state.get_pos(char_name)
        tgt = state.get_pos(target)
        if cur and tgt:
            nx = cur[0] + (1 if tgt[0] > cur[0] else -1 if tgt[0] < cur[0] else 0)
            ny = cur[1] + (1 if tgt[1] > cur[1] else -1 if tgt[1] < cur[1] else 0)
            tools.move_player(char_name, nx, ny)
            los = tools.check_valid_attack_line(char_name, target)
    ch = state.get_character(char_name)
    if not ch:
        return f"{char_name}: error. <DM/>"
    _def = state.get_character(target)
    ac = _def.ac if _def is not None else 10
    dist = state.distance_feet(char_name, target) if best else 100
    weap = ch.equipped_mainhand
    from .models import MELEE_SET

    if weap.lower() in MELEE_SET and dist > 5:
        tools.dash(char_name)
        cur = state.get_pos(char_name)
        tgt = state.get_pos(target)
        if cur and tgt:
            nx = cur[0] + (2 if tgt[0] > cur[0] else -1)
            ny = cur[1] + (2 if tgt[1] > cur[1] else -1)
            try:
                tools.move_player(char_name, nx, ny)
            except:
                pass
        dist = state.distance_feet(char_name, target)
    if dist <= 90:
        atk = tools.roll_attack(
            char_name,
            target,
            roll_type="normal",
            ac=ac,
            weapon_name=weap,
            action_cost=1,
        )
        if atk.get("success"):
            dmg_expr = "1d8"
            try:
                from .models import ALL_WEAPONS

                w = ALL_WEAPONS.get(weap.lower())
                if w:
                    dmg_expr = w.damage_dice
            except:
                pass
            dmg = tools.roll_dmg(
                char_name,
                target,
                dmg_expr,
                "slashing" if "slashing" in dmg_expr else "piercing",
                is_critical=atk.get("critical", False),
            )
            true = dmg["damage"]
            resists = tools.check_resist(target)
            for e in resists:
                if e["damage_type"] == dmg["damage_type"] and e["kind"] == "resist":
                    true = true // 2
                if e["kind"] == "immune":
                    true = 0
            tools.update_hp(target, -true)
            return f"{char_name} attacks {target} with {weap} — {'HIT' if atk['success'] else 'MISS'} for {true} dmg. <DM/>"
        else:
            if atk.get("out_of_range"):
                return f"{char_name} cannot reach {target} (out of range). <DM/>"
            return f"{char_name} attacks {target} with {weap} — MISS. <DM/>"
    return f"{char_name} moves and waits. <DM/>"
