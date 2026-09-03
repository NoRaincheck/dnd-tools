"""Tricube scene simulation — single scene (like one combat or challenge scene).

Mirrors dnd_tools.simulation.Simulation but for 1-3d6 / karma / resolve / effort.

LLM-verified example (tiel-coder-35b-a3b-mtp, seed 42, 3 turns):
  Initiative: Lyra 7, Fenn 7, Ogre 4 ... Lyra roll [6] vs 4 -> success -1 effort (Goblin1 0),
  Fenn crafty [6,6] vs 5 -> exceptional -> Ogre 0, monster pressure [1,5,4] vs 5 -> success,
  Tool Calls: 26 via TricubeTools (check_karma_resolve, roll_challenge, etc.) — see README.md
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from dnd_campaign.session import CampaignSession as DndCampaignSession  # interop / pattern reference
from dnd_tools.mapgen import make_indoor_map, make_outdoor_map
from dnd_tools.simulation import Simulation as DndSimulation  # pattern reuse

from .agents import heuristic_player_turn

_ = DndCampaignSession
_ = DndSimulation
from .models import TricubeCharacter, effort_for_rank
from .state import TricubeCampaignState, TricubeState
from .tools import TricubeCampaignTools, TricubeTools


def create_tricube_player(
    name: str,
    trait: str = "brawny",
    concept: str = "fighter",
    perk: str = "brave",
    quirk: str = "stubborn",
    combat_style: str | None = None,
    karma: int = 3,
    resolve: int = 3,
    rank: int = 1,
) -> TricubeCharacter:
    return TricubeCharacter(
        name=name,
        trait=trait.lower(),
        concept=concept,
        combat_style=(combat_style or "").lower() if combat_style else "",
        perks=[perk],
        quirks=[quirk],
        karma=karma,
        karma_max=karma,
        resolve=resolve,
        resolve_max=resolve,
        rank=rank,
    )


def create_tricube_monster(
    name: str,
    trait: str = "brawny",
    concept: str = "goblin",
    perk: str | None = None,
    rank: int = 1,
    effort: int | None = None,
    is_boss: bool = False,
) -> TricubeCharacter:
    ch = TricubeCharacter(
        name=name,
        trait=trait.lower(),
        concept=concept,
        perks=[perk] if perk else [],
        quirks=[],
        karma=0,
        karma_max=0,
        resolve=3,
        resolve_max=3,
        rank=rank,
        is_player=False,
    )
    ch._effort_init = effort if effort is not None else effort_for_rank(rank, is_boss=is_boss)  # type: ignore[attr-defined]
    return ch


def initialize_tricube_scene(
    state: TricubeState,
    players: list[TricubeCharacter],
    monsters: list[TricubeCharacter],
    map_kind: str = "outdoor",
    seed: int = 0,
) -> TricubeState:
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
    for i, m in enumerate(monsters):
        x = cx + 2 + (i % 2) * 2
        y = cy - 1 + (i // 2) * 2
        x = max(1, min(w - 2, x))
        y = max(1, min(h - 2, y))
        cells[y][x].valid = True
        cells[y][x].z = 0
        state.add_monster(m, (x, y, 0))
        eff = getattr(m, "_effort_init", effort_for_rank(m.rank))
        state.effort_pools[m.name] = int(eff)  # type: ignore[attr-defined]
    return state


# Scenario generation (27 like dnd)
def generate_tricube_scenarios(seed: int = 42, out_dir: Path | str = "scenarios") -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # reuse dnd-like 3 groups *3 tiers *3 monster sets
    groups = [
        [("agile", "assassin"), ("brawny", "knight"), ("crafty", "mage"), ("agile", "scout")],
        [("brawny", "soldier"), ("crafty", "healer"), ("agile", "thief"), ("brawny", "berserker")],
        [("crafty", "psionic"), ("agile", "pilot"), ("brawny", "merc"), ("crafty", "scholar")],
    ]
    monster_sets = [
        {
            "name": "Goblin Horde",
            "mobs": [("goblin", "agile", 1), ("goblin", "agile", 1), ("goblin", "agile", 1), ("goblin", "agile", 1)],
            "map": "outdoor",
        },
        {
            "name": "Kennel",
            "mobs": [("wolf", "brawny", 1), ("wolf", "brawny", 1), ("goblin", "agile", 1)],
            "map": "indoor",
        },
        {
            "name": "Ogre Cave",
            "mobs": [("ogre", "brawny", 2), ("goblin", "agile", 1), ("goblin", "agile", 1)],
            "map": "indoor",
        },
    ]
    paths: list[Path] = []
    sid = 0
    for g in groups:
        for tier_rank in [1, 2, 3]:
            for ms in monster_sets:
                sid += 1
                data = {"scenario_id": sid, "seed": seed + sid, "group": g, "rank": tier_rank, "monster_set": ms}
                p = out / f"tricube_scenario_{sid:02d}.json"
                with open(p, "w") as f:
                    json.dump(data, f, indent=2)
                paths.append(p)
    return paths


def load_tricube_scenario(path: Path | str) -> tuple[TricubeState, TricubeTools]:
    with open(path) as f:
        spec = json.load(f)
    seed = spec.get("seed", 0)
    random.seed(seed)
    state = TricubeState(seed_val=seed)
    rank = spec.get("rank", 1)
    players: list[TricubeCharacter] = []
    for i, (trait, concept) in enumerate(spec["group"]):
        players.append(
            create_tricube_player(
                f"P{i + 1}_{concept}", trait=trait, concept=concept, perk="brave", quirk="stubborn", rank=rank
            )
        )
    mobs = spec["monster_set"]
    monsters: list[TricubeCharacter] = []
    for i, (name, trait, r) in enumerate(mobs["mobs"]):
        monsters.append(create_tricube_monster(f"M{i + 1}_{name}", trait=trait, concept=name, rank=r))
    initialize_tricube_scene(state, players, monsters, map_kind=mobs["map"], seed=seed)
    tools = TricubeTools(state)
    return state, tools


# ------------------------------------------------------------------
# Simulation loop — turn-by-turn scene
# ------------------------------------------------------------------


class TricubeSimulation:
    def __init__(
        self,
        state: TricubeState | TricubeCampaignState,
        tools: TricubeTools | TricubeCampaignTools | None = None,
        llm: Any | None = None,
        use_heuristic: bool = True,
        max_turns: int = 10,
    ):
        # unwrap campaign state if needed
        if isinstance(state, TricubeCampaignState):
            self.cstate: TricubeCampaignState | None = state
            self.state: TricubeState = state.inner
            self.tools: TricubeTools | TricubeCampaignTools = tools or TricubeCampaignTools(state)  # type: ignore
        else:
            self.cstate = None
            self.state = state
            self.tools = tools or TricubeTools(state)  # type: ignore
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

    def _monster_turn(self, name: str) -> None:
        ch = self.state.get_character(name)
        if not ch or not ch.alive:
            return
        self.tools.check_side(name)  # type: ignore
        # choose nearest player with effort? monsters attack players resolve-wise
        alive_players = [(n, c) for n, c in self.state.players.items() if c.alive and not c.retired]
        if not alive_players:
            return
        # pick nearest
        best = None
        best_d = 1e9
        for n, _ in alive_players:
            try:
                d = self.state.distance_feet(name, n)
                if d < best_d:
                    best_d = d
                    best = n
            except Exception:
                pass
        target = best or alive_players[0][0]
        # move if not LoS
        try:
            los = self.tools.check_valid_attack_line(name, target)  # type: ignore
        except Exception:
            los = True
        if not los:
            cur = self.state.get_pos(name)
            tgt = self.state.get_pos(target)
            if cur and tgt:
                nx = cur[0] + (1 if tgt[0] > cur[0] else -1 if tgt[0] < cur[0] else 0)
                ny = cur[1] + (1 if tgt[1] > cur[1] else -1 if tgt[1] < cur[1] else 0)
                try:
                    self.tools.move_player(name, nx, ny)  # type: ignore
                except Exception:
                    pass
        # resolve as defense for player: monster's trait vs 5, player defends via defense_roll trait
        # we model monster attack as player defense roll to keep resolve semantics
        # if monster is attacker, we ask player to defend with their combat style trait
        t_ch = self.state.get_character(target)
        if not t_ch:
            return
        # For defense, defender uses own trait style? In Tales, defense is per attacker's intended? Use defender's combat trait? Simplified: defender's trait
        # We'll let defender roll vs 5 using their own trait's defense equivalence: use their trait
        # Heuristic: use defender's trait as defense trait (reflects style)
        # If monster trait strong vs defender, difficulty already rank-adjusted via roll_challenge if we passed effort_target
        # For defense, we directly call defense_roll on target
        res = self.tools.defense_roll(target, t_ch.trait, difficulty=5)  # type: ignore
        self.state.add_transcript(
            f"{name} (monster) pressures {target}: {res.get('rolls')} vs {res.get('effective_difficulty')} -> {'success' if res.get('success') else 'fail'}{' crit' if res.get('critical_failure') else ''} resolve cost {res.get('resolve_cost')} -> {t_ch.resolve}/{t_ch.resolve_max}"
        )
        self.tools.end_turn(name)  # type: ignore
        self._bookkeep(name)

    def _player_turn(self, name: str) -> None:
        ch = self.state.get_character(name)
        if not ch or not ch.alive or ch.retired:
            return
        self.tools.check_side(name)  # type: ignore
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
                # need wrapper that accepts CampaignState
                cstate = self.cstate or self.state
                line = run_tau_player_turn_sync(
                    player_name=name, tools=self.tools, state=cstate, provider=provider, model=model, max_turns=6
                )  # type: ignore
                self.state.add_transcript(line)
            except Exception as e:
                self.state.add_transcript(f"{name}: [tau fallback {e}] <DM/>")
                line = heuristic_player_turn(name, self.tools, self.cstate or self.state)  # type: ignore
                self.state.add_transcript(line)
        self.tools.end_turn(name)  # type: ignore
        self._bookkeep(name)

    def _bookkeep(self, name: str) -> None:
        # clear per-turn gates already in end_turn; nothing else
        self.state.add_transcript("<End Turn/>")

    def run(self) -> dict[str, Any]:
        init = self.tools.roll_initiative()  # type: ignore
        self.state.add_transcript(f"Initiative: {init}")
        self.state.add_transcript("<End Turn/>")
        turn_count = 0
        while turn_count < self.max_turns:
            # end conditions: all monsters effort 0 or all players retired/defeated?
            players_alive = any(c.alive and not c.retired for c in self.state.players.values())
            effort_remaining = sum(v for v in self.state.effort_pools.values())
            monsters_alive_effort = any(
                c.alive and self.state.effort_pools.get(c.name, 0) > 0 for c in self.state.monsters.values()
            )
            # also generic pools
            generic_effort = any(k not in self.state.monsters and v > 0 for k, v in self.state.effort_pools.items())
            if not players_alive or (effort_remaining == 0 and not generic_effort and not monsters_alive_effort):
                # scene may end even if generic challenge defeated
                if effort_remaining == 0:
                    break
                if not monsters_alive_effort and not generic_effort:
                    # if pools exist but no monster alive, still break
                    pass
            actor = self.state.current_actor()
            if not actor:
                break
            ch = self.state.get_character(actor)
            if not ch or not ch.alive or ch.retired:
                self.state.advance_turn()
                continue
            is_monster = actor in self.state.monsters
            if is_monster:
                self.state.add_transcript(f"--- Monster Turn: {actor} (round {self.state.round}) ---")
                self._monster_turn(actor)
            else:
                self.state.add_transcript(f"--- Player Turn: {actor} (round {self.state.round}) ---")
                self._player_turn(actor)
            self.state.advance_turn()
            turn_count += 1
            # also stop if effort fully cleared
            if sum(self.state.effort_pools.values()) == 0 and turn_count > 2:
                break
        death = self.tools.print_affliction_log()  # type: ignore[attr-defined]
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
                    "resolve": c.resolve,
                    "max": c.resolve_max,
                    "karma": c.karma,
                    "afflictions": len(c.afflictions),
                    "retired": c.retired,
                }
                for n, c in self.state.players.items()
            },
            "monsters": {
                n: {"effort": self.state.effort_pools.get(n, 0), "alive": c.alive}
                for n, c in self.state.monsters.items()
            },
            "effort_pools": dict(self.state.effort_pools),
            "rounds": self.state.round,
        }
