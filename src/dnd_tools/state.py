"""GameState — authoritative simulation state, deterministic transitions."""

from __future__ import annotations

import math

from .dice import roll_dice
from .dice import seed as dice_seed
from .models import Cell, Character


class GameState:
    def __init__(self, seed_val: int = 0, map_w: int = 20, map_h: int = 20):
        self.seed = seed_val
        dice_seed(seed_val)
        self.players: dict[str, Character] = {}
        self.monsters: dict[str, Character] = {}
        self.players_pos: dict[str, tuple[int, int, int]] = {}
        self.monster_pos: dict[str, tuple[int, int, int]] = {}
        self.map: list[list[Cell]] = []
        self.initiative_order: list[str] = []
        self.current_turn_idx: int = 0
        self.round: int = 1
        self.death_log: list[str] = []
        self.tool_trace: list[dict] = []  # auditable trace
        self.transcript: list[str] = []
        self._make_empty_map(map_w, map_h)

    # ------------------------------------------------------------------
    # Map
    # ------------------------------------------------------------------
    def _make_empty_map(self, w: int, h: int):
        self.map = [
            [Cell(x=x, y=y, z=0, valid=True) for x in range(w)] for y in range(h)
        ]

    def set_map(self, cells: list[list[Cell]]):
        self.map = cells

    def map_size(self):
        return len(self.map[0]), len(self.map)

    # ------------------------------------------------------------------
    # Character management
    # ------------------------------------------------------------------
    def add_player(self, char: Character, pos: tuple[int, int, int]):
        self.players[char.name] = char
        self.players_pos[char.name] = pos
        char.pos = pos
        char.is_player = True

    def add_monster(self, char: Character, pos: tuple[int, int, int]):
        self.monsters[char.name] = char
        self.monster_pos[char.name] = pos
        char.pos = pos
        char.is_player = False

    def get_character(self, name: str) -> Character | None:
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

    def set_pos(self, name: str, pos: tuple[int, int, int]):
        if name in self.players_pos:
            self.players_pos[name] = pos
            self.players[name].pos = pos
        elif name in self.monster_pos:
            self.monster_pos[name] = pos
            self.monsters[name].pos = pos

    # ------------------------------------------------------------------
    # Initiative
    # ------------------------------------------------------------------
    def roll_initiative(self):
        entries = []
        for c in list(self.players.values()) + list(self.monsters.values()):
            roll = roll_dice("1d20") + c.ability_mod("dexterity")
            c.initiative = roll
            entries.append((roll, c.name))
        entries.sort(reverse=True)
        self.initiative_order = [n for _, n in entries]
        self.current_turn_idx = 0
        return [{"name": n, "initiative": r} for r, n in entries]

    def current_actor(self) -> str | None:
        if not self.initiative_order:
            return None
        return self.initiative_order[self.current_turn_idx % len(self.initiative_order)]

    def advance_turn(self):
        self.current_turn_idx += 1
        if self.current_turn_idx % len(self.initiative_order) == 0:
            self.round += 1

    # ------------------------------------------------------------------
    # HP / Death
    # ------------------------------------------------------------------
    def update_hp(self, name: str, delta: int) -> dict:
        """delta negative = damage, positive = heal. Honors temp HP."""
        ch = self.get_character(name)
        if not ch:
            raise KeyError(name)
        if delta < 0:
            dmg = -delta
            # temp HP absorbs first
            if ch.temp_hp > 0:
                absorb = min(ch.temp_hp, dmg)
                ch.temp_hp -= absorb
                dmg -= absorb
            ch.hp -= dmg
            if ch.hp <= 0:
                ch.hp = 0
                ch.alive = False
                self.death_log.append(f"{name} dropped to 0 HP (round {self.round})")
                # remove from map positions but keep dict for tracking
                # initiative stays but will be skipped
        else:
            ch.hp = min(ch.max_hp, ch.hp + delta)
        return {
            "name": name,
            "hp": ch.hp,
            "max_hp": ch.max_hp,
            "alive": ch.alive,
            "temp_hp": ch.temp_hp,
        }

    def check_hp(self, name: str) -> int:
        ch = self.get_character(name)
        if not ch:
            raise KeyError(name)
        return ch.hp

    # ------------------------------------------------------------------
    # Distance / LoS
    # ------------------------------------------------------------------
    def distance_feet(self, a: str, b: str) -> float:
        pa = self.get_pos(a)
        pb = self.get_pos(b)
        if pa is None or pb is None:
            raise KeyError(f"position missing for {a} or {b}")
        dx = pa[0] - pb[0]
        dy = pa[1] - pb[1]
        # grid distance: each cell 5ft
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
        max_dim = max(len(self.map), len(self.map[0]))
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def is_alive(self, name: str) -> bool:
        ch = self.get_character(name)
        return ch.alive if ch else False

    def all_player_names(self) -> list[str]:
        return list(self.players.keys())

    def all_monster_names(self) -> list[str]:
        return list(self.monsters.keys())

    def log_tool(self, name: str, args: dict, result):
        self.tool_trace.append(
            {
                "tool": name,
                "args": args,
                "result": result,
                "round": self.round,
                "actor": self.current_actor(),
            }
        )

    def add_transcript(self, line: str):
        self.transcript.append(line)
