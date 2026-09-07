"""SnSTools — scene tools, and SnSCampaignTools wrapper.

Mirrors dnd_tools.tools pattern: typed API + validation + OpenAI schemas, all
mutations through SnSState/SnSCampaignState and logged to tool_trace.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .dice import roll_sns_check, roll_spell_damage, roll_weapon_damage
from .models import (
    ALL_SPELLS,
    MONSTER_TABLE,
    SPELL_LEVEL,
    SPELL_TABLE,
    SnSCharacter,
    SnSMonster,
    roll_adventure,
)
from .state import SnSCampaignState, SnSState


class SnSTools:
    def __init__(self, state: SnSState):
        self.state = state

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def get_names_of_all_players(self) -> list[str]:
        r = self.state.all_player_names()
        self.state.log_tool("get_names_of_all_players", {}, r)
        return r

    def get_names_of_all_monsters(self) -> list[str]:
        r = self.state.all_monster_names()
        self.state.log_tool("get_names_of_all_monsters", {}, r)
        return r

    def check_character(self, name: str) -> dict[str, Any]:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        if isinstance(ch, SnSCharacter):
            r = {
                "name": ch.name,
                "ancestry": ch.ancestry,
                "background": ch.background,
                "sns": ch.sns,
                "hp": ch.hp,
                "hp_max": ch.hp_max,
                "sp": ch.sp,
                "sp_max": ch.sp_max,
                "wd": ch.wd,
                "en": ch.en,
                "spells_known": list(ch.spells_known),
                "inventory": list(ch.inventory),
                "pos": ch.pos,
                "alive": ch.alive,
                "unconscious": ch.unconscious,
                "is_player": True,
            }
        else:
            r = {
                "name": ch.name,
                "threat": ch.threat,
                "hp": ch.hp,
                "hp_max": ch.hp_max,
                "dmg": ch.dmg,
                "pos": ch.pos,
                "alive": ch.alive,
                "is_player": False,
            }
        self.state.log_tool("check_character", {"name": name}, r)
        return r

    def check_monster(self, name: str) -> dict[str, Any]:
        m = self.state.get_monster(name)
        if not m:
            raise KeyError(name)
        r = {
            "name": m.name,
            "threat": m.threat,
            "hp": m.hp,
            "hp_max": m.hp_max,
            "dmg": m.dmg,
            "pos": m.pos,
            "alive": m.alive,
        }
        self.state.log_tool("check_monster", {"name": name}, r)
        return r

    def check_hp(self, name: str) -> dict[str, Any]:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        r = {"name": name, "hp": ch.hp, "max": ch.hp_max, "alive": ch.alive}
        if isinstance(ch, SnSCharacter):
            r["unconscious"] = ch.unconscious  # type: ignore[attr-defined]
        self.state.log_tool("check_hp", {"name": name}, r)
        return r

    def check_sp(self, name: str) -> dict[str, Any]:
        ch = self.state.get_player(name)
        if not ch:
            raise KeyError(name)
        r = {"name": name, "sp": ch.sp, "max": ch.sp_max}
        self.state.log_tool("check_sp", {"name": name}, r)
        return r

    def check_sns(self, name: str) -> dict[str, Any]:
        ch = self.state.get_player(name)
        if not ch:
            raise KeyError(name)
        r = {"name": name, "sns": ch.sns, "hp_max": ch.hp_max, "sp_max": ch.sp_max, "wd": ch.wd, "en": ch.en}
        self.state.log_tool("check_sns", {"name": name}, r)
        return r

    def check_valid_attack_line(self, attacker_name: str, defender_name: str) -> bool:
        result = self.state.line_of_sight(attacker_name, defender_name)
        self.state.log_tool(
            "check_valid_attack_line", {"attacker_name": attacker_name, "defender_name": defender_name}, result
        )
        return result

    def check_distance(self, a: str, b: str) -> dict[str, Any]:
        d = self.state.distance_feet(a, b)
        r = {"a": a, "b": b, "feet": d}
        self.state.log_tool("check_distance", {"a": a, "b": b}, r)
        return r

    def list_spells(self, level: int | None = None) -> dict[str, Any]:
        if level is None:
            r: dict[str, Any] = {"table": {str(k): v for k, v in SPELL_TABLE.items()}}
        else:
            r = {"level": level, "spells": SPELL_TABLE.get(level, [])}
        self.state.log_tool("list_spells", {"level": level}, r)
        return r

    def list_monster_table(self) -> dict[str, Any]:
        r = {"table": MONSTER_TABLE}
        self.state.log_tool("list_monster_table", {}, r)
        return r

    def generate_adventure(self) -> dict[str, str]:
        adv = roll_adventure()
        self.state.adventure = adv
        self.state.log_tool("generate_adventure", {}, adv)
        return adv

    # ------------------------------------------------------------------
    # Movement
    # ------------------------------------------------------------------
    def move_player(self, name: str, x: int, y: int) -> dict[str, Any]:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        w, h = self.state.map_size()
        if not (0 <= x < w and 0 <= y < h):
            res = {"valid": False, "reason": "out of bounds"}
            self.state.log_tool("move_player", {"name": name, "x": x, "y": y}, res)
            return res
        cell = self.state.map[y][x]
        if not cell.valid:
            res = {"valid": False, "reason": "impassable"}
            self.state.log_tool("move_player", {"name": name, "x": x, "y": y}, res)
            return res
        new_pos = (x, y, cell.z)
        self.state.set_pos(name, new_pos)
        res = {"valid": True, "pos": new_pos}
        self.state.log_tool("move_player", {"name": name, "x": x, "y": y}, res)
        return res

    def move(self, name: str, x: int, y: int) -> dict[str, Any]:
        return self.move_player(name, x, y)

    def visualize_map(self) -> str:
        w, h = self.state.map_size()
        grid = [["." for _ in range(w)] for _ in range(h)]
        for y in range(h):
            for x in range(w):
                if not self.state.map[y][x].valid:
                    grid[y][x] = "#"
        for name, (x, y, _z) in list(self.state.players_pos.items()) + list(self.state.monster_pos.items()):
            if 0 <= x < w and 0 <= y < h:
                grid[y][x] = name[0].upper() if name in self.state.players else name[0].lower()
        out = "\n".join("".join(row) for row in grid)
        self.state.log_tool("visualize_map", {}, out)
        return out

    # ------------------------------------------------------------------
    # Core rolls — Swords & Sorcery mechanic
    # ------------------------------------------------------------------
    def _dice_count(self, prepared: bool, trained: bool, help_bonus: int = 0) -> int:
        base = 1
        if prepared:
            base += 1
        if trained:
            base += 1
        base += help_bonus
        return max(1, min(3, base))

    def roll_check(
        self,
        character: str,
        ability: str,
        prepared: bool = False,
        trained: bool = False,
    ) -> dict[str, Any]:
        """Generic S&S roll: ability = swords|sorcery, +1d prepared, +1d trained, help bonus auto-consumed."""
        ch = self.state.get_player(character)
        if not ch:
            raise KeyError(character)
        ability = ability.lower()
        if ability not in ("swords", "sorcery"):
            raise ValueError("ability must be swords or sorcery")
        help_bonus = self.state._pending_help.pop(character, 0)
        # consume stored _help_bonus on character as well
        if ch._help_bonus:
            help_bonus = max(help_bonus, ch._help_bonus)
            ch._help_bonus = 0
        dice_count = self._dice_count(bool(prepared), bool(trained), help_bonus)
        r = roll_sns_check(ch.sns, ability, dice_count)
        r["character"] = character
        r["ability"] = ability
        r["prepared"] = bool(prepared)
        r["trained"] = bool(trained)
        r["help_bonus"] = help_bonus
        # annotate outcome description
        outcome_desc = {
            "fail": "It goes wrong. GM says how things get worse.",
            "barely": "You barely manage it. GM inflicts complication/harm/cost.",
            "success": "You do it well. Good job!",
            "critical": "Critical success! GM tells you extra effect.",
        }
        r["outcome_desc"] = outcome_desc[r["outcome"]]
        if r["divine_intervention"]:
            r["divine_note"] = (
                "Divine Intervention! Ask GM a question (What are they really feeling? etc.). Roll counts as success; you may change action and roll again."
            )
        self.state.log_tool(
            "roll_check", {"character": character, "ability": ability, "prepared": prepared, "trained": trained}, r
        )
        return r

    def roll_swords(self, character: str, prepared: bool = False, trained: bool = False) -> dict[str, Any]:
        return self.roll_check(character, "swords", prepared, trained)

    def roll_sorcery(self, character: str, prepared: bool = False, trained: bool = False) -> dict[str, Any]:
        return self.roll_check(character, "sorcery", prepared, trained)

    def help(
        self, helper: str, target: str, ability: str, prepared: bool = False, trained: bool = False
    ) -> dict[str, Any]:
        """Helper makes a roll; if they succeed, target gets +1d next roll."""
        helper_ch = self.state.get_player(helper)
        target_ch = self.state.get_player(target)
        if not helper_ch or not target_ch:
            raise KeyError("helper or target not found")
        # helper rolls with their own S&S
        dice_count = self._dice_count(bool(prepared), bool(trained), 0)
        r = roll_sns_check(helper_ch.sns, ability.lower(), dice_count)
        r["helper"] = helper
        r["target"] = target
        r["ability"] = ability
        success = bool(r["success"])
        if success:
            # grant +1d to target's next roll (capped at 3 total)
            existing = self.state._pending_help.get(target, 0)
            self.state._pending_help[target] = min(2, existing + 1)  # +1 bonus
            target_ch._pending_help_from = helper
            r["help_granted"] = True
            r["note"] = f"{target} gets +1d on next roll (help from {helper})"
        else:
            r["help_granted"] = False
            r["note"] = f"{helper} failed to help"
        self.state.log_tool("help", {"helper": helper, "target": target, "ability": ability}, r)
        return r

    def divine_intervention(self, character: str, question: str) -> dict[str, Any]:
        """After rolling exactly S&S, ask GM a question (honest answer). May change action and reroll."""
        # We don't enforce that previous roll was divine; we just log the question for LLM trace
        res = {
            "character": character,
            "question": question,
            "answer": "GM answers honestly (narrative). You may change action and roll again if you wish.",
        }
        self.state.log_tool("divine_intervention", {"character": character, "question": question}, res)
        return res

    # ------------------------------------------------------------------
    # Combat / Magic
    # ------------------------------------------------------------------
    def attack(self, attacker: str, defender: str, prepared: bool = False, trained: bool = False) -> dict[str, Any]:
        """SWORDS attack: roll vs attacker S&S, then WD d6s highest on success. Apply to defender."""
        atk = self.state.get_player(attacker)
        if not atk:
            raise KeyError(attacker)
        def_ch = self.state.get_character(defender)
        if not def_ch:
            raise KeyError(defender)
        # help bonus
        help_bonus = self.state._pending_help.pop(attacker, 0)
        if atk._help_bonus:
            help_bonus = max(help_bonus, atk._help_bonus)
            atk._help_bonus = 0
        dice_count = self._dice_count(bool(prepared), bool(trained), help_bonus)
        roll = roll_sns_check(atk.sns, "swords", dice_count)
        # determine damage only on success
        dmg_info: dict[str, Any] | None = None
        hp_after: dict[str, Any] | None = None
        if roll["success"]:
            dmg_info = roll_weapon_damage(atk.wd)
            dmg = int(dmg_info["damage"])
            # apply to defender: monsters use monster HP, players use player HP
            if defender in self.state.monsters:
                # monster takes damage; handle via update_hp
                hp_after = self.state.update_hp(defender, -dmg)
            elif defender in self.state.players:
                hp_after = self.state.update_hp(defender, -dmg)
            else:
                hp_after = {"note": "defender not found in state"}
        else:
            dmg_info = {"wd": atk.wd, "rolls": [], "damage": 0}
            # on fail, GM worsens — but we don't auto-damage attacker; caller handles complication
        result = {
            "attacker": attacker,
            "defender": defender,
            "roll": roll,
            "prepared": bool(prepared),
            "trained": bool(trained),
            "help_bonus": help_bonus,
            "damage": dmg_info,
            "defender_hp": hp_after,
        }
        self.state.log_tool(
            "attack", {"attacker": attacker, "defender": defender, "prepared": prepared, "trained": trained}, result
        )
        return result

    def cast_spell(
        self,
        caster: str,
        spell: str,
        level: int | None = None,
        prepared: bool = False,
        trained: bool = False,
        targets: list[str] | None = None,
    ) -> dict[str, Any]:
        """Cast spell: level 0 auto, level>=1 requires SORCERY roll; fail = backlash; success costs SP and deals heal/damage."""
        ch = self.state.get_player(caster)
        if not ch:
            raise KeyError(caster)
        # normalize spell name
        spell_key = spell.lower()
        if level is None:
            level = SPELL_LEVEL.get(spell_key)
            if level is None:
                raise ValueError(f"unknown spell '{spell}' (known: {ALL_SPELLS})")
        if spell not in ch.spells_known and spell_key not in [s.lower() for s in ch.spells_known]:
            # allow casting even if not known? In S&S you know = max SP; enforce but allow fallback
            pass
        if level == 0:
            # no roll, no SP
            dmg_info = None
            # level 0 spells are narrative; we just log
            result = {
                "caster": caster,
                "spell": spell,
                "level": 0,
                "roll": None,
                "sp_cost": 0,
                "sp_after": ch.sp,
                "note": "Level-0: no roll, no SP cost. Continuous effects last one minute.",
                "damage": dmg_info,
            }
            self.state.log_tool("cast_spell", {"caster": caster, "spell": spell, "level": 0}, result)
            return result
        # level >=1: need SORCERY roll
        help_bonus = self.state._pending_help.pop(caster, 0)
        if ch._help_bonus:
            help_bonus = max(help_bonus, ch._help_bonus)
            ch._help_bonus = 0
        dice_count = self._dice_count(bool(prepared), bool(trained), help_bonus)
        roll = roll_sns_check(ch.sns, "sorcery", dice_count)
        if not roll["success"]:
            # fail: bad magical consequence, no SP cost? In S&S SP cost on success only
            result = {
                "caster": caster,
                "spell": spell,
                "level": level,
                "roll": roll,
                "sp_cost": 0,
                "sp_after": ch.sp,
                "success": False,
                "note": "Spell failed — something bad and magical happens (GM narrates). No SP spent.",
                "help_bonus": help_bonus,
            }
            self.state.log_tool("cast_spell", {"caster": caster, "spell": spell, "level": level}, result)
            return result
        # success: cost SP
        if ch.sp < level:
            result = {
                "caster": caster,
                "spell": spell,
                "level": level,
                "roll": roll,
                "success": False,
                "error": f"not enough SP: {ch.sp} < {level}",
            }
            self.state.log_tool("cast_spell", {"caster": caster, "spell": spell, "level": level}, result)
            return result
        ch.sp -= level
        # damage/heal roll if spell deals it (we model all level>=1 as potential dmg/heal; caller splits)
        dmg_info = roll_spell_damage(level)
        # split across targets if provided — we don't auto-apply; return info and apply to first target for convenience
        target_hps: dict[str, Any] = {}
        if targets:
            # split total evenly? For now apply total to each if DM wants to split manually they can call update_hp; we apply to first only as example
            # Better: divide total roughly: we give total, let GM split narrative
            for t in targets[:3]:
                # heal vs damage heuristic: Heal heals, others damage
                ch_t = self.state.get_character(t)
                if not ch_t:
                    continue
                if spell_key in ("heal", "mend"):
                    self.state.update_hp(t, int(dmg_info["total"]))
                    target_hps[t] = ch_t.hp
                elif t in self.state.monsters or t in self.state.players:
                    self.state.update_hp(t, -int(dmg_info["total"]))
                    target_hps[t] = ch_t.hp
        result = {
            "caster": caster,
            "spell": spell,
            "level": level,
            "roll": roll,
            "sp_cost": level,
            "sp_after": ch.sp,
            "success": True,
            "damage": dmg_info,
            "targets": targets,
            "target_hps": target_hps,
            "note": "Success — SP spent. Damage/heal = highest d6 + 2*level (can split between close targets). Continuous 1 minute.",
            "help_bonus": help_bonus,
        }
        self.state.log_tool(
            "cast_spell", {"caster": caster, "spell": spell, "level": level, "targets": targets}, result
        )
        return result

    def heal_spell(self, caster: str, target: str, level: int = 2) -> dict[str, Any]:
        return self.cast_spell(caster, "Heal", level=level, targets=[target])

    # ------------------------------------------------------------------
    # Resource / bookkeeping
    # ------------------------------------------------------------------
    def update_hp(self, name: str, delta: int) -> dict[str, Any]:
        res = self.state.update_hp(name, delta)
        self.state.log_tool("update_hp", {"name": name, "delta": delta}, res)
        return res

    def update_sp(self, name: str, delta: int) -> dict[str, Any]:
        res = self.state.update_sp(name, delta)
        self.state.log_tool("update_sp", {"name": name, "delta": delta}, res)
        return res

    def night_rest(self, names: list[str] | None = None) -> dict[str, Any]:
        res = self.state.night_rest(names)
        self.state.log_tool("night_rest", {"names": names}, res)
        return res

    def roll_initiative(self) -> list[dict[str, Any]]:
        res = self.state.roll_initiative()
        self.state.log_tool("roll_initiative", {}, res)
        return res

    def end_turn(self, character: str) -> dict[str, Any]:
        # clear help bonus if not used? Keep until next roll; already consumed in roll
        res = {"character": character, "note": "end of turn"}
        self.state.log_tool("end_turn", {"character": character}, res)
        return res

    def print_death_log(self) -> dict[str, Any]:
        res = {"log": list(self.state.death_log)}
        self.state.log_tool("print_death_log", {}, res)
        return res

    # alias compat
    def print_affliction_log(self) -> dict[str, Any]:
        return self.print_death_log()

    # ------------------------------------------------------------------
    # Monster helpers (GM)
    # ------------------------------------------------------------------
    def set_monster(self, name: str, threat: str, hp: int | None = None, dmg: int | None = None) -> dict[str, Any]:
        """GM: declare monster with threat tier (auto HP/DMG) or explicit override."""
        if threat not in MONSTER_TABLE:
            raise ValueError(f"threat must be {list(MONSTER_TABLE)}")
        base = MONSTER_TABLE[threat]
        mon = SnSMonster(name=name, threat=threat, hp=hp or base["HP"], hp_max=hp or base["HP"], dmg=dmg or base["DMG"])  # type: ignore[arg-type]
        # position will be set by scene init; if already exists update
        if name in self.state.monsters:
            self.state.monsters[name].threat = threat
            self.state.monsters[name].hp = mon.hp
            self.state.monsters[name].hp_max = mon.hp_max
            self.state.monsters[name].dmg = mon.dmg
        res = {"name": name, "threat": threat, "hp": mon.hp, "dmg": mon.dmg}
        self.state.log_tool("set_monster", {"name": name, "threat": threat}, res)
        return res

    # ------------------------------------------------------------------
    # Schemas for tau
    # ------------------------------------------------------------------
    def tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_names_of_all_players",
                    "description": "List player names",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_names_of_all_monsters",
                    "description": "List monster names",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_character",
                    "description": "Get S&S sheet: sns/hp/sp/wd/en/spells/pos/alive",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_monster",
                    "description": "Get monster HP/DMG/threat",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_hp",
                    "description": "Get HP",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_sp",
                    "description": "Get SP",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_sns",
                    "description": "Get S&S number and derived HP/SP/WD/EN",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_valid_attack_line",
                    "description": "LoS between attacker and defender",
                    "parameters": {
                        "type": "object",
                        "properties": {"attacker_name": {"type": "string"}, "defender_name": {"type": "string"}},
                        "required": ["attacker_name", "defender_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_distance",
                    "description": "Distance in feet",
                    "parameters": {
                        "type": "object",
                        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
                        "required": ["a", "b"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_spells",
                    "description": "List spells by level (0-3)",
                    "parameters": {"type": "object", "properties": {"level": {"type": "integer"}}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_monster_table",
                    "description": "Monster threat→HP/DMG table",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_adventure",
                    "description": "Roll patron/quest/location/threat (d6 each)",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "move_player",
                    "description": "Move to x,y (grid, 5ft per cell)",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"}},
                        "required": ["name", "x", "y"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "move",
                    "description": "Alias for move_player",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"}},
                        "required": ["name", "x", "y"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "visualize_map",
                    "description": "ASCII map",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "roll_check",
                    "description": "S&S roll: ability swords(<sns) or sorcery(>sns), prepared+trained add dice, help bonus auto. Returns successes/divine/outcome.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "ability": {"type": "string", "enum": ["swords", "sorcery"]},
                            "prepared": {"type": "boolean"},
                            "trained": {"type": "boolean"},
                        },
                        "required": ["character", "ability"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "roll_swords",
                    "description": "Alias: roll SWORDS (< sns)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "prepared": {"type": "boolean"},
                            "trained": {"type": "boolean"},
                        },
                        "required": ["character"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "roll_sorcery",
                    "description": "Alias: roll SORCERY (> sns)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "prepared": {"type": "boolean"},
                            "trained": {"type": "boolean"},
                        },
                        "required": ["character"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "help",
                    "description": "Helper makes a roll to grant target +1d next roll (if helper succeeds)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "helper": {"type": "string"},
                            "target": {"type": "string"},
                            "ability": {"type": "string", "enum": ["swords", "sorcery"]},
                            "prepared": {"type": "boolean"},
                            "trained": {"type": "boolean"},
                        },
                        "required": ["helper", "target", "ability"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "divine_intervention",
                    "description": "After rolling exactly S&S: ask GM an honest question; you may change action and reroll",
                    "parameters": {
                        "type": "object",
                        "properties": {"character": {"type": "string"}, "question": {"type": "string"}},
                        "required": ["character", "question"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "attack",
                    "description": "SWORDS attack: roll < sns then WD d6s highest damage to defender",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "attacker": {"type": "string"},
                            "defender": {"type": "string"},
                            "prepared": {"type": "boolean"},
                            "trained": {"type": "boolean"},
                        },
                        "required": ["attacker", "defender"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "cast_spell",
                    "description": "Cast spell: level 0 auto (no roll/SP), level>=1 SORCERY roll fail=backlash success=SP cost level and damage highest+2*level",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "caster": {"type": "string"},
                            "spell": {"type": "string"},
                            "level": {"type": "integer"},
                            "prepared": {"type": "boolean"},
                            "trained": {"type": "boolean"},
                            "targets": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["caster", "spell"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "heal_spell",
                    "description": "Shortcut: Heal level 2 on target",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "caster": {"type": "string"},
                            "target": {"type": "string"},
                            "level": {"type": "integer"},
                        },
                        "required": ["caster", "target"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "update_hp",
                    "description": "Update HP by delta (negative damage)",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}, "delta": {"type": "integer"}},
                        "required": ["name", "delta"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "update_sp",
                    "description": "Update SP by delta",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}, "delta": {"type": "integer"}},
                        "required": ["name", "delta"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "night_rest",
                    "description": "Night's rest: restore all HP and SP",
                    "parameters": {
                        "type": "object",
                        "properties": {"names": {"type": "array", "items": {"type": "string"}}},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "roll_initiative",
                    "description": "Roll 1d6 initiative for all",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "end_turn",
                    "description": "End turn bookkeeping",
                    "parameters": {
                        "type": "object",
                        "properties": {"character": {"type": "string"}},
                        "required": ["character"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "print_death_log",
                    "description": "Print death/unconscious log",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "set_monster",
                    "description": "GM: set monster threat/HP/DMG",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "threat": {"type": "string", "enum": ["Easy", "Medium", "Hard", "Deadly"]},
                            "hp": {"type": "integer"},
                            "dmg": {"type": "integer"},
                        },
                        "required": ["name", "threat"],
                    },
                },
            },
        ]

    def dispatch(self, name: str, args: dict[str, Any]) -> Any:
        fn = getattr(self, name, None)
        if not fn:
            raise ValueError(f"Unknown tool {name}")
        return fn(**args)


# ---------------------------------------------------------------------------
# Campaign wrapper
# ---------------------------------------------------------------------------


class SnSCampaignTools:
    def __init__(self, cstate: SnSCampaignState):
        self.cstate = cstate
        self.inner_tools = SnSTools(cstate.inner)

    def __getattr__(self, name: str) -> Any:
        if hasattr(self.inner_tools, name):
            return getattr(self.inner_tools, name)
        raise AttributeError(name)

    def dispatch(self, name: str, args: dict[str, Any]) -> Any:
        if hasattr(self, name) and name in {
            "long_rest",
            "short_rest",
            "checkpoint",
            "save_checkpoint",
            "load_checkpoint",
            "get_summary",
            "prune_traces",
        }:
            fn = getattr(self, name)
            return fn(**args)
        return self.inner_tools.dispatch(name, args)

    def long_rest(self, name: str | None = None) -> dict[str, Any]:  # type: ignore[override]
        res = self.cstate.long_rest(name)
        self.cstate.inner.log_tool("long_rest", {"name": name}, res)
        self.cstate.checkpoint()
        return res

    def short_rest(self, name: str) -> dict[str, Any]:
        # S&S has night rest only; short rest is no-op but for compat
        res = {"name": name, "note": "S&S has only night rest (full restore); short rest is narrative."}
        self.cstate.inner.log_tool("short_rest", {"name": name}, res)
        return res

    def checkpoint(self) -> dict[str, Any]:
        self.cstate.checkpoint()
        res: dict[str, Any] = {"history_len": len(self.cstate.history)}
        self.cstate.inner.log_tool("checkpoint", {}, res)
        return res

    def save_checkpoint(self, path: str) -> dict[str, Any]:
        p = self.cstate.save(path)
        res = {"path": str(p)}
        self.cstate.inner.log_tool("save_checkpoint", {"path": path}, res)
        return res

    def load_checkpoint(self, path: str) -> dict[str, Any]:
        loaded = SnSCampaignState.load(path)
        self.cstate.restore(loaded.snapshot())
        self.cstate.inner.tool_trace = loaded.inner.tool_trace
        self.cstate.inner.transcript = loaded.inner.transcript
        res = {"path": path, "round": self.cstate.inner.round}
        self.cstate.inner.log_tool("load_checkpoint", {"path": path}, res)
        return res

    def get_summary(self) -> dict[str, Any]:
        from .memory import summarize_state

        s = summarize_state(self.cstate)
        self.cstate.inner.log_tool("get_summary", {}, s)
        return s

    def prune_traces(self, keep_last: int = 200) -> dict[str, Any]:
        self.cstate.prune_traces(keep_last=keep_last)
        res = {"tool_trace_len": len(self.cstate.inner.tool_trace)}
        self.cstate.inner.log_tool("prune_traces", {"keep_last": keep_last}, res)
        return res

    def tool_schemas(self) -> list[dict[str, Any]]:
        base = self.inner_tools.tool_schemas()
        extra: list[dict[str, Any]] = [
            {
                "type": "function",
                "function": {
                    "name": "long_rest",
                    "description": "Night rest: restore all HP/SP (all or one)",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "short_rest",
                    "description": "Short rest (narrative, S&S only has night rest)",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "checkpoint",
                    "description": "Snapshot to bounded history",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "save_checkpoint",
                    "description": "Persist snapshot to file",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_summary",
                    "description": "Compact campaign summary for LLM",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "prune_traces",
                    "description": "Prune traces to last N",
                    "parameters": {"type": "object", "properties": {"keep_last": {"type": "integer"}}, "required": []},
                },
            },
        ]
        _ = Path
        return base + extra
