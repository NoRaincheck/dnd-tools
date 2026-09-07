"""S&S scene simulation — single scene / adventure.

Mirrors tricube simulation but for S&S 1-3d6 < / > S&S, WD, SP, etc.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from dnd_tools.mapgen import make_indoor_map, make_outdoor_map

from .agents import heuristic_player_turn
from .models import (
    SnSCharacter,
    SnSMonster,
    roll_sns_number,
)
from .state import SnSCampaignState, SnSState
from .tools import SnSCampaignTools, SnSTools


def create_sns_player(
    name: str,
    ancestry: str = "Human",
    background: str = "Soldier",
    sns: int | None = None,
    spells: list[str] | None = None,
) -> SnSCharacter:
    if sns is None:
        sns = roll_sns_number()
    ch = SnSCharacter(name=name, ancestry=ancestry, background=background, sns=sns)
    if spells is not None:
        ch.spells_known = spells
    return ch


def create_sns_monster(name: str, threat: str = "Medium", hp: int | None = None, dmg: int | None = None) -> SnSMonster:
    return SnSMonster(name=name, threat=threat, hp=hp or 0, hp_max=hp or 0, dmg=dmg or 0)


def initialize_sns_scene(
    state: SnSState,
    players: list[SnSCharacter],
    monsters: list[SnSMonster],
    map_kind: str = "outdoor",
    seed: int = 0,
    adventure: dict[str, str] | None = None,
) -> SnSState:
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
    if adventure:
        state.adventure = adventure
    else:
        from .models import roll_adventure

        state.adventure = roll_adventure(random.Random(seed))
    return state


def generate_sns_scenarios(seed: int = 42, out_dir: Path | str = "scenarios") -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # 3 groups × 3 threat mixes? simple 27 like dnd but with S&S flavors
    groups = [
        [("Human", "Soldier", 5), ("Elf", "Sage", 2), ("Dwarf", "Noble", 4), ("Gnome", "Thief", 3)],
        [("Orc", "Tracker", 4), ("Catfolk", "Entertainer", 2), ("Human", "Soldier", 5), ("Elf", "Sage", 3)],
        [("Dwarf", "Thief", 3), ("Human", "Tracker", 4), ("Orc", "Soldier", 5), ("Gnome", "Sage", 2)],
    ]
    monster_sets = [
        {"name": "Goblin Ambush", "threats": ["Easy", "Easy", "Easy", "Easy"], "map": "outdoor"},
        {"name": "Kennel", "threats": ["Medium", "Easy", "Easy"], "map": "indoor"},
        {"name": "Dragon's Lair", "threats": ["Hard", "Medium"], "map": "indoor"},
    ]
    paths: list[Path] = []
    sid = 0
    for g in groups:
        for rank_threat in [["Easy"], ["Medium"], ["Hard"]]:  # placeholder tier
            _ = rank_threat
            for ms in monster_sets:
                sid += 1
                data = {"scenario_id": sid, "seed": seed + sid, "group": g, "monster_set": ms}
                p = out / f"sns_scenario_{sid:02d}.json"
                with open(p, "w") as f:
                    json.dump(data, f, indent=2)
                paths.append(p)
    return paths


def load_sns_scenario(path: Path | str) -> tuple[SnSState, SnSTools]:
    with open(path) as f:
        spec = json.load(f)
    seed = spec.get("seed", 0)
    random.seed(seed)
    state = SnSState(seed_val=seed)
    players: list[SnSCharacter] = []
    for anc, bg, sns in spec["group"]:
        players.append(create_sns_player(f"{anc[:2]}_{bg}", ancestry=anc, background=bg, sns=sns))
    mobs = spec["monster_set"]
    monsters: list[SnSMonster] = []
    for i, threat in enumerate(mobs["threats"]):
        monsters.append(create_sns_monster(f"M{i + 1}_{threat}", threat=threat))
    initialize_sns_scene(state, players, monsters, map_kind=mobs["map"], seed=seed)
    tools = SnSTools(state)
    return state, tools


# ------------------------------------------------------------------
# Simulation loop
# ------------------------------------------------------------------


class SnSSimulation:
    def __init__(
        self,
        state: SnSState | SnSCampaignState,
        tools: SnSTools | SnSCampaignTools | None = None,
        llm: Any | None = None,
        use_heuristic: bool = True,
        max_turns: int = 10,
    ):
        if isinstance(state, SnSCampaignState):
            self.cstate: SnSCampaignState | None = state
            self.state: SnSState = state.inner
            self.tools: SnSTools | SnSCampaignTools = tools or SnSCampaignTools(state)  # type: ignore
        else:
            self.cstate = None
            self.state = state
            self.tools = tools or SnSTools(state)  # type: ignore
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
        mon = self.state.get_monster(name)
        if not mon or not mon.alive:
            return
        self.tools.check_valid_attack_line(
            name, self.state.all_player_names()[0] if self.state.all_player_names() else name
        )  # type: ignore
        # pick nearest alive player
        alive_players = [(n, c) for n, c in self.state.players.items() if c.alive and not c.unconscious]
        if not alive_players:
            # all unconscious — monster waits
            self.state.add_transcript(
                f"{name} (monster, {mon.threat} DMG {mon.dmg}) looms over unconscious party. <End Turn/>"
            )
            return
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
        tch = self.state.get_player(target)
        # In S&S, only players roll: ask target to roll SWORDS to avoid
        # We simulate via the target's SWORDS roll; fail => take mon.dmg
        # Use roll_check directly
        # Determine if target is prepared/trained for defense: if background suggests dodge, mark trained
        if not tch:
            return
        trained = tch.background in ("Thief", "Tracker", "Soldier")
        # We use roll_check SWORDS; on fail take DMG, barely may take half?
        res = self.tools.roll_check(target, "swords", trained=trained)  # type: ignore
        dmg = 0
        if res["outcome"] == "fail":
            dmg = mon.dmg
        elif res["outcome"] == "barely":
            dmg = max(1, mon.dmg // 2)
        elif res["outcome"] == "critical":
            dmg = 0  # extra benefit
        # handle divine
        div_note = " Divine Intervention!" if res.get("divine_intervention") else ""
        if dmg:
            self.state.update_hp(target, -dmg)
            # if now 0, they are unconscious — one save chance (we allow next turn to roll)
            self.state.add_transcript(
                f"{name} (monster {mon.threat}) attacks {target}: {target} SWORDS {res['rolls']} vs S&S {tch.sns} -> {res['outcome']}{div_note} | takes {dmg} DMG -> {tch.hp}/{tch.hp_max}{' UNCONSCIOUS' if tch.unconscious else ''}."
            )
        else:
            self.state.add_transcript(
                f"{name} (monster {mon.threat}) attacks {target}: {target} SWORDS {res['rolls']} vs S&S {tch.sns} -> {res['outcome']}{div_note} | avoids damage."
            )
        if res.get("divine_intervention"):
            self.tools.divine_intervention(target, "What should I lookout for?")  # type: ignore
        self.tools.end_turn(name)  # type: ignore
        self.state.add_transcript("<End Turn/>")

    def _player_turn(self, name: str) -> None:
        ch = self.state.get_player(name)
        if not ch or not ch.alive:
            return
        if ch.unconscious:
            # one chance to save: roll SWORDS or SORCERY to stabilize? Use SWORDS trained if poss
            self.state.add_transcript(f"--- Player Turn: {name} (unconscious — save chance) ---")
            res = self.tools.roll_check(name, "swords", trained=True)  # type: ignore
            if res["success"]:
                ch.hp = 1
                ch.unconscious = False
                self.state.add_transcript(
                    f"{name} stabilizes! SWORDS {res['rolls']} vs {ch.sns} -> {res['outcome']} recovers to 1 HP."
                )
            else:
                ch.alive = False
                ch.unconscious = False
                self.state.death_log.append(f"{name} died after failing save at 0 HP")
                self.state.add_transcript(f"{name} fails save {res['rolls']} -> dies.")
            self.tools.end_turn(name)  # type: ignore
            self.state.add_transcript("<End Turn/>")
            return
        self.state.add_transcript(f"--- Player Turn: {name} (round {self.state.round}) ---")
        # side check
        try:
            self.tools.check_character(name)  # type: ignore
        except Exception:
            pass
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
        self.tools.end_turn(name)  # type: ignore
        self.state.add_transcript("<End Turn/>")

    def run(self) -> dict[str, Any]:
        init = self.tools.roll_initiative()  # type: ignore
        self.state.add_transcript(f"Initiative: {init}")
        if self.state.adventure:
            self.state.add_transcript(f"Adventure: {self.state.adventure}")
        self.state.add_transcript("<End Turn/>")
        turn_count = 0
        while turn_count < self.max_turns:
            players_alive = any(c.alive for c in self.state.players.values())
            monsters_alive = any(m.alive for m in self.state.monsters.values())
            if not players_alive or not monsters_alive:
                # but allow unconscious recovery chance still counts as alive? we treat alive true but unconscious true; loop continues until death
                if not monsters_alive:
                    break
                if not any(c.alive and not c.unconscious for c in self.state.players.values()):
                    # check if any unconscious still has save chance — one more round
                    unconscious_savable = any(c.alive and c.unconscious for c in self.state.players.values())
                    if not unconscious_savable:
                        break
                    # else continue to let them save
            actor = self.state.current_actor()
            if not actor:
                break
            ch = self.state.get_character(actor)
            if not ch or not ch.alive:
                self.state.advance_turn()
                continue
            # if player unconscious, still give them turn to save
            is_monster = actor in self.state.monsters
            if is_monster:
                self.state.add_transcript(f"--- Monster Turn: {actor} (round {self.state.round}) ---")
                self._monster_turn(actor)
            else:
                self._player_turn(actor)
            self.state.advance_turn()
            turn_count += 1
        death = self.tools.print_death_log()  # type: ignore
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
                    "hp": c.hp,
                    "max": c.hp_max,
                    "sp": c.sp,
                    "sp_max": c.sp_max,
                    "sns": c.sns,
                    "alive": c.alive,
                    "unconscious": c.unconscious,
                }
                for n, c in self.state.players.items()
            },
            "monsters": {
                n: {"hp": m.hp, "max": m.hp_max, "alive": m.alive, "threat": m.threat}
                for n, m in self.state.monsters.items()
            },
            "adventure": self.state.adventure,
            "rounds": self.state.round,
        }
