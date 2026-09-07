"""SnSState (scene) + SnSCampaignState (long-horizon).

Reuses dnd_tools mapgen + dice seeding + Cell, owns SnS characters/monsters.
Mirrors tricube state patterns: bounded history, snapshot/restore, prune.

Map: 20x20 default, each cell 5ft for distance, z for LoS (imported logic).
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dnd_campaign.state import CampaignState as DndCampaignState  # pattern reuse
from dnd_tools.dice import seed as dice_seed
from dnd_tools.models import Cell

from .models import SnSCharacter, SnSMonster

_ = DndCampaignState


def _char_to_dict(c: SnSCharacter) -> dict[str, Any]:
    d = asdict(c)
    d["pos"] = list(c.pos)
    return d


def _dict_to_char(d: dict[str, Any]) -> SnSCharacter:
    d = dict(d)
    d["pos"] = tuple(d.get("pos", (0, 0, 0)))
    # filter unknown keys defensively
    allowed = set(SnSCharacter.__dataclass_fields__.keys())
    return SnSCharacter(**{k: v for k, v in d.items() if k in allowed})


def _mon_to_dict(m: SnSMonster) -> dict[str, Any]:
    d = asdict(m)
    d["pos"] = list(m.pos)
    return d


def _dict_to_mon(d: dict[str, Any]) -> SnSMonster:
    d = dict(d)
    d["pos"] = tuple(d.get("pos", (0, 0, 0)))
    allowed = set(SnSMonster.__dataclass_fields__.keys())
    return SnSMonster(**{k: v for k, v in d.items() if k in allowed})


def _cell_to_dict(c: Cell) -> dict[str, Any]:
    return asdict(c)


def _dict_to_cell(d: dict[str, Any]) -> Cell:
    return Cell(**d)


# ---------------------------------------------------------------------------
# SnSState — single scene
# ---------------------------------------------------------------------------


class SnSState:
    def __init__(self, seed_val: int = 0, map_w: int = 20, map_h: int = 20):
        self.seed = seed_val
        dice_seed(seed_val)
        self.map: list[list[Cell]] = []
        self._make_empty_map(map_w, map_h)
        self.players: dict[str, SnSCharacter] = {}
        self.monsters: dict[str, SnSMonster] = {}
        self.players_pos: dict[str, tuple[int, int, int]] = {}
        self.monster_pos: dict[str, tuple[int, int, int]] = {}
        # Turn order — RAW S&S has no initiative. This is just a sensible
        # conversation order (players in declaration order, then threats as
        # GM-framed hazards). Kept as initiative_order for compat.
        self.initiative_order: list[str] = []
        self.turn_order: list[str] = []  # alias for initiative_order
        self.current_turn_idx: int = 0
        self.round: int = 1
        self.death_log: list[str] = []
        self.tool_trace: list[dict[str, Any]] = []
        self.transcript: list[str] = []
        # pending help: target -> bonus dice count
        self._pending_help: dict[str, int] = {}
        # adventure hook for this scene
        self.adventure: dict[str, str] = {}

    def _make_empty_map(self, w: int, h: int) -> None:
        self.map = [[Cell(x=x, y=y, z=0, valid=True) for x in range(w)] for y in range(h)]

    def set_map(self, cells: list[list[Cell]]) -> None:
        self.map = cells

    def map_size(self) -> tuple[int, int]:
        return len(self.map[0]), len(self.map)

    # -- character management ----------------------------------------------

    def add_player(self, char: SnSCharacter, pos: tuple[int, int, int]) -> None:
        char.is_player = True
        char.pos = pos
        self.players[char.name] = char
        self.players_pos[char.name] = pos

    def add_monster(self, mon: SnSMonster, pos: tuple[int, int, int]) -> None:
        mon.is_player = False
        mon.pos = pos
        self.monsters[mon.name] = mon
        self.monster_pos[mon.name] = pos

    def get_character(self, name: str) -> SnSCharacter | SnSMonster | None:
        if name in self.players:
            return self.players[name]
        if name in self.monsters:
            return self.monsters[name]
        return None

    def get_player(self, name: str) -> SnSCharacter | None:
        return self.players.get(name)

    def get_monster(self, name: str) -> SnSMonster | None:
        return self.monsters.get(name)

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
        return bool(ch and ch.alive)  # type: ignore[union-attr]

    # -- turn order (RAW: no initiative) ----------------------------------

    def roll_initiative(self) -> list[dict[str, Any]]:
        """Deprecated alias for establish_turn_order(). No dice — RAW has no initiative."""
        return self.establish_turn_order()

    def establish_turn_order(self) -> list[dict[str, Any]]:
        """Sensible conversation order: players in declaration order, then threats.

        S&S RAW (ref/sword-and-sorcery.md:120) has no initiative; the GM resolves
        in sensible order and only players roll. We keep a deterministic order for
        simulation bookkeeping without any 1d6.
        """
        order = list(self.players.keys()) + list(self.monsters.keys())
        self.initiative_order = order
        self.turn_order = order
        self.current_turn_idx = 0
        # Return dicts without initiative numbers for RAW fidelity; keep 'order' index
        return [{"name": n, "order": i} for i, n in enumerate(order)]

    def current_actor(self) -> str | None:
        order = self.turn_order or self.initiative_order
        if not order:
            return None
        return order[self.current_turn_idx % len(order)]

    def advance_turn(self) -> None:
        order = self.turn_order or self.initiative_order
        self.current_turn_idx += 1
        if order and self.current_turn_idx % len(order) == 0:
            self.round += 1

    # -- HP / SP ------------------------------------------------------------

    def update_hp(self, name: str, delta: int) -> dict[str, Any]:
        """delta negative = damage, positive = heal. 0 HP → unconscious with one save chance."""
        # try player first, then monster
        if name in self.players:
            ch = self.players[name]
            if delta < 0:
                ch.hp = max(0, ch.hp + delta)
                if ch.hp == 0 and not ch.unconscious:
                    ch.unconscious = True
                    msg = f"{name} knocked unconscious (0 HP) — one chance to save before death (round {self.round})"
                    self.death_log.append(msg)
                elif ch.hp == 0 and ch.unconscious:
                    # second time at 0 → death if not saved
                    ch.alive = False
                    ch.unconscious = False
                    msg = f"{name} has died (failed save at 0 HP)"
                    self.death_log.append(msg)
            else:
                ch.hp = min(ch.hp_max, ch.hp + delta)
                if ch.hp > 0:
                    ch.unconscious = False
            return {"name": name, "hp": ch.hp, "max": ch.hp_max, "alive": ch.alive, "unconscious": ch.unconscious}
        if name in self.monsters:
            m = self.monsters[name]
            if delta < 0:
                m.hp = max(0, m.hp + delta)
                if m.hp == 0:
                    m.alive = False
                    msg = f"{name} defeated (0 HP)"
                    self.death_log.append(msg)
            else:
                m.hp = min(m.hp_max, m.hp + delta)
            return {"name": name, "hp": m.hp, "max": m.hp_max, "alive": m.alive}
        raise KeyError(name)

    def update_sp(self, name: str, delta: int) -> dict[str, Any]:
        ch = self.players.get(name)
        if not ch:
            raise KeyError(name)
        if delta < 0:
            if ch.sp + delta < 0:
                raise ValueError(f"not enough SP: {ch.sp} < {-delta}")
            ch.sp += delta
        else:
            ch.sp = min(ch.sp_max, ch.sp + delta)
        return {"name": name, "sp": ch.sp, "max": ch.sp_max}

    def night_rest(self, names: list[str] | None = None) -> dict[str, Any]:
        targets = [self.players[n] for n in (names or list(self.players.keys())) if n in self.players]
        out: dict[str, Any] = {}
        for ch in targets:
            ch.hp = ch.hp_max
            ch.sp = ch.sp_max
            ch.unconscious = False
            if not ch.alive:
                # rest doesn't resurrect, but mark
                pass
            out[ch.name] = {"hp": ch.hp, "sp": ch.sp}
        return out

    # -- distance / LoS -----------------------------------------------------

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

    # -- logging ------------------------------------------------------------

    def log_tool(self, name: str, args: dict[str, Any], result: Any) -> None:
        self.tool_trace.append(
            {"tool": name, "args": args, "result": result, "round": self.round, "actor": self.current_actor()}
        )

    def add_transcript(self, line: str) -> None:
        self.transcript.append(line)


# ---------------------------------------------------------------------------
# SnSCampaignState — multi-scene with bounded history
# ---------------------------------------------------------------------------


class SnSCampaignState:
    def __init__(self, seed_val: int = 0, map_w: int = 20, map_h: int = 20, max_history: int = 100):
        self.inner: SnSState = SnSState(seed_val=seed_val, map_w=map_w, map_h=map_h)
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

    def snapshot(self) -> dict[str, Any]:
        w, h = self.inner.map_size()
        return {
            "seed": self.inner.seed,
            "map": [[_cell_to_dict(c) for c in row] for row in self.inner.map],
            "map_w": w,
            "map_h": h,
            "players": {k: _char_to_dict(v) for k, v in self.inner.players.items()},
            "monsters": {k: _mon_to_dict(v) for k, v in self.inner.monsters.items()},
            "players_pos": {k: list(v) for k, v in self.inner.players_pos.items()},
            "monster_pos": {k: list(v) for k, v in self.inner.monster_pos.items()},
            "initiative_order": list(self.inner.initiative_order),
            "turn_order": list(self.inner.turn_order),
            "current_turn_idx": self.inner.current_turn_idx,
            "round": self.inner.round,
            "death_log": list(self.inner.death_log),
            "adventure": dict(self.inner.adventure),
            "campaign_meta": dict(self.campaign_meta),
        }

    def restore(self, snap: dict[str, Any]) -> None:
        dice_seed(snap.get("seed", 0))
        self.inner.seed = snap.get("seed", 0)
        self.inner.map = [[_dict_to_cell(c) for c in row] for row in snap.get("map", [])]
        self.inner.players = {k: _dict_to_char(v) for k, v in snap.get("players", {}).items()}
        self.inner.monsters = {k: _dict_to_mon(v) for k, v in snap.get("monsters", {}).items()}
        self.inner.players_pos = {k: tuple(v) for k, v in snap.get("players_pos", {}).items()}
        self.inner.monster_pos = {k: tuple(v) for k, v in snap.get("monster_pos", {}).items()}
        for k, pos in self.inner.players_pos.items():
            if k in self.inner.players:
                self.inner.players[k].pos = pos
        for k, pos in self.inner.monster_pos.items():
            if k in self.inner.monsters:
                self.inner.monsters[k].pos = pos
        # compat: old saves stored initiative with dice values; new saves store turn_order
        order = snap.get("turn_order", snap.get("initiative_order", []))
        self.inner.initiative_order = list(order)
        self.inner.turn_order = list(order)
        self.inner.current_turn_idx = int(snap.get("current_turn_idx", 0))
        self.inner.round = int(snap.get("round", 1))
        self.inner.death_log = list(snap.get("death_log", []))
        self.inner.adventure = dict(snap.get("adventure", {}))
        self.campaign_meta = dict(snap.get("campaign_meta", {}))

    def checkpoint(self) -> None:
        self.history.append(self.snapshot())
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]

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
    def load(cls, path: str | Path) -> SnSCampaignState:
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

    def long_rest(self, name: str | None = None) -> dict[str, Any]:
        if name is not None:
            res = self.inner.night_rest([name])
        else:
            res = self.inner.night_rest()
        self.campaign_meta["total_rounds"] += self.inner.round
        return res

    def prune_traces(self, keep_last: int = 200) -> None:
        if len(self.inner.tool_trace) > keep_last:
            self.inner.tool_trace = self.inner.tool_trace[-keep_last:]
        if len(self.inner.transcript) > keep_last:
            self.inner.transcript = self.inner.transcript[:10] + self.inner.transcript[-keep_last:]
