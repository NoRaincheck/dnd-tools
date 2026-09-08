"""Blades score simulation — single score (like one heist) + engagements.

Mirrors tricube simulation but for Position/Effect + Stress + Clocks.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from dnd_tools.mapgen import make_indoor_map, make_outdoor_map

from .agents import heuristic_player_turn
from .models import BladesCharacter
from .state import BladesCampaignState, BladesState
from .tools import BladesCampaignTools, BladesTools


def create_blades_player(
    name: str,
    playbook: str = "Cutter",
    actions: dict[str, int] | None = None,
    vice: str = "Pleasure",
) -> BladesCharacter:
    return BladesCharacter(name=name, playbook=playbook, actions=actions or {}, vice=vice)


def create_blades_opposition(name: str, segments: int = 6) -> BladesCharacter:
    # opposition represented as minimal BladesCharacter (no stress) but we store as monster for map compat
    return BladesCharacter(name=name, playbook="Cutter", actions={}, is_player=False)


def initialize_blades_score(
    state: BladesState,
    players: list[BladesCharacter],
    opposition: list[BladesCharacter] | None = None,
    map_kind: str = "indoor",
    seed: int = 0,
    clocks: list[tuple[str, int, str]] | None = None,
) -> BladesState:
    if map_kind == "indoor":
        cells = make_indoor_map(seed)
    else:
        cells = make_outdoor_map(seed)
    state.set_map(cells)
    w, h = state.map_size()
    cx, cy = w // 2, h // 2
    for i, p in enumerate(players):
        x = cx - 4 + (i % 2) * 2
        y = cy - 1 + (i // 2) * 2
        x = max(1, min(w - 2, x))
        y = max(1, min(h - 2, y))
        cells[y][x].valid = True
        cells[y][x].z = 0
        state.add_player(p, (x, y, 0))
    if opposition:
        for i, m in enumerate(opposition):
            x = cx + 2 + (i % 2) * 2
            y = cy - 1 + (i // 2) * 2
            x = max(1, min(w - 2, x))
            y = max(1, min(h - 2, y))
            cells[y][x].valid = True
            cells[y][x].z = 0
            state.add_monster(m, (x, y, 0))
    # clocks
    if clocks:
        for name, seg, kind in clocks:
            state.set_clock(name, seg, kind)
    else:
        state.set_clock("Score Clock", 6, "obstacle")
        state.set_clock("Heat Clock", 4, "danger")
    return state


def generate_blades_scenarios(seed: int = 42, out_dir: Path | str = "scenarios") -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    playbook_groups = [
        ["Cutter", "Lurk", "Spider", "Whisper"],
        ["Hound", "Leech", "Slide", "Cutter"],
        ["Whisper", "Spider", "Lurk", "Slide"],
    ]
    clock_sets = [
        {"name": "Infiltrate Manor", "clocks": [("Infiltrate", 6, "obstacle"), ("Alert", 6, "danger")]},
        {"name": "Steal Ledger", "clocks": [("Ledger", 4, "obstacle"), ("Suspicion", 6, "danger")]},
        {"name": "Occult Ritual", "clocks": [("Ritual", 8, "obstacle"), ("Doom", 6, "danger")]},
    ]
    paths: list[Path] = []
    sid = 0
    for g in playbook_groups:
        for tier_heat in [0, 2, 4]:
            for cs in clock_sets:
                sid += 1
                data = {"scenario_id": sid, "seed": seed + sid, "group": g, "heat": tier_heat, "clock_set": cs}
                p = out / f"blades_scenario_{sid:02d}.json"
                with open(p, "w") as f:
                    json.dump(data, f, indent=2)
                paths.append(p)
    return paths


def load_blades_scenario(path: Path | str) -> tuple[BladesState, BladesTools]:
    with open(path) as f:
        spec = json.load(f)
    seed = spec.get("seed", 0)
    random.seed(seed)
    state = BladesState(seed_val=seed)
    players: list[BladesCharacter] = []
    for i, pb in enumerate(spec["group"]):
        players.append(create_blades_player(f"P{i + 1}_{pb}", playbook=pb))
    # crew heat
    state.crew.heat = int(spec.get("heat", 0))
    # clocks
    cs = spec.get("clock_set", {})
    clocks = [(n, seg, kind) for n, seg, kind in cs.get("clocks", [("Score", 6, "obstacle")])]
    initialize_blades_score(state, players, clocks=clocks, map_kind="indoor", seed=seed)
    tools = BladesTools(state)
    return state, tools


# ------------------------------------------------------------------
# Simulation loop — turn-by-turn score
# ------------------------------------------------------------------


class BladesSimulation:
    def __init__(
        self,
        state: BladesState | BladesCampaignState,
        tools: BladesTools | BladesCampaignTools | None = None,
        llm: Any | None = None,
        use_heuristic: bool = True,
        max_turns: int = 10,
        plan: str = "infiltration",
        detail: str = "quietly through the canal",
    ):
        if isinstance(state, BladesCampaignState):
            self.cstate: BladesCampaignState | None = state
            self.state: BladesState = state.inner
            self.tools: BladesTools | BladesCampaignTools = tools or BladesCampaignTools(state)  # type: ignore
        else:
            self.cstate = None
            self.state = state
            self.tools = tools or BladesTools(state)  # type: ignore
        self.llm = llm
        if llm is None and not use_heuristic:
            try:
                from .agents import LLMClient

                self.llm = LLMClient()
            except Exception:
                self.llm = None
                use_heuristic = True
        self.use_heuristic = use_heuristic
        self.max_turns = max_turns
        self.plan = plan
        self.detail = detail

    def _player_turn(self, name: str) -> None:
        ch = self.state.get_character(name)
        if not ch or not ch.alive or ch.retired:
            return
        # Blades players use position/effect gate; side check is flavor
        if self.use_heuristic or not self.llm:
            line = heuristic_player_turn(name, self.tools, self.cstate or self.state)  # type: ignore
            self.state.add_transcript(line)
        else:
            try:
                from .agents import run_tau_player_turn_sync

                provider = getattr(self.llm, "provider", None) or getattr(self.llm, "_provider", None)
                model = getattr(self.llm, "model", "qwen3.6-35b-a3b-mtp")
                if provider is None:
                    from .agents import make_tau_provider

                    provider = make_tau_provider(
                        getattr(self.llm, "base_url", "http://127.0.0.1:1234/v1"),
                        getattr(self.llm, "api_key", "lm-studio"),
                    )
                cstate = self.cstate or self.state
                line = run_tau_player_turn_sync(
                    player_name=name, tools=self.tools, state=cstate, provider=provider, model=model, max_turns=6
                )  # type: ignore
                self.state.add_transcript(line)
            except Exception as e:
                self.state.add_transcript(f"{name}: [tau fallback {e}] <DM/>")
                line = heuristic_player_turn(name, self.tools, self.cstate or self.state)  # type: ignore
                self.state.add_transcript(line)
        try:
            self.tools.end_turn(name)  # type: ignore
        except Exception:
            pass
        self.state.add_transcript("<End Turn/>")

    def _opposition_turn(self, name: str) -> None:
        # Opposition doesn't roll on its own; we tick a danger clock to pressure
        danger_clocks = [k for k, v in self.state.clocks.items() if v.kind == "danger" and not v.completed]
        if danger_clocks:
            clk = danger_clocks[0]
            self.state.tick_clock(clk, 1)
            self.state.add_transcript(
                f"{name} (opposition) pressures crew → {clk} ticks to {self.state.clocks[clk].ticks}/{self.state.clocks[clk].segments}"
            )
        else:
            self.state.add_transcript(f"{name} holds position")
        try:
            self.tools.end_turn(name)  # type: ignore
        except Exception:
            pass
        self.state.add_transcript("<End Turn/>")

    def run(self) -> dict[str, Any]:
        # Engagement roll
        try:
            eng = self.tools.engage_roll(self.plan, self.detail, dice=1)  # type: ignore
            self.state.add_transcript(f"Engagement ({self.plan}/{self.detail}): {eng}")
        except Exception:
            pass
        init = self.tools.roll_initiative()  # type: ignore
        self.state.add_transcript(f"Initiative: {init}")
        self.state.add_transcript("<End Turn/>")
        turn_count = 0
        while turn_count < self.max_turns:
            # end conditions: all obstacle clocks completed or all players retired
            players_alive = any(c.alive and not c.retired for c in self.state.players.values())
            obstacle_clocks = [v for v in self.state.clocks.values() if v.kind == "obstacle"]
            if obstacle_clocks and all(v.completed for v in obstacle_clocks):
                self.state.add_transcript("Score completed — all obstacle clocks filled!")
                break
            if not players_alive:
                self.state.add_transcript("Crew retired/withdrawn — score ends")
                break
            actor = self.state.current_actor()
            if not actor:
                break
            ch = self.state.get_character(actor)
            if not ch or not ch.alive or ch.retired:
                self.state.advance_turn()
                continue
            is_monster = actor in self.state.monsters
            if is_monster:
                self.state.add_transcript(f"--- Opposition Turn: {actor} (round {self.state.round}) ---")
                self._opposition_turn(actor)
            else:
                self.state.add_transcript(f"--- Scoundrel Turn: {actor} (round {self.state.round}) ---")
                self._player_turn(actor)
            self.state.advance_turn()
            turn_count += 1
            # also show clocks occasionally
            if turn_count % 3 == 0:
                try:
                    vis = self.tools.visualize_clocks()  # type: ignore
                    self.state.add_transcript(f"Clocks: {vis.get('ascii', '')}")
                except Exception:
                    pass
        # payoff / heat summary (minimal)
        try:
            death = self.tools.print_trauma_log()  # type: ignore
        except Exception:
            death = {"log": []}
        if self.cstate:
            self.cstate.checkpoint()
            if len(self.state.tool_trace) > 400:
                self.cstate.prune_traces(keep_last=300)
        return {
            "transcript": self.state.transcript,
            "tool_trace": self.state.tool_trace,
            "death": death,
            "players": {
                n: {
                    "stress": c.stress,
                    "max": c.stress_max,
                    "trauma": len(c.trauma),
                    "harm": len(c.harm),
                    "retired": c.retired,
                    "alive": c.alive,
                }
                for n, c in self.state.players.items()
            },
            "clocks": {
                k: {"ticks": v.ticks, "segments": v.segments, "completed": v.completed}
                for k, v in self.state.clocks.items()
            },
            "crew": {"heat": self.state.crew.heat, "tier": self.state.crew.tier, "coin": self.state.crew.coin},
            "rounds": self.state.round,
        }
