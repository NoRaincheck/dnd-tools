"""BladesState (single score) + BladesCampaignState (multi-score).

Reuses dnd_tools mapgen + dice seeding + Cell. Patterns mirror tricube/sword-and-sorcery
but owned for Position & Effect + Stress + Clocks.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dnd_tools.dice import seed as dice_seed
from dnd_tools.models import Cell

from .dice import roll_action
from .models import BladesCharacter, BladesClock, Crew, HarmEntry

# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _harm_to_dict(h: HarmEntry) -> dict[str, Any]:
    return asdict(h)


def _dict_to_harm(d: dict[str, Any]) -> HarmEntry:
    return HarmEntry(**d)


def _char_to_dict(c: BladesCharacter) -> dict[str, Any]:
    d = asdict(c)
    d["pos"] = list(c.pos)
    d["harm"] = [_harm_to_dict(h) for h in c.harm]
    return d


def _dict_to_char(d: dict[str, Any]) -> BladesCharacter:
    d = dict(d)
    d["pos"] = tuple(d.get("pos", (0, 0, 0)))
    d["harm"] = [_dict_to_harm(h) for h in d.get("harm", [])]
    # filter to known fields
    allowed = set(BladesCharacter.__dataclass_fields__.keys())
    filtered = {k: v for k, v in d.items() if k in allowed}
    # private pending fields may be stored as _xxx — ignore if present
    for k in list(filtered.keys()):
        if k.startswith("_"):
            filtered.pop(k)
    return BladesCharacter(**filtered)


def _clock_to_dict(c: BladesClock) -> dict[str, Any]:
    return asdict(c)


def _dict_to_clock(d: dict[str, Any]) -> BladesClock:
    return BladesClock(**d)


def _crew_to_dict(c: Crew) -> dict[str, Any]:
    return asdict(c)


def _dict_to_crew(d: dict[str, Any]) -> Crew:
    return Crew(**d)


def _cell_to_dict(c: Cell) -> dict[str, Any]:
    return asdict(c)


def _dict_to_cell(d: dict[str, Any]) -> Cell:
    return Cell(**d)


# ---------------------------------------------------------------------------
# BladesState — single score
# ---------------------------------------------------------------------------


class BladesState:
    def __init__(self, seed_val: int = 0, map_w: int = 20, map_h: int = 20):
        self.seed = seed_val
        dice_seed(seed_val)
        self.map: list[list[Cell]] = []
        self._make_empty_map(map_w, map_h)
        self.players: dict[str, BladesCharacter] = {}
        self.monsters: dict[str, BladesCharacter] = {}  # opposition as BladesCharacter too (for clocks/heat)
        self.players_pos: dict[str, tuple[int, int, int]] = {}
        self.monster_pos: dict[str, tuple[int, int, int]] = {}
        self.clocks: dict[str, BladesClock] = {}
        self.crew: Crew = Crew()
        self.initiative_order: list[str] = []
        self.current_turn_idx: int = 0
        self.round: int = 1
        # logs
        self.trauma_log: list[str] = []
        self.harm_log: list[str] = []
        self.death_log: list[str] = []  # alias compat
        self.tool_trace: list[dict[str, Any]] = []
        self.transcript: list[str] = []
        # engagement bookkeeping
        self._engagement_position: str | None = None  # controlled/risky/desperate start

    # -- map ---------------------------------------------------------------

    def _make_empty_map(self, w: int, h: int) -> None:
        self.map = [[Cell(x=x, y=y, z=0, valid=True) for x in range(w)] for y in range(h)]

    def set_map(self, cells: list[list[Cell]]) -> None:
        self.map = cells

    def map_size(self) -> tuple[int, int]:
        if not self.map or not self.map[0]:
            return (20, 20)
        return len(self.map[0]), len(self.map)

    # -- character management ----------------------------------------------

    def add_player(self, char: BladesCharacter, pos: tuple[int, int, int]) -> None:
        char.is_player = True
        char.pos = pos
        self.players[char.name] = char
        self.players_pos[char.name] = pos

    def add_monster(self, char: BladesCharacter, pos: tuple[int, int, int]) -> None:
        char.is_player = False
        char.pos = pos
        self.monsters[char.name] = char
        self.monster_pos[char.name] = pos

    def get_character(self, name: str) -> BladesCharacter | None:
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

    # -- clocks ------------------------------------------------------------

    def set_clock(self, name: str, segments: int = 6, kind: str = "obstacle") -> BladesClock:
        if name not in self.clocks:
            self.clocks[name] = BladesClock(name=name, segments=int(segments), kind=kind)
        else:
            # allow overwrite segments/kind if caller specifies
            self.clocks[name].segments = int(segments)
            self.clocks[name].kind = kind
        return self.clocks[name]

    def tick_clock(self, name: str, ticks: int) -> dict[str, Any]:
        clk = self.clocks.get(name)
        if not clk:
            clk = self.set_clock(name)
        before = clk.ticks
        clk.add_ticks(int(ticks))
        return {
            "name": name,
            "before": before,
            "after": clk.ticks,
            "segments": clk.segments,
            "completed": clk.completed,
        }

    def check_clock(self, name: str) -> dict[str, Any] | None:
        clk = self.clocks.get(name)
        if not clk:
            return None
        return {
            "name": clk.name,
            "ticks": clk.ticks,
            "segments": clk.segments,
            "completed": clk.completed,
            "kind": clk.kind,
        }

    # -- stress / trauma ---------------------------------------------------

    def mark_stress(self, name: str, delta: int) -> dict[str, Any]:
        ch = self.get_character(name)
        if not ch:
            raise KeyError(name)
        ch.stress = max(0, min(ch.stress_max, ch.stress + int(delta)))
        # trauma check: overflow exactly when hitting max? SRD: when you *would* mark beyond max, take trauma and clear
        # we model: if mark brings to max and delta>0 and ch.stress==max and trauma not yet handled, callers should call maybe_trauma
        return {"name": name, "stress": ch.stress, "max": ch.stress_max, "trauma": list(ch.trauma)}

    def add_trauma(self, name: str, trauma: str) -> dict[str, Any]:
        ch = self.get_character(name)
        if not ch:
            raise KeyError(name)
        if trauma not in ch.trauma:
            ch.trauma.append(trauma)
            self.trauma_log.append(f"{name} trauma '{trauma}' (round {self.round})")
            self.death_log.append(f"{name} trauma '{trauma}' (round {self.round})")
            ch.stress = 0  # clear on trauma per SRD
        if len(ch.trauma) >= 4:
            ch.alive = False
            self.trauma_log.append(f"{name} retired (4 trauma)")
            self.death_log.append(f"{name} retired (4 trauma)")
        return {"name": name, "trauma": list(ch.trauma), "retired": ch.retired, "stress": ch.stress}

    def check_stress(self, name: str) -> int:
        ch = self.get_character(name)
        if not ch:
            raise KeyError(name)
        return ch.stress

    # -- harm --------------------------------------------------------------

    def apply_harm(self, target: str, level: int, name: str, description: str = "") -> dict[str, Any]:
        ch = self.get_character(target)
        if not ch:
            raise KeyError(target)
        level = int(level)
        if level == 4:
            # fatal — die unless resisted; caller should handle resistance first; we record death
            ch.alive = False
            ch.harm.append(HarmEntry(level=4, name=name, description=description))
            self.harm_log.append(f"{target} fatal harm '{name}' (round {self.round})")
            self.death_log.append(f"{target} fatal harm '{name}' (round {self.round})")
            return {"target": target, "level": 4, "name": name, "alive": False}
        # check if level already filled: SRD says need to record harm at level 3 already filled -> catastrophic -> deathish
        # simplified: if already 2 entries at that level, bump to next level
        count_at_level = sum(1 for h in ch.harm if h.level == level)
        # thresholds: level1 has 2 boxes, level2 2, level3 1? Actually SRD shows varying but we use 2 each for simplicity
        max_boxes = 2 if level in (1, 2, 3) else 1
        effective_level = level
        if count_at_level >= max_boxes:
            # overflow to next level
            effective_level = min(4, level + 1)
            if effective_level == 4:
                ch.alive = False
                ch.harm.append(HarmEntry(level=4, name=name, description=description))
                self.harm_log.append(f"{target} harm overflow to fatal '{name}' (round {self.round})")
                return {"target": target, "level": 4, "name": name, "alive": False, "overflow": True}
        ch.harm.append(HarmEntry(level=effective_level, name=name, description=description))
        self.harm_log.append(f"{target} harm L{effective_level} '{name}' (round {self.round})")
        return {"target": target, "level": effective_level, "name": name, "alive": ch.alive}

    def heal_harm(self, target: str, harm_name: str) -> dict[str, Any]:
        ch = self.get_character(target)
        if not ch:
            raise KeyError(target)
        idx = next((i for i, h in enumerate(ch.harm) if h.name.lower() == harm_name.lower()), None)
        if idx is None:
            return {"valid": False, "reason": f"harm '{harm_name}' not found"}
        removed = ch.harm.pop(idx)
        return {"valid": True, "target": target, "removed": removed.name, "remaining": len(ch.harm)}

    # -- initiative (score order not RAW but needed for simulation) ----------

    def roll_initiative(self) -> list[dict[str, Any]]:
        """Score initiative: roll fortune 1d6 per combatant + Prowess-ish? Simplified: 1d6 + stress urgency."""
        entries: list[tuple[int, str]] = []
        for c in list(self.players.values()) + list(self.monsters.values()):
            r = roll_action(1)  # 1d6 fortune-like
            val = r["highest"] + (1 if c.is_player else 0)
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

    # -- distance / LoS (map reuse) ---------------------------------------

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
# BladesCampaignState — multi-score
# ---------------------------------------------------------------------------


class BladesCampaignState:
    """Long-horizon wrapper around BladesState."""

    def __init__(self, seed_val: int = 0, map_w: int = 20, map_h: int = 20, max_history: int = 100):
        self.inner: BladesState = BladesState(seed_val=seed_val, map_w=map_w, map_h=map_h)
        self.max_history: int = max_history
        self.history: list[dict[str, Any]] = []
        self.campaign_meta: dict[str, Any] = {"seed": seed_val, "scores": 0, "total_rounds": 0, "total_heat": 0}

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

    # -- snapshots ---------------------------------------------------------

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
            "clocks": {k: _clock_to_dict(v) for k, v in self.inner.clocks.items()},
            "crew": _crew_to_dict(self.inner.crew),
            "initiative_order": list(self.inner.initiative_order),
            "current_turn_idx": self.inner.current_turn_idx,
            "round": self.inner.round,
            "trauma_log": list(self.inner.trauma_log),
            "harm_log": list(self.inner.harm_log),
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
        self.inner.clocks = {k: _dict_to_clock(v) for k, v in snap.get("clocks", {}).items()}
        if "crew" in snap:
            self.inner.crew = _dict_to_crew(snap["crew"])
        self.inner.initiative_order = list(snap.get("initiative_order", []))
        self.inner.current_turn_idx = int(snap.get("current_turn_idx", 0))
        self.inner.round = int(snap.get("round", 1))
        self.inner.trauma_log = list(snap.get("trauma_log", []))
        self.inner.harm_log = list(snap.get("harm_log", []))
        self.inner.death_log = list(snap.get("trauma_log", []))
        self.campaign_meta = dict(snap.get("campaign_meta", {}))

    def checkpoint(self) -> None:
        self.history.append(self.snapshot())
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]

    # -- persistence -------------------------------------------------------

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
    def load(cls, path: str | Path) -> BladesCampaignState:
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

    # -- downtime helpers --------------------------------------------------

    def indulge_vice(self, name: str) -> dict[str, Any]:
        ch = self.inner.get_character(name)
        if not ch:
            raise KeyError(name)
        # vice clears stress: roll attr? SRD: indulgence clears = highest die (often Fortune?). Simplified: roll 1d6 per vice? Use fortune 1d6+? Simplified: clear = max(1, ch.stress //2) + random?
        # We'll do deterministic: clear = 2 + (1 if ch.stress>6 else 0) but we expose tool-level fortune for LLM to narrate; state just clears 1d6?
        # For determinism via dice: use roll_action with vice flavor? Simpler: clear 3 stress (bounded)
        # But to keep deterministic and testable we let tools handle dice; campaign state just supports clearing
        return {"name": name, "stress": ch.stress, "note": "use BladesTools.indulge_vice for dice-based clearing"}

    def prune_traces(self, keep_last: int = 200) -> None:
        if len(self.inner.tool_trace) > keep_last:
            self.inner.tool_trace = self.inner.tool_trace[-keep_last:]
        if len(self.inner.transcript) > keep_last:
            self.inner.transcript = self.inner.transcript[:10] + self.inner.transcript[-keep_last:]
