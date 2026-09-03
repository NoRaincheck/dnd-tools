"""CampaignState — long-horizon wrapper around dnd_tools.state.GameState.

Does NOT modify GameState. Holds an inner GameState as source of truth and adds:
- bounded snapshot history (for rewind / persistence)
- long/short rest helpers (beyond per-turn reset_resources)
- transcript/tool_trace pruning for LLM context limits
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dnd_tools.models import Buff, Cell, Character
from dnd_tools.state import GameState


def _char_to_dict(c: Character) -> dict[str, Any]:
    d = asdict(c)
    # tuple pos is json-safe as list; keep as list for dump
    d["pos"] = list(c.pos)
    return d


def _dict_to_char(d: dict[str, Any]) -> Character:
    # reconstruct Buff/ResistEntry inside asdict nesting
    d = dict(d)
    d["pos"] = tuple(d.get("pos", (0, 0, 0)))
    # buffs/resists are dataclasses — asdict already expanded to dicts, need rebuild
    buffs = []
    for b in d.get("buffs", []):
        buffs.append(Buff(**b))
    d["buffs"] = buffs
    # ResistEntry
    from dnd_tools.models import ResistEntry

    resists = []
    for r in d.get("resists", []):
        resists.append(ResistEntry(**r))
    d["resists"] = resists
    return Character(**d)


def _cell_to_dict(c: Cell) -> dict[str, Any]:
    return asdict(c)


def _dict_to_cell(d: dict[str, Any]) -> Cell:
    return Cell(**d)


class CampaignState:
    """Long-horizon state. Wraps GameState; paper code in src/dnd_tools/* is untouched."""

    def __init__(self, seed_val: int = 0, map_w: int = 20, map_h: int = 20, max_history: int = 100):
        self.inner: GameState = GameState(seed_val=seed_val, map_w=map_w, map_h=map_h)
        self.max_history: int = max_history
        self.history: list[dict[str, Any]] = []
        self.campaign_meta: dict[str, Any] = {"seed": seed_val, "encounters": 0}

    # -- delegation helpers -------------------------------------------------
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

    # -- snapshots ----------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        """Capture full deterministic state as json-serializable dict."""
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
            "initiative_order": list(self.inner.initiative_order),
            "current_turn_idx": self.inner.current_turn_idx,
            "round": self.inner.round,
            "death_log": list(self.inner.death_log),
            "campaign_meta": dict(self.campaign_meta),
        }

    def restore(self, snap: dict[str, Any]) -> None:
        """Restore inner GameState from snapshot (deterministic)."""
        from dnd_tools.dice import seed as dice_seed

        dice_seed(snap.get("seed", 0))
        self.inner.seed = snap.get("seed", 0)
        self.inner.map = [[_dict_to_cell(c) for c in row] for row in snap.get("map", [])]
        # rebuild characters
        self.inner.players = {k: _dict_to_char(v) for k, v in snap.get("players", {}).items()}
        self.inner.monsters = {k: _dict_to_char(v) for k, v in snap.get("monsters", {}).items()}
        self.inner.players_pos = {k: tuple(v) for k, v in snap.get("players_pos", {}).items()}
        self.inner.monster_pos = {k: tuple(v) for k, v in snap.get("monster_pos", {}).items()}
        # keep Character.pos in sync
        for k, pos in self.inner.players_pos.items():
            if k in self.inner.players:
                self.inner.players[k].pos = pos
        for k, pos in self.inner.monster_pos.items():
            if k in self.inner.monsters:
                self.inner.monsters[k].pos = pos
        self.inner.initiative_order = list(snap.get("initiative_order", []))
        self.inner.current_turn_idx = int(snap.get("current_turn_idx", 0))
        self.inner.round = int(snap.get("round", 1))
        self.inner.death_log = list(snap.get("death_log", []))
        self.campaign_meta = dict(snap.get("campaign_meta", {}))

    def checkpoint(self) -> None:
        """Append snapshot to bounded history."""
        self.history.append(self.snapshot())
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]

    # -- persistence --------------------------------------------------------
    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "snapshot": self.snapshot(),
            "tool_trace": self.inner.tool_trace[-500:],  # bounded for file size
            "transcript_tail": self.inner.transcript[-200:],
        }
        p.write_text(json.dumps(payload, indent=2))
        return p

    @classmethod
    def load(cls, path: str | Path) -> CampaignState:
        p = Path(path)
        data = json.loads(p.read_text())
        snap = data.get("snapshot", data)
        cs = cls(seed_val=snap.get("seed", 0))
        cs.restore(snap)
        # restore traces if present
        if "tool_trace" in data:
            cs.inner.tool_trace = list(data["tool_trace"])
        if "transcript_tail" in data:
            cs.inner.transcript = list(data["transcript_tail"])
        return cs

    # -- long-horizon helpers -----------------------------------------------
    def short_rest(self, name: str) -> dict[str, Any]:
        """Short rest: reset speed/resources, keep HP/slots. Returns summary."""
        ch = self.inner.get_character(name)
        if not ch:
            raise KeyError(name)
        ch.speed_remaining = ch.speed
        ch.num_of_action = 1
        ch.num_of_bonus_action = 1
        ch.num_of_reaction = 1
        return {"name": name, "hp": ch.hp, "speed": ch.speed_remaining}

    def long_rest(self, name: str | None = None) -> dict[str, Any]:
        """Long rest: full heal, restore slots, clear temp buffs/resists, reset economy.

        If name is None, applies to all players. Monsters are not rested.
        """
        targets: list[Character] = []
        if name is not None:
            ch = self.inner.get_character(name)
            if not ch:
                raise KeyError(name)
            targets = [ch]
        else:
            targets = list(self.inner.players.values())
        out: dict[str, Any] = {}
        for ch in targets:
            ch.hp = ch.max_hp
            ch.temp_hp = 0
            ch.alive = True
            ch.speed_remaining = ch.speed
            ch.num_of_action = 1
            ch.num_of_bonus_action = 1
            ch.num_of_reaction = 1
            ch.spell_slots = dict(ch.spell_slots_max)
            # clear non-permanent buffs/resists (-1 = permanent)
            ch.buffs = [b for b in ch.buffs if b.remaining_turns == -1]
            ch.resists = [r for r in ch.resists if r.remaining_turns == -1]
            ch.concentration = None
            ch.concentration_turns = 0
            out[ch.name] = {"hp": ch.hp, "slots": dict(ch.spell_slots)}
        self.campaign_meta["encounters"] = 0
        return out

    def prune_traces(self, keep_last: int = 200) -> None:
        """Bound tool_trace/transcript to keep LLM context manageable."""
        if len(self.inner.tool_trace) > keep_last:
            self.inner.tool_trace = self.inner.tool_trace[-keep_last:]
        if len(self.inner.transcript) > keep_last:
            # keep first 10 (init) + last N
            self.inner.transcript = self.inner.transcript[:10] + self.inner.transcript[-keep_last:]
