"""Triple-O middleware — wraps a tau LLM turn to force Triple-O creativity.

Flow (per player / per dilemma):
  1) LLM must propose three branches (obvious/option/odd) — constrained option space.
  2) Middleware rolls 1d6 (or 2d6 double-down) — deterministic via TripleO seed.
  3) Selected branch is returned to harness + narrated.

This is model-agnostic: the harness only ever executes the rolled branch.
Heuristic fallback does the same propose→roll loop without an LLM.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .core import TripleO
from .spark import roll_spark
from .tools import TripleOTools

try:
    from tau_agent.harness import AgentHarness, AgentHarnessConfig
    from tau_agent.messages import AssistantMessage, TextContent
    from tau_agent.tools import AgentTool, AgentToolResult
    from tau_ai.env import OpenAICompatibleConfig
    from tau_ai.openai_compatible import OpenAICompatibleProvider

    _TAU_AVAILABLE = True
except Exception:  # pragma: no cover
    _TAU_AVAILABLE = False


def make_triple_o_provider(base_url: str = "http://127.0.0.1:1234/v1", api_key: str = "lm-studio"):
    if not _TAU_AVAILABLE:
        raise RuntimeError("tau-ai not installed — `uv add tau-ai`")
    cfg = OpenAICompatibleConfig(api_key=api_key, base_url=base_url.rstrip("/"), timeout_seconds=60.0, max_retries=1)
    return OpenAICompatibleProvider(cfg)


def _tools_to_agent_tools(tools: TripleOTools) -> list[AgentTool]:  # type: ignore[no-untyped-def]
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


async def _run_triple_o_harness(
    *,
    provider,
    model: str,
    system: str,
    tools: TripleOTools,
    user_content: str,
    max_turns: int = 8,
) -> tuple[str, list[dict[str, Any]]]:
    agent_tools = _tools_to_agent_tools(tools)
    harness = AgentHarness(
        AgentHarnessConfig(provider=provider, model=model, system=system, tools=agent_tools, max_turns=max_turns)
    )
    before = len(tools.tool_trace)
    last_text = ""
    async for _event in harness.prompt(user_content):
        pass
    traces = tools.tool_trace[before:]
    for msg in reversed(harness.messages):
        if isinstance(msg, AssistantMessage):
            last_text = "".join(c.text for c in msg.content if isinstance(c, TextContent))
            if last_text.strip():
                break
    if not last_text.strip() and traces:
        last = traces[-1]
        last_text = json.dumps(last.get("result", last), default=str)[:400]
    return last_text, traces


class TripleOMiddleware:
    """High-level middleware that orchestrates propose → roll → narrate.

    Parameters
    ----------
    engine:
        Seeded TripleO engine (if None, created with ``seed``).
    tools:
        TripleOTools bound to that engine (created automatically if omitted).
    seed:
        Only used if both engine/tools omitted.
    """

    SYSTEM_PROMPT = (
        "You are a Player Character Emulator using the Triple-O framework.\n"
        "When the GM asks what you do, you MUST propose three plausible branches:\n"
        "  Obvious (your Traits make this most predictable), Option (reasonable alternative), Odd (left-field / impulsive).\n"
        "Call propose_triple_o with those three short sentences (1-2 each), then STOP — the harness will roll 1d6\n"
        "(4-6 Obvious, 2-3 Option, 1 Odd) and decide which branch you actually execute.\n"
        "Args: character (your name), situation (one-line context), obvious/option/odd (each a sentence), traits (your Traits list).\n"
        "After the die chooses, narrate the chosen action in 1-2 sentences. "
        "You may optionally call spark_roll for flavour (Disposition/Motivation + Action/Method) before narrating.\n"
        "If uncertain, use ask_triple_o for GM yes/no questions.\n"
        "Never self-select; the die is authoritative."
    )

    def __init__(self, engine: TripleO | None = None, tools: TripleOTools | None = None, seed: int = 0):
        if tools is not None:
            self.tools = tools
            self.engine = tools.engine
        elif engine is not None:
            self.engine = engine
            self.tools = TripleOTools(engine)
        else:
            self.engine = TripleO(seed=seed)
            self.tools = TripleOTools(self.engine)

    def run_turn_sync(
        self,
        *,
        player_name: str,
        traits: str | list[str],
        situation: str,
        provider,
        model: str,
        advantage: str | None = None,
        max_turns: int = 8,
    ) -> dict[str, Any]:
        """Run one Triple-O turn synchronously.

        Returns dict with ``text`` (narration), ``roll`` dict, ``traces``.
        """
        trait_list = [traits] if isinstance(traits, str) else list(traits)
        system = self.SYSTEM_PROMPT + f"\nYou are {player_name} (Traits: {', '.join(trait_list)})."
        ctx = (
            f"Situation: {situation}\n"
            f"Character: {player_name} Traits: {trait_list}\n"
            f"Instructions: 1) Call propose_triple_o with character={player_name}, situation, obvious/option/odd and traits. "
            f"2) Then immediately call roll_triple_o" + (f" with advantage={advantage}" if advantage else "") + ". "
            f"3) Optionally call spark_roll for flavour. 4) Narrate the chosen branch in 1-2 sentences.\n"
            f"Spark hint: {roll_spark()} — use it to flavour the execution if you wish (not to override the die).\n"
        )
        try:
            text, traces = asyncio.run(
                _run_triple_o_harness(
                    provider=provider,
                    model=model,
                    system=system,
                    tools=self.tools,
                    user_content=ctx,
                    max_turns=max_turns,
                )
            )
        except Exception as e:
            return {"text": f"[tau error {e}]", "roll": None, "traces": [], "error": str(e)}
        # extract roll result from traces
        roll_res = None
        for t in traces:
            if t.get("tool") == "roll_triple_o":
                roll_res = t.get("result")
                break
        if roll_res is None:
            # maybe harness didn't follow — force a deterministic fallback propose→roll
            try:
                self.tools.propose_triple_o(
                    character=player_name,
                    situation=situation,
                    obvious=f"{player_name} acts cautiously given {trait_list[0] if trait_list else 'traits'}",
                    option=f"{player_name} tries a balanced alternative",
                    odd=f"{player_name} does something unexpected",
                    traits=trait_list,
                )
                roll_res = self.tools.roll_triple_o(player_name, advantage=advantage)
                if not text.strip():
                    text = f"{player_name} executes the {roll_res['category']} branch: {roll_res['choice']}"
            except Exception as e:
                return {"text": f"[fallback error {e}]", "roll": None, "traces": traces, "error": str(e)}
        return {"text": text, "roll": roll_res, "traces": traces}

    # heuristic fallback without LLM — still propose→roll for creativity push
    def run_heuristic(
        self,
        *,
        player_name: str,
        traits: list[str] | str,
        situation: str,
        obvious: str,
        option: str,
        odd: str,
        advantage: str | None = None,
    ) -> dict[str, Any]:
        trait_list = [traits] if isinstance(traits, str) else list(traits)
        self.tools.propose_triple_o(player_name, situation, obvious, option, odd, traits=trait_list)
        adv: str | None = None
        if advantage == "advantage" or advantage == "disadvantage":
            adv = advantage
        res = self.tools.roll_triple_o(player_name, advantage=adv)
        spark = roll_spark()
        narrative = (
            f"{player_name} ({res['category']}) — {res['choice']} "
            f"[{spark['disposition']} / {spark['motivation']} → {spark['action']} via {spark['method']}]"
        )
        return {"text": narrative, "roll": res, "spark": spark}
