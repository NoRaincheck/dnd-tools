"""Agent abstraction — Tau-native (LMStudio) with heuristic fallback.

Mirrors dnd_tools.agents but for Blades position/effect + stress.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .prompts import GM_PROMPT, PLAYER_PROMPT
from .state import BladesCampaignState, BladesState

try:
    from tau_agent.harness import AgentHarness, AgentHarnessConfig
    from tau_agent.messages import AssistantMessage, TextContent
    from tau_agent.tools import AgentTool, AgentToolResult
    from tau_ai.env import OpenAICompatibleConfig
    from tau_ai.openai_compatible import OpenAICompatibleProvider

    _TAU_AVAILABLE = True
except Exception:  # pragma: no cover
    _TAU_AVAILABLE = False


def make_tau_provider(base_url: str = "http://127.0.0.1:1234/v1", api_key: str = "lm-studio"):
    if not _TAU_AVAILABLE:
        raise RuntimeError("tau-ai not installed — run `uv add tau-ai`")
    cfg = OpenAICompatibleConfig(api_key=api_key, base_url=base_url.rstrip("/"), timeout_seconds=60.0, max_retries=1)
    return OpenAICompatibleProvider(cfg)


def _tools_to_agent_tools(tools: Any) -> list[AgentTool]:
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
                except Exception as e:  # isolation boundary
                    return AgentToolResult(content=[TextContent(text=f"error: {e}")], details={"error": str(e)})

            return _exec

        agent_tools.append(
            AgentTool(name=name, label=name, description=description, parameters=params, execute_fn=_make_exec())
        )
    return agent_tools


async def _run_harness_turn(*, provider, model: str, system: str, tools: Any, user_content: str, max_turns: int = 6):
    agent_tools = _tools_to_agent_tools(tools)
    harness = AgentHarness(
        AgentHarnessConfig(provider=provider, model=model, system=system, tools=agent_tools, max_turns=max_turns)
    )
    before_len = len(tools.state.tool_trace) if hasattr(tools, "state") else 0  # type: ignore
    # CampaignTools has .cstate.inner.tool_trace ; BladesCampaignTools path
    if hasattr(tools, "cstate"):
        before_len = len(tools.cstate.inner.tool_trace)  # type: ignore
    last_text = ""
    async for _event in harness.prompt(user_content):
        pass
    traces: list[dict[str, Any]] = []
    try:
        if hasattr(tools, "cstate"):
            traces = tools.cstate.inner.tool_trace[before_len:]  # type: ignore
        else:
            traces = tools.state.tool_trace[before_len:]  # type: ignore
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
    tools: Any,
    state: BladesState | BladesCampaignState,
    provider,
    model: str,
    max_turns: int = 6,
) -> str:
    inner: BladesState
    if isinstance(state, BladesCampaignState):
        inner = state.inner
    else:
        inner = state
    ch = inner.get_character(player_name)
    playbook = ch.playbook if ch else "Cutter"
    system = PLAYER_PROMPT + f"\nYou are {player_name} the {playbook}."
    # build LLM context strictly via tools - include clocks
    clocks_ascii = ""
    try:
        clocks_ascii = tools.visualize_clocks().get("ascii", "")  # type: ignore
    except Exception:
        pass
    alive = [k for k, v in inner.players.items() if v.alive and not v.retired]
    ctx = (
        f"Your turn: {player_name} ({playbook}) stress {ch.stress if ch else '?'} / harm {len(ch.harm) if ch else 0} . "
        f"Alive scoundrels: {alive} "
        f"Clocks:\n{clocks_ascii}\n"
        f"Instructions: 1) Call set_position_and_effect(character='{player_name}', action='<one of 12>', position='controlled|risky|desperate', effect='limited|standard|great') to negotiate. "
        f"2) Optionally push_yourself/assist/devil_bargain for bonus dice. "
        f"3) Call action_roll(character='{player_name}', clock='Score Clock') — it will map 6/4-5/1-3 to consequence via position. "
        f"4) If consequence appears, call resistance_roll or use_armor. End narration with <DM/>."
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


async def run_tau_harness_async(provider, model: str, system: str, tools: Any, user_content: str, max_turns: int = 6):
    return await _run_harness_turn(
        provider=provider, model=model, system=system, tools=tools, user_content=user_content, max_turns=max_turns
    )


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


class BaseAgent:
    def __init__(self, *a, **kw):
        raise RuntimeError("BaseAgent is deprecated — use tau harness via run_tau_player_turn_sync")


class DMAgent:
    def __init__(self, llm: TauLLM):
        self.llm = llm
        self.system = GM_PROMPT


class PlayerAgent:
    def __init__(self, name: str, llm: TauLLM, playbook: str = ""):
        self.name = name
        self.llm = llm
        self.system = PLAYER_PROMPT + f"\nYou are {name} the {playbook}."


def execute_tool_loop(agent, tools, max_iters: int = 6):  # pragma: no cover
    raise RuntimeError("execute_tool_loop is deprecated — use tau harness")


# ------------------------------------------------------------------
# Heuristic fallback — greets greedy score ticks with rigid gate
# ------------------------------------------------------------------
def heuristic_player_turn(char_name: str, tools: Any, state: Any) -> str:
    """Greedy policy: negotiate risky/standard on best action, roll, resist if stressed."""
    # unwrap campaign state
    inner: BladesState
    if isinstance(state, BladesCampaignState):
        inner = state.inner
    else:
        inner = state
    ch = inner.get_character(char_name)
    if not ch:
        return f"{char_name}: error no character. <DM/>"
    # pick best action (highest rating), else default skirmish
    best_action = max(ch.actions.items(), key=lambda x: x[1])[0] if ch.actions else "Skirmish"
    if ch.actions.get(best_action, 0) == 0:
        best_action = "Prowl"
    # choose a clock to tick: first incomplete else create "Score Clock" 6
    target_clock = None
    for name, clk in inner.clocks.items():
        if not clk.completed:
            target_clock = name
            break
    if not target_clock:
        # create score clock
        tools.set_clock("Score Clock", 6, "obstacle")
        target_clock = "Score Clock"
    # rigid gate: must set position/effect
    pos = "risky"  # heuristic default
    eff = "standard"
    # maybe occasionally push desperate for flavor if stress low
    if ch.stress <= 2 and len(inner.clocks) > 1:
        pos = "desperate"
        eff = "great"
        # push for effect to simulate AI Fix demonstration occasionally
        try:
            tools.push_yourself(char_name, "effect")
            eff = "great"  # already
        except Exception:
            pass
    try:
        tools.set_position_and_effect(char_name, best_action, pos, eff)
    except Exception as e:
        return f"{char_name}: set_position gate failed {e} <DM/>"
    # occasional assist from ally if stress low ally exists
    # we skip assist in heuristic to keep deterministic
    roll_res = tools.action_roll(char_name, best_action, pos, eff, clock=target_clock)
    if not roll_res.get("valid"):
        return f"{char_name}: action_roll failed {roll_res.get('reason')} <DM/>"
    outcome = roll_res.get("outcome")
    consequence = roll_res.get("consequence") or []
    ticks = roll_res.get("ticks", 0)
    # on partial/failure with consequence, try to resist if stress not max
    if consequence and ch.stress < 7:
        # pick attribute: map action to attr; pick that attr
        from .models import ACTION_TO_ATTR

        attr = ACTION_TO_ATTR.get(best_action, "Prowess")
        try:
            rr = tools.resistance_roll(char_name, attr)
            return f"{char_name} ({best_action}) {pos}/{eff} → {outcome} {roll_res.get('rolls')} (highest {roll_res.get('highest')}) ticks {ticks} on {target_clock} but consequence {consequence} — resists with {attr} roll {rr.get('rolls')} → {rr.get('stress_cost')} stress (now {rr.get('stress_after')}). <DM/>"
        except Exception:
            pass
    if outcome in ("critical", "success"):
        return f"{char_name} ({best_action}) {pos}/{eff} → {outcome} {roll_res.get('rolls')} (highest {roll_res.get('highest')}) ticks {ticks} on {target_clock}. <DM/>"
    elif outcome == "partial":
        return f"{char_name} ({best_action}) {pos}/{eff} → partial {roll_res.get('rolls')} but consequence {consequence} ticks {ticks} on {target_clock}. <DM/>"
    else:
        return f"{char_name} ({best_action}) {pos}/{eff} → failure {roll_res.get('rolls')} consequence {consequence} ticks {ticks}. <DM/>"
