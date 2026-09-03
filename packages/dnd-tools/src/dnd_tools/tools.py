"""Typed tool API — grounded, validated function calls."""

from __future__ import annotations

from typing import Any

from .dice import roll_dice
from .models import ALL_WEAPONS, MELEE_SET, RANGED_SET
from .state import GameState


# small helpers
def _weapon_for(name: str):
    return ALL_WEAPONS.get(name.lower())


def _is_melee_weapon(w: str) -> bool:
    return w.lower() in MELEE_SET


def _is_ranged_weapon(w: str) -> bool:
    return w.lower() in RANGED_SET


class Tools:
    """All @ai_function equivalents bound to a GameState.

    Each method returns a JSON-serializable dict and logs to GameState.tool_trace.
    Methods raise on unknown character; otherwise return valid=False style dicts per paper.
    """

    def __init__(self, state: GameState):
        self.state = state

    # ------------------------------------------------------------------
    # 1) Query / validation
    # ------------------------------------------------------------------
    def check_valid_attack_line(self, attacker_name: str, defender_name: str) -> bool:
        """Line-of-sight check with height interpolation."""
        result = self.state.line_of_sight(attacker_name, defender_name)
        self.state.log_tool(
            "check_valid_attack_line",
            {"attacker_name": attacker_name, "defender_name": defender_name},
            result,
        )
        return result

    def check_hp(self, name: str) -> int:
        hp = self.state.check_hp(name)
        self.state.log_tool("check_hp", {"name": name}, hp)
        return hp

    def update_hp(self, name: str, delta: int) -> dict:
        """delta negative = damage, positive = heal. Use after roll_dmg + resist calc."""
        res = self.state.update_hp(name, delta)
        self.state.log_tool("update_hp", {"name": name, "delta": delta}, res)
        return res

    def check_side(self, name: str) -> str:
        if name in self.state.players:
            r = "player"
        elif name in self.state.monsters:
            r = "monster"
        else:
            raise KeyError(name)
        self.state.log_tool("check_side", {"name": name}, r)
        return r

    def check_player_property(self, name: str, prop: str):
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        val = getattr(ch, prop, None)
        self.state.log_tool("check_player_property", {"name": name, "prop": prop}, val)
        return val

    def check_class(self, name: str) -> str:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        self.state.log_tool("check_class", {"name": name}, ch.char_class)
        return ch.char_class

    def check_resources(self, name: str) -> dict:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        res = {
            "action": ch.num_of_action,
            "bonus_action": ch.num_of_bonus_action,
            "reaction": ch.num_of_reaction,
            "spell_slots": dict(ch.spell_slots),
            "speed_remaining": ch.speed_remaining,
        }
        self.state.log_tool("check_resources", {"name": name}, res)
        return res

    def check_monster_type(self, name: str) -> str:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        self.state.log_tool("check_monster_type", {"name": name}, ch.monster_type)
        return ch.monster_type

    def check_monster_actions(self, name: str) -> dict:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        # return available actions: weapons inventory + spell list + speed
        res = {
            "weapons": ch.inventory,
            "spells": ch.spell_list,
            "speed_remaining": ch.speed_remaining,
            "actions": ch.num_of_action,
            "bonus": ch.num_of_bonus_action,
        }
        self.state.log_tool("check_monster_actions", {"name": name}, res)
        return res

    def get_names_of_all_players(self) -> list[str]:
        r = self.state.all_player_names()
        self.state.log_tool("get_names_of_all_players", {}, r)
        return r

    def get_names_of_all_monsters(self) -> list[str]:
        r = self.state.all_monster_names()
        self.state.log_tool("get_names_of_all_monsters", {}, r)
        return r

    def check_player_mainhand(self, name: str) -> str:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        self.state.log_tool("check_player_mainhand", {"name": name}, ch.equipped_mainhand)
        return ch.equipped_mainhand

    def check_buffs(self, name: str) -> list[dict]:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        r = [{"name": b.name, "remaining": b.remaining_turns, "desc": b.description} for b in ch.buffs]
        self.state.log_tool("check_buffs", {"name": name}, r)
        return r

    def check_concentration(self, name: str) -> str | None:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        self.state.log_tool("check_concentration", {"name": name}, ch.concentration)
        return ch.concentration

    def check_resist(self, name: str) -> list[dict]:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        r = [
            {
                "damage_type": e.damage_type,
                "kind": e.kind,
                "remaining": e.remaining_turns,
            }
            for e in ch.resists
        ]
        self.state.log_tool("check_resist", {"name": name}, r)
        return r

    # ------------------------------------------------------------------
    # 2) Movement / positioning
    # ------------------------------------------------------------------
    def move(self, name: str, x: int, y: int) -> dict:
        return self.move_player(name, x, y)

    def move_player(self, name: str, x: int, y: int) -> dict:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        # bounds
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
        # distance cost: 5ft per cell (Chebyshev? Euclidean)
        cur = self.state.get_pos(name)
        if cur is None:
            raise KeyError(name)
        cx, cy, _cz = cur
        dist_cells = max(abs(cx - x), abs(cy - y))  # D&D 5e: diagonal = 5ft (simplified)
        # height slope: if diff >2, needs extra? For now allow but adv handled in attack
        cost = dist_cells * 5
        if cost > ch.speed_remaining:
            res = {
                "valid": False,
                "reason": f"not enough speed ({ch.speed_remaining} remaining, need {cost})",
            }
            self.state.log_tool("move_player", {"name": name, "x": x, "y": y}, res)
            return res
        # opportunity attack check is caller's responsibility, but we can hint
        ch.speed_remaining -= cost
        new_pos = (x, y, cell.z)
        self.state.set_pos(name, new_pos)
        res = {"valid": True, "pos": new_pos, "speed_remaining": ch.speed_remaining}
        self.state.log_tool("move_player", {"name": name, "x": x, "y": y}, res)
        return res

    def dash(self, name: str) -> dict:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        if ch.num_of_action < 1:
            res = {"valid": False, "reason": "no action for dash"}
            self.state.log_tool("dash", {"name": name}, res)
            return res
        ch.num_of_action -= 1
        ch.speed_remaining += ch.speed
        res = {"valid": True, "speed_remaining": ch.speed_remaining}
        self.state.log_tool("dash", {"name": name}, res)
        return res

    def disengage(self, name: str) -> dict:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        if ch.num_of_action < 1:
            res = {"valid": False, "reason": "no action for disengage"}
            self.state.log_tool("disengage", {"name": name}, res)
            return res
        ch.num_of_action -= 1
        # mark buff that prevents opportunity attack this turn
        from .models import Buff

        ch.buffs.append(
            Buff(
                name="disengaged",
                remaining_turns=1,
                description="No opportunity attacks",
            )
        )
        res = {"valid": True}
        self.state.log_tool("disengage", {"name": name}, res)
        return res

    def opportunity_attack(self, mover: str, enemy: str) -> dict:
        """Called when mover leaves reach of enemy."""
        # check adjacency before move: if within 5ft and enemy has reaction and not disengaged
        ch_mover = self.state.get_character(mover)
        ch_enemy = self.state.get_character(enemy)
        if not ch_mover or not ch_enemy:
            raise KeyError("unknown character")
        # if mover has disengaged buff, no OA
        if any(b.name == "disengaged" for b in ch_mover.buffs):
            res = {"triggered": False, "reason": "disengaged"}
            self.state.log_tool("opportunity_attack", {"mover": mover, "enemy": enemy}, res)
            return res
        if ch_enemy.num_of_reaction < 1:
            res = {"triggered": False, "reason": "no reaction"}
            self.state.log_tool("opportunity_attack", {"mover": mover, "enemy": enemy}, res)
            return res
        # check reach: within 1 cell is melee reach
        pa = self.state.get_pos(enemy)
        pb = self.state.get_pos(mover)  # after move; we need pre-move? caller should handle before move
        # For simplicity treat current distance after intent but before move as trigger.
        # If within 1, trigger.
        # Caller should call before moving.
        # Here we just report triggered if adjacent.
        # To make it simple, we assume caller provides correct timing; we check current distance before move.
        # If they already moved, distance may be >1. We still check if they were adjacent: not perfect.
        res = {"triggered": False, "reason": "not in reach"}
        # naive: if positions are within 1 currently, it would have been.
        # We'll say if distance now >1 and before was 1, trigger — but we don't have history, so we trigger if enemy has reaction and no buff, leave to DM to resolve.
        # For determinism, we trigger only if still within 1 (means attempted to move while engaged - we consider trigger).
        # Better: trigger if distance <=1*5? Let's check.
        if pa and pb and max(abs(pa[0] - pb[0]), abs(pa[1] - pb[1])) <= 1:
            res = {"triggered": True, "reach": 5}
        self.state.log_tool("opportunity_attack", {"mover": mover, "enemy": enemy}, res)
        return res

    def clear_speed(self, name: str) -> dict:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        ch.speed_remaining = 0
        res = {"valid": True, "speed_remaining": 0}
        self.state.log_tool("clear_speed", {"name": name}, res)
        return res

    def reset_speed(self, name: str) -> dict:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        ch.speed_remaining = ch.speed
        res = {"valid": True, "speed_remaining": ch.speed}
        self.state.log_tool("reset_speed", {"name": name}, res)
        return res

    # ------------------------------------------------------------------
    # 3) Dice primitives
    # ------------------------------------------------------------------
    def roll_dice(self, expr: str) -> int:
        v = roll_dice(expr)
        self.state.log_tool("roll_dice", {"expr": expr}, v)
        return v

    # ------------------------------------------------------------------
    # 4) Attack / spell resolution
    # ------------------------------------------------------------------
    def roll_attack(
        self,
        attacker_name: str,
        defender_name: str,
        roll_type: str = "normal",
        ac: int = 10,
        modifier: int = 0,
        weapon_name: str = "club",
        use_spellcasting_modifier: bool = False,
        action_cost: int = 1,
        bonus_action_cost: int = 0,
        reaction_cost: int = 0,
        is_critical: bool = False,
    ) -> dict:
        ch_att = self.state.get_character(attacker_name)
        ch_def = self.state.get_character(defender_name)
        if not ch_att:
            raise KeyError(attacker_name)
        if not ch_def:
            raise KeyError(defender_name)

        # validity: resources
        if (
            (ch_att.num_of_action < action_cost)
            or (ch_att.num_of_bonus_action < bonus_action_cost)
            or (ch_att.num_of_reaction < reaction_cost)
        ):
            res = {
                "valid": False,
                "ac": ac,
                "roll": 0,
                "success": False,
                "critical": False,
                "out_of_range": False,
                "reason": "insufficient action economy",
            }
            self.state.log_tool(
                "roll_attack",
                {
                    "attacker_name": attacker_name,
                    "defender_name": defender_name,
                    "weapon_name": weapon_name,
                },
                res,
            )
            return res

        # weapon fallback
        w = _weapon_for(weapon_name)
        if not w:
            # fallback to mainhand
            w = _weapon_for(ch_att.equipped_mainhand)
            weapon_name = ch_att.equipped_mainhand
        if w is None:
            # default club
            from .models import MELEE_WEAPONS

            w = MELEE_WEAPONS["club"]

        # range check
        # need positions: attacker vs defender must be in different dicts? Compute distance
        try:
            attacker_pos = self.state.get_pos(attacker_name)
            defender_pos = self.state.get_pos(defender_name)
        except:
            attacker_pos = defender_pos = None
        if attacker_pos and defender_pos:
            # melee check
            is_melee = w.category.value == "melee"
            if is_melee:
                if (
                    max(
                        abs(attacker_pos[0] - defender_pos[0]),
                        abs(attacker_pos[1] - defender_pos[1]),
                    )
                    > 1
                ):
                    # try ranged fallback logic from paper is caller's job; we just flag out_of_range
                    # deduct resources? Paper: returns valid True but out_of_range True without deduct? In code they deduct before range check for melee.
                    # We'll deduct resources then return out_of_range per paper's melee path.
                    ch_att.num_of_action -= action_cost
                    ch_att.num_of_bonus_action -= bonus_action_cost
                    ch_att.num_of_reaction -= reaction_cost
                    res = {
                        "valid": True,
                        "ac": ac,
                        "roll": 0,
                        "success": False,
                        "critical": False,
                        "out_of_range": True,
                        "reason": "melee out of range",
                    }
                    self.state.log_tool(
                        "roll_attack",
                        {
                            "attacker_name": attacker_name,
                            "defender_name": defender_name,
                        },
                        res,
                    )
                    return res
            else:
                # ranged: check distance vs range_long
                dist = self.state.distance_feet(attacker_name, defender_name)
                max_range = w.range_long or w.range_normal
                if dist > max_range:
                    ch_att.num_of_action -= action_cost
                    ch_att.num_of_bonus_action -= bonus_action_cost
                    ch_att.num_of_reaction -= reaction_cost
                    res = {
                        "valid": True,
                        "ac": ac,
                        "roll": 0,
                        "success": False,
                        "critical": False,
                        "out_of_range": True,
                        "reason": f"out of range {dist}ft > {max_range}ft",
                    }
                    self.state.log_tool(
                        "roll_attack",
                        {
                            "attacker_name": attacker_name,
                            "defender_name": defender_name,
                        },
                        res,
                    )
                    return res
        # Deduct economy
        ch_att.num_of_action -= action_cost
        ch_att.num_of_bonus_action -= bonus_action_cost
        ch_att.num_of_reaction -= reaction_cost

        # AC override
        effective_ac = max(ac, ch_def.ac)

        # Target stat for player vs monster modifier logic from paper
        # Paper: if attacker is player, ignore modifier and compute from stats; else use modifier param
        roll_mod = modifier
        is_player_att = attacker_name in self.state.players
        if is_player_att:
            # Determine stat
            if w.category.value == "ranged" or "finesse" in w.properties:
                target_stat = ch_att.ability_mod("dexterity")
            else:
                target_stat = ch_att.ability_mod("strength")
            if use_spellcasting_modifier:
                target_stat = ch_att.spellcasting_mod()
            roll_mod = ch_att.pb + target_stat
        # Height advantage handling from paper: if abs(z diff) >2 adjust roll_type
        # Paper excerpt had a bug: abs(attacker_pos[2] - defender_pos[2] > 2) — we implement sensible: diff>2
        if attacker_pos and defender_pos and abs(attacker_pos[2] - defender_pos[2]) > 2:
            # higher gets advantage per design
            # If attacker higher, advantage; if lower, disadvantage? Simplify: higher = advantage
            if attacker_pos[2] > defender_pos[2]:
                if roll_type == "disadvantage":
                    roll_type = "normal"
                elif roll_type == "normal":
                    roll_type = "advantage"
            else:
                if roll_type == "advantage":
                    roll_type = "normal"
                elif roll_type == "normal":
                    roll_type = "disadvantage"

        # Roll
        if roll_type == "advantage":
            raw = roll_dice("2d20kh1")
        elif roll_type == "disadvantage":
            raw = roll_dice("2d20kl1")
        elif roll_type == "normal":
            raw = roll_dice("1d20")
        else:
            raise ValueError(f"invalid roll_type {roll_type}")

        critical = (raw == 20 and not attacker_pos) or raw == 20 or is_critical
        # For crit, raw==20 already captured; is_critical forces crit
        if is_critical:
            critical = True
        total = raw + roll_mod
        success = total >= effective_ac or critical

        res = {
            "valid": True,
            "ac": effective_ac,
            "roll": total,
            "raw": raw,
            "modifier": roll_mod,
            "success": success,
            "critical": critical,
            "out_of_range": False,
        }
        self.state.log_tool(
            "roll_attack",
            {
                "attacker_name": attacker_name,
                "defender_name": defender_name,
                "weapon_name": weapon_name,
                "roll_type": roll_type,
            },
            res,
        )
        return res

    def roll_spell_attack(
        self,
        attacker_name: str,
        defender_name: str,
        roll_type: str = "normal",
        ac: int = 10,
        is_ranged: bool = True,
        action_cost: int = 1,
        bonus_action_cost: int = 0,
    ) -> dict:
        # Spell attack is similar to weapon attack but uses spellcasting mod
        return self.roll_attack(
            attacker_name,
            defender_name,
            roll_type=roll_type,
            ac=ac,
            modifier=0,
            weapon_name="spell",
            use_spellcasting_modifier=True,
            action_cost=action_cost,
            bonus_action_cost=bonus_action_cost,
        )

    def roll_save(
        self,
        attacker_name: str,
        defender_name: str,
        ability: str,
        dc: int,
        action_cost: int = 0,
    ) -> dict:
        """Defender makes saving throw vs dc."""
        ch_att = self.state.get_character(attacker_name)
        ch_def = self.state.get_character(defender_name)
        if not ch_att or not ch_def:
            raise KeyError("unknown")
        # Paralyze auto-fail handled by caller? Paper says auto fail str/dex saves if paralyzed
        auto_fail = False
        for b in ch_def.buffs:
            if b.name.lower() == "paralyzed" and ability.lower() in (
                "strength",
                "dexterity",
            ):
                auto_fail = True
        if auto_fail:
            res = {
                "valid": True,
                "roll": 0,
                "dc": dc,
                "success": False,
                "auto_fail": True,
            }
            self.state.log_tool(
                "roll_save",
                {
                    "attacker_name": attacker_name,
                    "defender_name": defender_name,
                    "ability": ability,
                    "dc": dc,
                },
                res,
            )
            return res
        mod = ch_def.ability_mod(ability.lower())
        # proficiency? simplify: if monster type? ignore
        raw = roll_dice("1d20")
        total = raw + mod
        success = total >= dc
        res = {
            "valid": True,
            "roll": total,
            "raw": raw,
            "modifier": mod,
            "dc": dc,
            "success": success,
        }
        self.state.log_tool(
            "roll_save",
            {
                "attacker_name": attacker_name,
                "defender_name": defender_name,
                "ability": ability,
                "dc": dc,
            },
            res,
        )
        return res

    def roll_dmg(
        self,
        attacker_name: str,
        defender_name: str,
        dmg_dice_expression: str,
        damage_type: str = "slashing",
        is_critical: bool = False,
    ) -> dict:
        ch_att = self.state.get_character(attacker_name)
        if not ch_att:
            raise KeyError(attacker_name)
        expr = dmg_dice_expression
        if is_critical:
            # double dice: "1d8" -> "2d8" (simplified: roll twice)
            # For complex like "2d6", double to "4d6"
            import re

            m = re.match(r"(\d+)d(\d+)(.*)", expr)
            if m:
                n = int(m.group(1)) * 2
                expr = f"{n}d{m.group(2)}{m.group(3)}"
        dmg = roll_dice(expr)
        # Add ability mod for weapon attacks? Simplified: add relevant mod if weapon
        # We expose raw; DM should compute resist later.
        res = {
            "valid": True,
            "damage": dmg,
            "dice": expr,
            "damage_type": damage_type,
            "critical": is_critical,
        }
        self.state.log_tool(
            "roll_dmg",
            {
                "attacker_name": attacker_name,
                "defender_name": defender_name,
                "expr": dmg_dice_expression,
            },
            res,
        )
        return res

    # ------------------------------------------------------------------
    # 5) Turn economy / bookkeeping
    # ------------------------------------------------------------------
    def roll_initiative(self) -> list[dict]:
        res = self.state.roll_initiative()
        self.state.log_tool("roll_initiative", {}, res)
        return res

    def reset_resources(self, name: str) -> dict:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        ch.num_of_action = 1
        ch.num_of_bonus_action = 1
        # reaction resets at start of turn per RAW; but paper says end of turn checklist resets resources (incl reaction)
        ch.num_of_reaction = 1
        res = {"valid": True}
        self.state.log_tool("reset_resources", {"name": name}, res)
        return res

    def check_resist_alias(self, name: str):
        return self.check_resist(name)

    # Buff / resist / concentration management
    def add_resist(self, name: str, damage_type: str, turns: int = -1) -> dict:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        from .models import ResistEntry

        ch.resists.append(ResistEntry(damage_type=damage_type, kind="resist", remaining_turns=turns))
        res = {"valid": True}
        self.state.log_tool("add_resist", {"name": name, "damage_type": damage_type}, res)
        return res

    def add_immune(self, name: str, damage_type: str, turns: int = -1) -> dict:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        from .models import ResistEntry

        ch.resists.append(ResistEntry(damage_type=damage_type, kind="immune", remaining_turns=turns))
        res = {"valid": True}
        self.state.log_tool("add_immune", {"name": name, "damage_type": damage_type}, res)
        return res

    def add_vulner(self, name: str, damage_type: str, turns: int = -1) -> dict:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        from .models import ResistEntry

        ch.resists.append(ResistEntry(damage_type=damage_type, kind="vulner", remaining_turns=turns))
        res = {"valid": True}
        self.state.log_tool("add_vulner", {"name": name, "damage_type": damage_type}, res)
        return res

    def remove_a_buff(self, name: str, buff_name: str) -> dict:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        before = len(ch.buffs)
        ch.buffs = [b for b in ch.buffs if b.name != buff_name]
        res = {"valid": True, "removed": before != len(ch.buffs)}
        self.state.log_tool("remove_a_buff", {"name": name, "buff_name": buff_name}, res)
        return res

    def remove_resist(self, name: str, damage_type: str) -> dict:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        before = len(ch.resists)
        ch.resists = [e for e in ch.resists if not (e.damage_type == damage_type and e.kind == "resist")]
        res = {"valid": True, "removed": before != len(ch.resists)}
        self.state.log_tool("remove_resist", {"name": name, "damage_type": damage_type}, res)
        return res

    def remove_immune(self, name: str, damage_type: str) -> dict:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        before = len(ch.resists)
        ch.resists = [e for e in ch.resists if not (e.damage_type == damage_type and e.kind == "immune")]
        res = {"valid": True, "removed": before != len(ch.resists)}
        self.state.log_tool("remove_immune", {"name": name, "damage_type": damage_type}, res)
        return res

    def remove_vulner(self, name: str, damage_type: str) -> dict:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        before = len(ch.resists)
        ch.resists = [e for e in ch.resists if not (e.damage_type == damage_type and e.kind == "vulner")]
        res = {"valid": True, "removed": before != len(ch.resists)}
        self.state.log_tool("remove_vulner", {"name": name, "damage_type": damage_type}, res)
        return res

    def remove_a_concentration(self, name: str) -> dict:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        ch.concentration = None
        ch.concentration_turns = 0
        res = {"valid": True}
        self.state.log_tool("remove_a_concentration", {"name": name}, res)
        return res

    def print_death_point(self) -> dict:
        res = {"log": list(self.state.death_log)}
        self.state.log_tool("print_death_point", {}, res)
        return res

    # ------------------------------------------------------------------
    # 6) Rendering
    # ------------------------------------------------------------------
    def visualize_map(self) -> str:
        w, h = self.state.map_size()
        grid = [["." for _ in range(w)] for _ in range(h)]
        for y in range(h):
            for x in range(w):
                if not self.state.map[y][x].valid:
                    grid[y][x] = "#"
        for name, (x, y, z) in list(self.state.players_pos.items()) + list(self.state.monster_pos.items()):
            if 0 <= x < w and 0 <= y < h:
                # first letter
                grid[y][x] = name[0].upper() if name in self.state.players else name[0].lower()
        lines = ["".join(row) for row in grid]
        out = "\n".join(lines)
        self.state.log_tool("visualize_map", {}, out)
        return out

    # ------------------------------------------------------------------
    # Schema generation for LLM function calling
    # ------------------------------------------------------------------
    def tool_schemas(self) -> list[dict]:
        """Return OpenAI-compatible tool schemas."""
        # Simplified definitions — enough for LLM to call
        return [
            {
                "type": "function",
                "function": {
                    "name": "check_valid_attack_line",
                    "description": "Check line-of-sight between attacker and defender",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "attacker_name": {"type": "string"},
                            "defender_name": {"type": "string"},
                        },
                        "required": ["attacker_name", "defender_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_hp",
                    "description": "Get HP of a character",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_side",
                    "description": "Check if character is player or monster",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_player_property",
                    "description": "Get character property",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "prop": {"type": "string"},
                        },
                        "required": ["name", "prop"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_resources",
                    "description": "Check action economy and spell slots",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_class",
                    "description": "Get character class",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_monster_type",
                    "description": "Get monster type",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_monster_actions",
                    "description": "Get monster available actions",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
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
                    "name": "check_player_mainhand",
                    "description": "Check equipped weapon",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_buffs",
                    "description": "Check active buffs",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_concentration",
                    "description": "Check concentration spell",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_resist",
                    "description": "Check resistances",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "move_player",
                    "description": "Move character to x,y (grid). Each cell 5ft.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                        },
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
                        "properties": {
                            "name": {"type": "string"},
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                        },
                        "required": ["name", "x", "y"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dash",
                    "description": "Dash to gain extra movement",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "disengage",
                    "description": "Disengage to avoid opportunity attacks",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "opportunity_attack",
                    "description": "Check if moving provokes opportunity attack",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "mover": {"type": "string"},
                            "enemy": {"type": "string"},
                        },
                        "required": ["mover", "enemy"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clear_speed",
                    "description": "Set speed to 0 (restrained)",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "reset_speed",
                    "description": "Reset speed to max",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "reset_resources",
                    "description": "Reset action/bonus/reaction",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "roll_dice",
                    "description": "Roll dice expression e.g. 1d20, 2d6",
                    "parameters": {
                        "type": "object",
                        "properties": {"expr": {"type": "string"}},
                        "required": ["expr"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "roll_attack",
                    "description": "Roll attack. Validates economy, range. Returns success/critical/out_of_range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "attacker_name": {"type": "string"},
                            "defender_name": {"type": "string"},
                            "roll_type": {
                                "type": "string",
                                "enum": ["normal", "advantage", "disadvantage"],
                            },
                            "ac": {"type": "integer"},
                            "modifier": {"type": "integer"},
                            "weapon_name": {"type": "string"},
                            "use_spellcasting_modifier": {"type": "boolean"},
                            "action_cost": {"type": "integer"},
                            "bonus_action_cost": {"type": "integer"},
                            "reaction_cost": {"type": "integer"},
                            "is_critical": {"type": "boolean"},
                        },
                        "required": ["attacker_name", "defender_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "roll_spell_attack",
                    "description": "Spell attack roll",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "attacker_name": {"type": "string"},
                            "defender_name": {"type": "string"},
                            "roll_type": {"type": "string"},
                            "ac": {"type": "integer"},
                            "is_ranged": {"type": "boolean"},
                        },
                        "required": ["attacker_name", "defender_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "roll_save",
                    "description": "Saving throw",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "attacker_name": {"type": "string"},
                            "defender_name": {"type": "string"},
                            "ability": {"type": "string"},
                            "dc": {"type": "integer"},
                        },
                        "required": ["attacker_name", "defender_name", "ability", "dc"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "roll_dmg",
                    "description": "Roll damage dice",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "attacker_name": {"type": "string"},
                            "defender_name": {"type": "string"},
                            "dmg_dice_expression": {"type": "string"},
                            "damage_type": {"type": "string"},
                            "is_critical": {"type": "boolean"},
                        },
                        "required": [
                            "attacker_name",
                            "defender_name",
                            "dmg_dice_expression",
                        ],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "update_hp",
                    "description": "Update HP by delta (negative damage, positive heal)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "delta": {"type": "integer"},
                        },
                        "required": ["name", "delta"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "roll_initiative",
                    "description": "Roll initiative for all combatants",
                    "parameters": {"type": "object", "properties": {}, "required": []},
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
                    "name": "add_resist",
                    "description": "Add resistance",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "damage_type": {"type": "string"},
                        },
                        "required": ["name", "damage_type"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_immune",
                    "description": "Add immunity",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "damage_type": {"type": "string"},
                        },
                        "required": ["name", "damage_type"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_vulner",
                    "description": "Add vulnerability",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "damage_type": {"type": "string"},
                        },
                        "required": ["name", "damage_type"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "remove_a_buff",
                    "description": "Remove a buff",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "buff_name": {"type": "string"},
                        },
                        "required": ["name", "buff_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "remove_resist",
                    "description": "Remove resistance",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "damage_type": {"type": "string"},
                        },
                        "required": ["name", "damage_type"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "remove_immune",
                    "description": "Remove immunity",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "damage_type": {"type": "string"},
                        },
                        "required": ["name", "damage_type"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "remove_vulner",
                    "description": "Remove vulnerability",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "damage_type": {"type": "string"},
                        },
                        "required": ["name", "damage_type"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "remove_a_concentration",
                    "description": "Remove concentration",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "print_death_point",
                    "description": "Print death log at end of combat",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
        ]

    def dispatch(self, name: str, args: dict) -> Any:
        """Dispatch by name for LLM tool call."""
        fn = getattr(self, name, None)
        if not fn:
            raise ValueError(f"Unknown tool {name}")
        return fn(**args)
