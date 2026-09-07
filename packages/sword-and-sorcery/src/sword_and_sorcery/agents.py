"""S&S agents — tau harness + heuristic fallback."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .prompts import PLAYER_PROMPT
from .state import SnSCampaignState, SnSState
from .tools import SnSCampaignTools, SnSTools

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


def _tools_to_agent_tools(tools: SnSTools | SnSCampaignTools) -> list[AgentTool]:  # type: ignore[no-untyped-def]
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
    tools: SnSTools | SnSCampaignTools,
    user_content: str,
    max_turns: int = 6,
) -> tuple[str, list[dict[str, Any]]]:
    agent_tools = _tools_to_agent_tools(tools)
    harness = AgentHarness(
        AgentHarnessConfig(provider=provider, model=model, system=system, tools=agent_tools, max_turns=max_turns)
    )
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
    tools: SnSTools | SnSCampaignTools,
    state: SnSState | SnSCampaignState,
    provider,
    model: str,
    max_turns: int = 6,
) -> str:
    inner: SnSState = state.inner if isinstance(state, SnSCampaignState) else state  # type: ignore
    ch = inner.get_player(player_name)
    if not ch:
        return f"{player_name}: error no character. <DM/>"
    system = (
        PLAYER_PROMPT
        + f"\nYou are {player_name} the {ch.ancestry} {ch.background} (S&S {ch.sns}, HP {ch.hp}/{ch.hp_max} SP {ch.sp}/{ch.sp_max} WD {ch.wd} EN {ch.en}, spells {ch.spells_known[:3]})."
    )
    alive_m = [
        f"{k} {v.threat} HP {v.hp}/{v.hp_max} DMG {v.dmg} at {inner.get_pos(k)}"
        for k, v in inner.monsters.items()
        if v.alive
    ]
    ctx = (
        f"Your turn: {player_name} ancestry {ch.ancestry} background {ch.background} S&S {ch.sns} HP {ch.hp}/{ch.hp_max} SP {ch.sp}/{ch.sp_max} WD {ch.wd} EN {ch.en} spells {ch.spells_known} at {inner.get_pos(player_name)}. "
        f"Alive players: {[k for k, v in inner.players.items() if v.alive]} Monsters: {alive_m} Adventure: {inner.adventure}\n"
        f"Map (ASCII, #=wall, upper=player, lower=monster):\n{tools.visualize_map()}\n"  # type: ignore
        f"Instructions: 1) Call check_character and check_monster for your target. "
        f"2) For attacks call attack with prepared/trained flags (trained if your background/ancestry fits, prepared if you set up). "
        f"3) For magic call cast_spell (level 0 no roll, level>=1 needs sorcery). "
        f"4) To help ally call help BEFORE their roll. "
        f"5) If you rolled exactly S&S, call divine_intervention with a good question. "
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


# Compat wrapper like tricube
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


def heuristic_player_turn(char_name: str, tools: SnSTools | SnSCampaignTools, state: Any) -> str:  # type: ignore[no-untyped-def]
    inner: SnSState = state.inner if hasattr(state, "inner") else state
    ch = inner.get_player(char_name)
    if not ch:
        return f"{char_name}: error. <DM/>"
    # choose nearest alive monster
    cands = [(n, m) for n, m in inner.monsters.items() if m.alive]
    if not cands:
        return f"{char_name}: no threats — holds position. <DM/>"
    # pick nearest by distance
    best = None
    best_d = 1e9
    for n, _ in cands:
        try:
            d = inner.distance_feet(char_name, n)
            if d < best_d:
                best_d = d
                best = n
        except Exception:
            pass
    target = best or cands[0][0]
    mon = inner.get_monster(target)
    # decide strategy: if S&S low (sorcery) and has spells + SP, maybe cast
    # if ch.sns <=3 and ch.sp>0 and "Fireball" in ch.spells_known or any spell, use cast
    # else attack
    # simple: if sns <=3 and sp >=1 and distance maybe use spell
    use_spell = False
    spell_choice = None
    # prefer Icebolt/Fireball for damage
    if ch.sns <= 3 and ch.sp > 0:
        for cand in ["Fireball", "Icebolt", "Lightning Storm", "Heal"]:
            if cand in ch.spells_known:
                spell_choice = cand
                use_spell = True
                break
        if not spell_choice and ch.spells_known:
            # pick first non-zero
            lvl1 = [
                s
                for s in ch.spells_known
                if s in ["Beast-Speak", "Icebolt", "Friendship", "Grease", "Heal", "Fireball", "Invisibility"]
            ]
            if lvl1:
                spell_choice = lvl1[0]
                use_spell = True
    # check LoS and move if needed
    try:
        los = tools.check_valid_attack_line(char_name, target)  # type: ignore
    except Exception:
        los = True
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
    # trained heuristic: if background matches action type, mark trained
    # e.g. Soldier/Tracker for swords, Sage for sorcery
    if use_spell and spell_choice:
        trained = ch.background in ("Sage", "Entertainer") or ch.sns <= 3
        # also if low hp and Heal, prioritize healing self/allies
        if spell_choice == "Heal":
            # find wounded ally
            wounded = [(n, c) for n, c in inner.players.items() if c.hp < c.hp_max and c.alive]
            if wounded:
                # heal most wounded
                wounded.sort(key=lambda x: x[1].hp)
                tgt_name = wounded[0][0]
                res = tools.cast_spell(char_name, "Heal", level=2, trained=trained, targets=[tgt_name])  # type: ignore
                roll = res.get("roll") or {}
                if res.get("success"):
                    dmg = res.get("damage", {})
                    tgt = inner.get_player(tgt_name)
                    tgt_hp = f"{tgt.hp}/{tgt.hp_max}" if tgt else "?"
                    return f"{char_name} casts Heal on {tgt_name} ({dmg.get('rolls')} +{dmg.get('total')}) → {tgt_name} {tgt_hp} SP {ch.sp}/{ch.sp_max}. <DM/>"
                else:
                    return f"{char_name} tries Heal on {tgt_name} sorcery {roll.get('rolls')} vs S&S {ch.sns} -> {roll.get('outcome')} (backlash). <DM/>"
        # damage spell
        res = tools.cast_spell(char_name, spell_choice, trained=trained, targets=[target])  # type: ignore
        roll = res.get("roll") or {}
        if res.get("success"):
            dmg = res.get("damage", {})
            mon_hp = f"{mon.hp}/{mon.hp_max}" if mon else "?"
            return f"{char_name} casts {spell_choice} at {target} sorcery {roll.get('rolls')} vs S&S {ch.sns} -> {roll.get('outcome')} damage {dmg.get('rolls')}=>{dmg.get('total')} {target} HP {mon_hp} SP {ch.sp}/{ch.sp_max}. <DM/>"
        else:
            # fail
            if roll:
                return f"{char_name} casts {spell_choice} sorcery {roll.get('rolls')} vs S&S {ch.sns} -> {roll.get('outcome')} (bad magic). SP {ch.sp}/{ch.sp_max}. <DM/>"
            return f"{char_name} casts {spell_choice} (level 0) no roll. <DM/>"
    else:
        # weapon attack (SWORDS)
        trained = ch.background in ("Soldier", "Tracker", "Thief", "Noble") or ch.sns >= 4
        res = tools.attack(char_name, target, trained=trained)  # type: ignore
        roll = res.get("roll", {})
        dmg = res.get("damage", {})
        defender_hp = res.get("defender_hp", {})
        if roll.get("success"):
            # divine?
            div = " Divine Intervention!" if roll.get("divine_intervention") else ""
            return f"{char_name} attacks {target} (SWORDS) {roll.get('rolls')} vs S&S {ch.sns} -> {roll.get('outcome')}{div} damage {dmg.get('rolls')}=>{dmg.get('damage')} {target} HP {defender_hp.get('hp')}/{defender_hp.get('max')}. <DM/>"
        else:
            div = " Divine!" if roll.get("divine_intervention") else ""
            return f"{char_name} attacks {target} (SWORDS) {roll.get('rolls')} vs S&S {ch.sns} -> {roll.get('outcome')}{div} (miss, GM worsens). <DM/>"
