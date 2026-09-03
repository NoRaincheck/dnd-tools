"""TricubeState (scene) + TricubeCampaignState (long-horizon).

Reuses dnd_tools mapgen + dice seeding + Cell, but owns Tricube characters.
Campaign layer mirrors dnd_campaign.state.CampaignState: bounded history,
snapshot/restore, prune, short/long rest.

Map: 20x20 default, each cell 5ft for distance, z for LoS (imported logic).
Transcripts + tool_trace are auditable and bounded for LLM context.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dnd_campaign.state import CampaignState as DndCampaignState  # interop pattern reuse
from dnd_tools.dice import seed as dice_seed
from dnd_tools.models import Cell

from .dice import roll_tricube
from .models import Affliction, TricubeCharacter

_ = DndCampaignState

# ---------------------------------------------------------------------------
# Helpers for serialization
# ---------------------------------------------------------------------------


def _aff_to_dict(a: Affliction) -> dict[str, Any]:
    return asdict(a)


def _dict_to_aff(d: dict[str, Any]) -> Affliction:
    return Affliction(**d)


def _char_to_dict(c: TricubeCharacter) -> dict[str, Any]:
    d = asdict(c)
    d["pos"] = list(c.pos)
    d["afflictions"] = [_aff_to_dict(a) for a in c.afflictions]
    return d


def _dict_to_char(d: dict[str, Any]) -> TricubeCharacter:
    d = dict(d)
    d["pos"] = tuple(d.get("pos", (0, 0, 0)))
    d["afflictions"] = [_dict_to_aff(a) for a in d.get("afflictions", [])]
    # drop any unknown keys from older snapshots
    # TricubeCharacter handles defaults
    return TricubeCharacter(
        **{
            k: v
            for k, v in d.items()
            if k in TricubeCharacter.__dataclass_fields__ or k in TricubeCharacter.__annotations__
        }
    )


def _cell_to_dict(c: Cell) -> dict[str, Any]:
    return asdict(c)


def _dict_to_cell(d: dict[str, Any]) -> Cell:
    return Cell(**d)


# ---------------------------------------------------------------------------
# TricubeState — single scene
# ---------------------------------------------------------------------------


class TricubeState:
    def __init__(self, seed_val: int = 0, map_w: int = 20, map_h: int = 20):
        self.seed = seed_val
        dice_seed(seed_val)
        self.map: list[list[Cell]] = []
        self._make_empty_map(map_w, map_h)
        # characters: separate pools but unified lookup
        self.players: dict[str, TricubeCharacter] = {}
        self.monsters: dict[str, TricubeCharacter] = {}  # also TricubeCharacter but is_player=False
        self.players_pos: dict[str, tuple[int, int, int]] = {}
        self.monster_pos: dict[str, tuple[int, int, int]] = {}
        # effort pools for challenges/NPCs (grouped foes share one key)
        self.effort_pools: dict[str, int] = {}
        # turn/round
        self.initiative_order: list[str] = []
        self.current_turn_idx: int = 0
        self.round: int = 1
        # logs
        self.affliction_log: list[str] = []
        self.death_log: list[str] = []  # alias for compat
        self.tool_trace: list[dict[str, Any]] = []
        self.transcript: list[str] = []
        # per-challenge tracking for karma/quirk gates
        self._challenge_counter: int = 0

    # -- map ---------------------------------------------------------------

    def _make_empty_map(self, w: int, h: int) -> None:
        self.map = [[Cell(x=x, y=y, z=0, valid=True) for x in range(w)] for y in range(h)]

    def set_map(self, cells: list[list[Cell]]) -> None:
        self.map = cells

    def map_size(self) -> tuple[int, int]:
        return len(self.map[0]), len(self.map)

    # -- character management ----------------------------------------------

    def add_player(self, char: TricubeCharacter, pos: tuple[int, int, int]) -> None:
        char.is_player = True
        char.pos = pos
        self.players[char.name] = char
        self.players_pos[char.name] = pos

    def add_monster(self, char: TricubeCharacter, pos: tuple[int, int, int]) -> None:
        char.is_player = False
        char.pos = pos
        self.monsters[char.name] = char
        self.monster_pos[char.name] = pos

    def add_challenge(self, name: str, effort: int) -> None:
        self.effort_pools[name] = effort

    def get_character(self, name: str) -> TricubeCharacter | None:
        if name in self.players:
            return self.players[name]
        if name in self.monsters:
            return self.monsters[name]
        return None

    def get_pos(self, name: str) -> tuple[int, int, int] | None:
        if name in self.players_pos:
            return self.players_pos[name]
        if name in self.monster_pos:
            return self.monster_pos[name]
        return None

    def set_pos(self, name: str, pos: tuple[int, int, int]) -> None:
        if name in self.players_pos:
            self.players_pos[name] = pos
            self.players[name].pos = pos
        elif name in self.monster_pos:
            self.monster_pos[name] = pos
            self.monsters[name].pos = pos

    def all_player_names(self) -> list[str]:
        return list(self.players.keys())

    def all_monster_names(self) -> list[str]:
        return list(self.monsters.keys())

    def is_alive(self, name: str) -> bool:
        ch = self.get_character(name)
        return ch.alive if ch else False

    # -- initiative ---------------------------------------------------------

    def roll_initiative(self) -> list[dict[str, Any]]:
        """Tales: narrative order; for LLM we roll 1d6 per combatant (or 2d6 if trait matters).

        Simplified: each rolls 1d6 + (1 if rank>1 else 0). Deterministic via dice.
        """
        entries: list[tuple[int, str]] = []
        for c in list(self.players.values()) + list(self.monsters.values()):
            r = roll_tricube(1, 4)  # single d6 value in rolls[0]
            val = r["rolls"][0] + c.rank
            c.initiative = val
            entries.append((val, c.name))
        entries.sort(reverse=True)
        self.initiative_order = [n for _, n in entries]
        self.current_turn_idx = 0
        return [{"name": n, "initiative": v} for v, n in entries]

    def current_actor(self) -> str | None:
        if not self.initiative_order:
            return None
        return self.initiative_order[self.current_turn_idx % len(self.initiative_order)]

    def advance_turn(self) -> None:
        self.current_turn_idx += 1
        if self.current_turn_idx % len(self.initiative_order) == 0:
            self.round += 1

    # -- resolve / affliction ---------------------------------------------

    def check_resolve(self, name: str) -> int:
        ch = self.get_character(name)
        if not ch:
            raise KeyError(name)
        return ch.resolve

    def update_resolve(self, name: str, delta: int) -> dict[str, Any]:
        """delta negative = damage, positive = heal. Handles 0->affliction."""
        ch = self.get_character(name)
        if not ch:
            raise KeyError(name)
        if delta < 0:
            dmg = -delta
            ch.resolve = max(0, ch.resolve - dmg)
            if ch.resolve == 0:
                # defeated in scene — gain affliction placeholder; caller should call apply_affliction
                # we auto-create generic affliction if not already handled
                aff_name = f"affliction_r{self.round}"
                aff = Affliction(name=aff_name, permanent=False, recovery="scene")
                ch.afflictions.append(aff)
                msg = f"{name} defeated (0 resolve) → affliction '{aff_name}' (round {self.round})"
                self.affliction_log.append(msg)
                self.death_log.append(msg)
                # recover all resolve but mark as out for remainder of scene
                # we keep alive True unless retired; caller should handle scene participation
                ch.resolve = ch.resolve_max
                # if >3 afflictions, retire
                if len(ch.afflictions) > 3:
                    ch.alive = False
                    self.affliction_log.append(f"{name} retired (>3 afflictions)")
        else:
            ch.resolve = min(ch.resolve_max, ch.resolve + delta)
        return {
            "name": name,
            "resolve": ch.resolve,
            "max": ch.resolve_max,
            "alive": ch.alive,
            "afflictions": len(ch.afflictions),
        }

    # legacy alias
    def check_hp(self, name: str) -> int:  # pragma: no cover
        return self.check_resolve(name)

    def update_hp(self, name: str, delta: int) -> dict[str, Any]:  # pragma: no cover
        return self.update_resolve(name, delta)

    # -- distance / LoS (copied logic from GameState for map reuse) -------

    def distance_feet(self, a: str, b: str) -> float:
        pa = self.get_pos(a)
        pb = self.get_pos(b)
        if pa is None or pb is None:
            raise KeyError(f"position missing for {a} or {b}")
        dx = pa[0] - pb[0]
        dy = pa[1] - pb[1]
        return math.hypot(dx, dy) * 5

    def line_of_sight(self, attacker: str, defender: str) -> bool:
        sxyz = self.get_pos(attacker)
        gxyz = self.get_pos(defender)
        if sxyz is None or gxyz is None:
            raise KeyError("character not found")
        sx, sy, sz = sxyz
        gx, gy, gz = gxyz
        dx = gx - sx
        dy = gy - sy
        horiz = math.hypot(dx, dy)
        max_dim = max(len(self.map), len(self.map[0])) if self.map else 1
        num = int(horiz * max_dim) if horiz > 0 else 1
        num = max(num, 1)
        for i in range(num + 1):
            t = i / num
            x = sx + dx * t
            y = sy + dy * t
            z_line = sz + (gz - sz) * t
            xi = round(x)
            yi = round(y)
            xi = max(0, min(len(self.map[0]) - 1, xi))
            yi = max(0, min(len(self.map) - 1, yi))
            terrain_z = self.map[yi][xi].z
            if terrain_z >= z_line + 0.25:
                return False
        return True

    # -- logging -----------------------------------------------------------

    def log_tool(self, name: str, args: dict[str, Any], result: Any) -> None:
        self.tool_trace.append(
            {"tool": name, "args": args, "result": result, "round": self.round, "actor": self.current_actor()}
        )

    def add_transcript(self, line: str) -> None:
        self.transcript.append(line)


# ---------------------------------------------------------------------------
# TricubeCampaignState — multi-scene with context
# ---------------------------------------------------------------------------


class TricubeCampaignState:
    """Long-horizon wrapper around TricubeState, like dnd_campaign CampaignState."""

    def __init__(self, seed_val: int = 0, map_w: int = 20, map_h: int = 20, max_history: int = 100):
        self.inner: TricubeState = TricubeState(seed_val=seed_val, map_w=map_w, map_h=map_h)
        self.max_history: int = max_history
        self.history: list[dict[str, Any]] = []
        self.campaign_meta: dict[str, Any] = {"seed": seed_val, "scenes": 0, "total_rounds": 0}

    @property
    def seed(self) -> int:
        return self.inner.seed

    @property
    def round(self) -> int:
        return self.inner.round

    @property
    def tool_trace(self) -> list[dict[str, Any]]:
        return self.inner.tool_trace

    @property
    def transcript(self) -> list[str]:
        return self.inner.transcript

    # -- snapshots --------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        w, h = self.inner.map_size()
        return {
            "seed": self.inner.seed,
            "map": [[_cell_to_dict(c) for c in row] for row in self.inner.map],
            "map_w": w,
            "map_h": h,
            "players": {k: _char_to_dict(v) for k, v in self.inner.players.items()},
            "monsters": {k: _char_to_dict(v) for k, v in self.inner.monsters.items()},
            "players_pos": {k: list(v) for k, v in self.inner.players_pos.items()},
            "monster_pos": {k: list(v) for k, v in self.inner.monster_pos.items()},
            "effort_pools": dict(self.inner.effort_pools),
            "initiative_order": list(self.inner.initiative_order),
            "current_turn_idx": self.inner.current_turn_idx,
            "round": self.inner.round,
            "affliction_log": list(self.inner.affliction_log),
            "campaign_meta": dict(self.campaign_meta),
        }

    def restore(self, snap: dict[str, Any]) -> None:
        dice_seed(snap.get("seed", 0))
        self.inner.seed = snap.get("seed", 0)
        self.inner.map = [[_dict_to_cell(c) for c in row] for row in snap.get("map", [])]
        self.inner.players = {k: _dict_to_char(v) for k, v in snap.get("players", {}).items()}
        self.inner.monsters = {k: _dict_to_char(v) for k, v in snap.get("monsters", {}).items()}
        self.inner.players_pos = {k: tuple(v) for k, v in snap.get("players_pos", {}).items()}
        self.inner.monster_pos = {k: tuple(v) for k, v in snap.get("monster_pos", {}).items()}
        for k, pos in self.inner.players_pos.items():
            if k in self.inner.players:
                self.inner.players[k].pos = pos
        for k, pos in self.inner.monster_pos.items():
            if k in self.inner.monsters:
                self.inner.monsters[k].pos = pos
        self.inner.effort_pools = dict(snap.get("effort_pools", {}))
        self.inner.initiative_order = list(snap.get("initiative_order", []))
        self.inner.current_turn_idx = int(snap.get("current_turn_idx", 0))
        self.inner.round = int(snap.get("round", 1))
        self.inner.affliction_log = list(snap.get("affliction_log", []))
        self.inner.death_log = list(snap.get("affliction_log", []))
        self.campaign_meta = dict(snap.get("campaign_meta", {}))

    def checkpoint(self) -> None:
        self.history.append(self.snapshot())
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]

    # -- persistence ------------------------------------------------------

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "snapshot": self.snapshot(),
            "tool_trace": self.inner.tool_trace[-500:],
            "transcript_tail": self.inner.transcript[-200:],
        }
        p.write_text(json.dumps(payload, indent=2))
        return p

    @classmethod
    def load(cls, path: str | Path) -> TricubeCampaignState:
        p = Path(path)
        data = json.loads(p.read_text())
        snap = data.get("snapshot", data)
        cs = cls(seed_val=snap.get("seed", 0))
        cs.restore(snap)
        if "tool_trace" in data:
            cs.inner.tool_trace = list(data["tool_trace"])
        if "transcript_tail" in data:
            cs.inner.transcript = list(data["transcript_tail"])
        return cs

    # -- rests ------------------------------------------------------------

    def short_rest(self, name: str) -> dict[str, Any]:
        ch = self.inner.get_character(name)
        if not ch:
            raise KeyError(name)
        # Tricube: no HP, just reset economy if we had it; for now no num_of_action, so just note
        return {"name": name, "resolve": ch.resolve}

    def long_rest(self, name: str | None = None) -> dict[str, Any]:
        targets: list[TricubeCharacter] = []
        if name is not None:
            ch = self.inner.get_character(name)
            if not ch:
                raise KeyError(name)
            targets = [ch]
        else:
            targets = list(self.inner.players.values())
        out: dict[str, Any] = {}
        for ch in targets:
            # full resolve
            ch.resolve = ch.resolve_max
            # clear non-permanent afflictions? In Tales, long rest not defined; we clear flesht? For campaign we clear scene afflictions only.
            # Keep permanent ones, clear scene-recovery ones.
            before = len(ch.afflictions)
            ch.afflictions = [
                a for a in ch.afflictions if a.permanent or a.recovery not in ("scene", "minutes", "hours")
            ]
            # if we cleared, note
            ch.alive = len(ch.afflictions) <= 3
            out[ch.name] = {
                "resolve": ch.resolve,
                "afflictions": len(ch.afflictions),
                "cleared": before - len(ch.afflictions),
            }
        self.campaign_meta["scenes"] = self.campaign_meta.get("scenes", 0)  # unchanged
        return out

    def prune_traces(self, keep_last: int = 200) -> None:
        if len(self.inner.tool_trace) > keep_last:
            self.inner.tool_trace = self.inner.tool_trace[-keep_last:]
        if len(self.inner.transcript) > keep_last:
            self.inner.transcript = self.inner.transcript[:10] + self.inner.transcript[-keep_last:]
