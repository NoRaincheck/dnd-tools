"""TricubeTools — scene-level tools, and TricubeCampaignTools wrapper.

Mirrors dnd_tools.tools.Tools and dnd_campaign.tools.CampaignTools patterns.
All mutations go through TricubeState/CampaignState and are logged to tool_trace.
Uses dnd_tools (Cell/dice) and dnd_campaign (CampaignState pattern) as foundations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dnd_campaign.tools import CampaignTools as DndCampaignTools  # interop reference
from dnd_tools.tools import Tools as DndTools  # reference for schema style

from .dice import opposed_result, reevaluate_with_difficulty, roll_tricube
from .models import Affliction, effort_for_rank
from .state import TricubeCampaignState, TricubeState

_ = DndCampaignTools
_ = DndTools


class TricubeTools:
    """Scene-level tool surface for LLM."""

    def __init__(self, state: TricubeState):
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

    def check_side(self, name: str) -> str:
        if name in self.state.players:
            r = "player"
        elif name in self.state.monsters:
            r = "monster"
        else:
            raise KeyError(name)
        self.state.log_tool("check_side", {"name": name}, r)
        return r

    def check_karma_resolve(self, name: str) -> dict[str, Any]:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        r = {
            "name": name,
            "karma": ch.karma,
            "karma_max": ch.karma_max,
            "resolve": ch.resolve,
            "resolve_max": ch.resolve_max,
            "rank": ch.rank,
            "trait": ch.trait,
            "concept": ch.concept,
            "combat_style": ch.combat_style,
            "perks": list(ch.perks),
            "quirks": list(ch.quirks),
            "afflictions": len(ch.afflictions),
            "retired": ch.retired,
            "pos": ch.pos,
        }
        self.state.log_tool("check_karma_resolve", {"name": name}, r)
        return r

    def check_afflictions(self, name: str) -> dict[str, Any]:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        r = {
            "name": name,
            "afflictions": [
                {"name": a.name, "permanent": a.permanent, "recovery": a.recovery, "location": a.location}
                for a in ch.afflictions
            ],
            "count": len(ch.afflictions),
            "retired": ch.retired,
        }
        self.state.log_tool("check_afflictions", {"name": name}, r)
        return r

    def check_effort(self, target: str) -> dict[str, Any]:
        v = self.state.effort_pools.get(target, 0)
        r = {"target": target, "effort": v}
        self.state.log_tool("check_effort", {"target": target}, r)
        return r

    def check_valid_attack_line(self, attacker_name: str, defender_name: str) -> bool:
        result = self.state.line_of_sight(attacker_name, defender_name)
        self.state.log_tool(
            "check_valid_attack_line", {"attacker_name": attacker_name, "defender_name": defender_name}, result
        )
        return result

    def check_trait(self, name: str) -> str:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        self.state.log_tool("check_trait", {"name": name}, ch.trait)
        return ch.trait

    # ------------------------------------------------------------------
    # Movement (reuse 5ft per cell like dnd)
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
        # no speed gate for tricube narrative movement; allow 1 cell per call
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
    # Effort pool management (GM)
    # ------------------------------------------------------------------
    def set_effort(self, target: str, tokens: int) -> dict[str, Any]:
        self.state.effort_pools[target] = int(tokens)
        res = {"target": target, "effort": tokens}
        self.state.log_tool("set_effort", {"target": target, "tokens": tokens}, res)
        return res

    def set_effort_from_rank(self, target: str, rank: int, is_boss: bool = False) -> dict[str, Any]:
        tokens = effort_for_rank(int(rank), is_boss=bool(is_boss))
        return self.set_effort(target, tokens)

    # ------------------------------------------------------------------
    # Core resolution
    # ------------------------------------------------------------------
    def roll_challenge(
        self,
        character: str,
        trait: str,
        difficulty: int = 5,
        dice_count: int | None = None,
        out_of_scope: bool = False,
        effort_target: str | None = None,
    ) -> dict[str, Any]:
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        trait = trait.lower()
        if trait not in ("agile", "brawny", "crafty"):
            raise ValueError(f"trait must be agile/brawny/crafty, got {trait}")
        if dice_count is None:
            dice_count = ch.dice_count_for(trait, out_of_scope=out_of_scope)
        else:
            dice_count = max(1, min(3, int(dice_count)))
            if out_of_scope:
                dice_count = max(1, dice_count - 1)
        # apply rank modifier if targeting a ranked foe and effort_target provided
        effective_difficulty = int(difficulty)
        if effort_target:
            # estimate rank from effort? Use bestiary fallback: if target is monster name, use its rank vs character rank
            tgt = self.state.get_character(effort_target)
            if tgt:
                if tgt.rank > ch.rank:
                    effective_difficulty += 1
                elif tgt.rank < ch.rank:
                    effective_difficulty -= 1
                # clamp while allowing quirk to exceed: let diff go 3..7 but allow >7 via quirks
                # no clamp here except floor 2?
                effective_difficulty = max(2, effective_difficulty)
        # new challenge: reset karma gate for this challenge (allow 1 spend per challenge)
        ch._karma_spent_this_challenge = False
        # pending quirk increases difficulty by 1 (declared before roll)
        pending_before = ch._pending_quirk
        if pending_before:
            effective_difficulty += 1
            # quirk can push above 7
        r = roll_tricube(dice_count, effective_difficulty)
        # handle effort removal
        # if effort_target is an effort pool group, deduct
        if effort_target and effort_target in self.state.effort_pools:
            pool = self.state.effort_pools[effort_target]
            removed = min(pool, r["successes"])
            self.state.effort_pools[effort_target] = pool - removed
            r["effort_removed"] = removed
            r["effort_remaining"] = self.state.effort_pools[effort_target]
        elif effort_target is None and character in self.state.effort_pools:
            pool = self.state.effort_pools[character]
            removed = min(pool, r["successes"])
            self.state.effort_pools[character] = pool - removed
            r["effort_removed"] = removed
            r["effort_remaining"] = self.state.effort_pools[character]
        # auto-resolve quirk recovery (karma) after roll if pending
        if pending_before:
            # success flag for later choose_quirk_reward decision
            ch.karma = min(ch.karma_max, ch.karma + 1)
            r["quirk_recovery"] = {
                "quirk": pending_before,
                "karma": ch.karma,
                "can_swap_to_resolve": bool(r["success"]),
            }
            ch._pending_quirk = None
            r["pending_quirk"] = pending_before
        else:
            r["pending_quirk"] = None
        # quirk recovery gating: record for spends
        # on this roll, resolve karma/quirk after caller sees result via invoke_quirk/spend_karma results
        # we mark challenge id
        self.state._challenge_counter += 1
        r["challenge_id"] = self.state._challenge_counter
        r["character"] = character
        r["trait"] = trait
        r["raw_difficulty"] = difficulty
        r["effective_difficulty"] = effective_difficulty
        self.state.log_tool(
            "roll_challenge",
            {
                "character": character,
                "trait": trait,
                "difficulty": difficulty,
                "dice_count": dice_count,
                "out_of_scope": out_of_scope,
                "effort_target": effort_target,
            },
            r,
        )
        return r

    def invoke_quirk(self, character: str, quirk: str) -> dict[str, Any]:
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        if ch._pending_quirk:
            res = {"valid": False, "reason": "quirk already declared for this challenge"}
            self.state.log_tool("invoke_quirk", {"character": character, "quirk": quirk}, res)
            return res
        # validate quirk exists or affliction usable as quirk
        all_q = [q.lower() for q in ch.quirks] + [a.name.lower() for a in ch.afflictions]
        if quirk.lower() not in all_q:
            res = {
                "valid": False,
                "reason": f"quirk '{quirk}' not found in {ch.quirks + [a.name for a in ch.afflictions]}",
            }
            self.state.log_tool("invoke_quirk", {"character": character, "quirk": quirk}, res)
            return res
        ch._pending_quirk = quirk
        res = {
            "valid": True,
            "character": character,
            "quirk": quirk,
            "note": "+1 difficulty on next roll_challenge; recover karma (or resolve on success)",
        }
        self.state.log_tool("invoke_quirk", {"character": character, "quirk": quirk}, res)
        return res

    def _resolve_quirk_after_roll(self, character: str, roll_result: dict[str, Any]) -> dict[str, Any]:
        ch = self.state.get_character(character)
        if not ch or not ch._pending_quirk:
            return {"applied": False}
        quirk = ch._pending_quirk
        ch._pending_quirk = None
        success = bool(roll_result.get("success"))
        # recovery rule: normally +1 karma; if success may recover resolve instead (we give choice via tool)
        # For deterministic fallback, we give karma; LLM can call recover to choose resolve
        ch.karma = min(ch.karma_max, ch.karma + 1)
        # caller may want to convert karma->resolve if success
        res = {
            "applied": True,
            "quirk": quirk,
            "success": success,
            "karma": ch.karma,
            "resolve": ch.resolve,
            "note": "gained +1 karma; if success may swap to +1 resolve via choose_quirk_reward",
        }
        self.state.log_tool("_resolve_quirk_after_roll", {"character": character}, res)
        return res

    def choose_quirk_reward(self, character: str, reward: str = "karma") -> dict[str, Any]:
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        # this is called after a successful quirk roll to swap karma for resolve
        # we already gave karma; if they choose resolve, adjust
        if reward == "resolve":
            # we added 1 karma above; undo and add resolve
            if ch.karma > 0:
                ch.karma -= 1
            ch.resolve = min(ch.resolve_max, ch.resolve + 1)
            res = {"character": character, "reward": "resolve", "karma": ch.karma, "resolve": ch.resolve}
        else:
            res = {"character": character, "reward": "karma", "karma": ch.karma, "resolve": ch.resolve}
        self.state.log_tool("choose_quirk_reward", {"character": character, "reward": reward}, res)
        return res

    def spend_karma(
        self, character: str, rolls: list[int] | None = None, difficulty: int | None = None
    ) -> dict[str, Any]:
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        if ch._karma_spent_this_challenge:
            res = {"valid": False, "reason": "karma already spent this challenge (max 1)"}
            self.state.log_tool("spend_karma", {"character": character}, res)
            return res
        if ch.karma <= 0:
            res = {"valid": False, "reason": "no karma remaining"}
            self.state.log_tool("spend_karma", {"character": character}, res)
            return res
        # retroactive -1 difficulty: caller must provide rolls + current difficulty
        if rolls is None or difficulty is None:
            res = {"valid": False, "reason": "need rolls + difficulty to re-evaluate"}
            self.state.log_tool("spend_karma", {"character": character}, res)
            return res
        ch.karma -= 1
        ch._karma_spent_this_challenge = True
        new_diff = max(2, int(difficulty) - 1)  # can go 3->2; don't allow <2
        new_r = reevaluate_with_difficulty(rolls, new_diff)
        new_r["karma"] = ch.karma
        new_r["old_difficulty"] = difficulty
        new_r["new_difficulty"] = new_diff
        self.state.log_tool(
            "spend_karma", {"character": character, "difficulty": difficulty, "new_difficulty": new_diff}, new_r
        )
        return new_r

    def bypass_challenge(self, character: str, perk: str) -> dict[str, Any]:
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        if perk.lower() not in [p.lower() for p in ch.perks]:
            res = {"valid": False, "reason": f"perk '{perk}' not known"}
            self.state.log_tool("bypass_challenge", {"character": character, "perk": perk}, res)
            return res
        if ch.karma <= 0:
            res = {"valid": False, "reason": "no karma"}
            self.state.log_tool("bypass_challenge", {"character": character, "perk": perk}, res)
            return res
        if ch._karma_spent_this_challenge:
            res = {"valid": False, "reason": "karma already spent"}
            self.state.log_tool("bypass_challenge", {"character": character, "perk": perk}, res)
            return res
        ch.karma -= 1
        ch._karma_spent_this_challenge = True
        res = {
            "valid": True,
            "character": character,
            "perk": perk,
            "karma": ch.karma,
            "note": "challenge bypassed via perk (GM must validate narrative)",
        }
        self.state.log_tool("bypass_challenge", {"character": character, "perk": perk}, res)
        return res

    # ------------------------------------------------------------------
    # Defense / Resolve handling
    # ------------------------------------------------------------------
    def defense_roll(
        self, character: str, trait: str, difficulty: int = 5, out_of_scope: bool = False
    ) -> dict[str, Any]:
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        r = self.roll_challenge(character, trait, difficulty, out_of_scope=out_of_scope)
        # resolve cost: fail -> -1 resolve, crit -> -2 (quirk recovery already handled in roll_challenge)
        resolve_cost = 0
        if r["critical_failure"]:
            resolve_cost = 2
        elif not r["success"]:
            resolve_cost = 1
        if resolve_cost:
            self.state.update_resolve(character, -resolve_cost)
            r["resolve_cost"] = resolve_cost
            r["resolve_after"] = ch.resolve
        else:
            r["resolve_cost"] = 0
        # if defeated, state.update_resolve already added affliction+recovery
        self.state.log_tool("defense_roll", {"character": character, "trait": trait, "difficulty": difficulty}, r)
        return r

    def apply_affliction(
        self, target: str, name: str, permanent: bool = False, recovery: str = "scene", location: str | None = None
    ) -> dict[str, Any]:
        ch = self.state.get_character(target)
        if not ch:
            raise KeyError(target)
        aff = Affliction(name=name, permanent=permanent, recovery=recovery, location=location)
        ch.afflictions.append(aff)
        if len(ch.afflictions) > 3:
            ch.alive = False
        res = {
            "target": target,
            "affliction": name,
            "permanent": permanent,
            "recovery": recovery,
            "total": len(ch.afflictions),
            "retired": ch.retired,
        }
        self.state.log_tool("apply_affliction", {"target": target, "name": name, "permanent": permanent}, res)
        return res

    def recover_affliction(self, target: str, affliction_name: str, perk: str | None = None) -> dict[str, Any]:
        ch = self.state.get_character(target)
        if not ch:
            raise KeyError(target)
        idx = next((i for i, a in enumerate(ch.afflictions) if a.name.lower() == affliction_name.lower()), None)
        if idx is None:
            res = {"valid": False, "reason": f"affliction '{affliction_name}' not found"}
            self.state.log_tool("recover_affliction", {"target": target, "affliction_name": affliction_name}, res)
            return res
        aff = ch.afflictions[idx]
        # permanent requires permanent karma (reduce max) or conversion via advance
        if aff.permanent:
            if ch.karma_max <= 0:
                res = {
                    "valid": False,
                    "reason": "permanent affliction requires permanent karma (reduce max) or advance conversion",
                }
                self.state.log_tool("recover_affliction", {"target": target, "affliction_name": affliction_name}, res)
                return res
            # need a perk that fits
            if perk and perk.lower() not in [p.lower() for p in ch.perks]:
                res = {"valid": False, "reason": "perk not known"}
                self.state.log_tool("recover_affliction", {"target": target, "affliction_name": affliction_name}, res)
                return res
            # cost permanent karma: reduce max by 1 and karma by 1 if available
            ch.karma_max = max(0, ch.karma_max - 1)
            ch.karma = min(ch.karma, ch.karma_max)
        else:
            if ch.karma <= 0:
                res = {"valid": False, "reason": "need 1 karma"}
                self.state.log_tool("recover_affliction", {"target": target, "affliction_name": affliction_name}, res)
                return res
            ch.karma -= 1
        # remove
        ch.afflictions.pop(idx)
        ch.alive = True
        res = {
            "valid": True,
            "target": target,
            "removed": affliction_name,
            "karma": ch.karma,
            "karma_max": ch.karma_max,
            "remaining": len(ch.afflictions),
        }
        self.state.log_tool(
            "recover_affliction", {"target": target, "affliction_name": affliction_name, "perk": perk}, res
        )
        return res

    def update_resolve(self, name: str, delta: int) -> dict[str, Any]:
        res = self.state.update_resolve(name, delta)
        self.state.log_tool("update_resolve", {"name": name, "delta": delta}, res)
        return res

    def check_resolve(self, name: str) -> int:
        v = self.state.check_resolve(name)
        self.state.log_tool("check_resolve", {"name": name}, v)
        return v

    # compatibility aliases
    def check_hp(self, name: str) -> int:  # pragma: no cover
        return self.check_resolve(name)

    def update_hp(self, name: str, delta: int) -> dict[str, Any]:  # pragma: no cover
        return self.update_resolve(name, delta)

    # ------------------------------------------------------------------
    # Opposed / fear
    # ------------------------------------------------------------------
    def opposed_challenge(
        self, char_a: str, char_b: str, trait_a: str = "crafty", trait_b: str = "crafty"
    ) -> dict[str, Any]:
        ca = self.state.get_character(char_a)
        cb = self.state.get_character(char_b)
        if not ca or not cb:
            raise KeyError("unknown character")
        # use dice counts per archetype
        ra = roll_tricube(ca.dice_count_for(trait_a), 4)  # rolls independent; difficulty is opponent's high
        rb = roll_tricube(cb.dice_count_for(trait_b), 4)
        # Actual opposed evaluation uses highest die as difficulty, so we reuse rolls
        out = opposed_result(ra["rolls"], rb["rolls"])
        out["a"] = {"character": char_a, "rolls": ra["rolls"]}
        out["b"] = {"character": char_b, "rolls": rb["rolls"]}
        self.state.log_tool("opposed_challenge", {"char_a": char_a, "char_b": char_b}, out)
        return out

    def fear_check(self, character: str, difficulty: int = 5, inexperienced: bool = False) -> dict[str, Any]:
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        trait = "crafty"
        dc = ch.dice_count_for(trait, out_of_scope=inexperienced)
        # crafty 3, else 2 already handled by dice_count_for; fear rule says crafty 3 else 2, so same
        r = roll_tricube(dc, difficulty)
        if not r["success"]:
            self.state.update_resolve(character, -1)
            r["resolve_cost"] = 1
            r["resolve_after"] = ch.resolve
        else:
            r["resolve_cost"] = 0
        self.state.log_tool(
            "fear_check", {"character": character, "difficulty": difficulty, "inexperienced": inexperienced}, r
        )
        return r

    # ------------------------------------------------------------------
    # Turn bookkeeping
    # ------------------------------------------------------------------
    def roll_initiative(self) -> list[dict[str, Any]]:
        res = self.state.roll_initiative()
        self.state.log_tool("roll_initiative", {}, res)
        return res

    def end_turn(self, character: str) -> dict[str, Any]:
        ch = self.state.get_character(character)
        if ch:
            # clear per-turn karma gate
            ch._karma_spent_this_challenge = False
            # if pending quirk wasn't used (player declared but never rolled), clear it
            # keep it for next roll? No, per challenge it should be used next roll only; we keep for now
        res = {"character": character, "note": "end of turn bookkeeping"}
        self.state.log_tool("end_turn", {"character": character}, res)
        return res

    def print_affliction_log(self) -> dict[str, Any]:
        res = {"log": list(self.state.affliction_log)}
        self.state.log_tool("print_affliction_log", {}, res)
        return res

    # alias for compat
    def print_death_point(self) -> dict[str, Any]:
        return self.print_affliction_log()

    # ------------------------------------------------------------------
    # Helpers for simulation
    # ------------------------------------------------------------------
    def reset_for_next_challenge(self, character: str) -> None:
        ch = self.state.get_character(character)
        if ch:
            ch._karma_spent_this_challenge = False
            # don't clear _pending_quirk here; it should be cleared after roll

    # ------------------------------------------------------------------
    # Schemas
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
                    "description": "List monster/challenge names",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_side",
                    "description": "Check if character is player or monster",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_karma_resolve",
                    "description": "Get karma/resolve/rank/perks/quirks/afflictions of a character",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_afflictions",
                    "description": "List afflictions and retirement status",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_effort",
                    "description": "Check effort pool of a target/challenge",
                    "parameters": {
                        "type": "object",
                        "properties": {"target": {"type": "string"}},
                        "required": ["target"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_valid_attack_line",
                    "description": "Line-of-sight between attacker and defender (grid+height)",
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
                    "name": "check_trait",
                    "description": "Get character trait (agile/brawny/crafty)",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "move_player",
                    "description": "Move character to x,y (grid). One cell per call for narrative movement.",
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
                    "name": "set_effort",
                    "description": "Set effort tokens for a challenge/NPC (GM)",
                    "parameters": {
                        "type": "object",
                        "properties": {"target": {"type": "string"}, "tokens": {"type": "integer"}},
                        "required": ["target", "tokens"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "set_effort_from_rank",
                    "description": "Set effort from rank (rank or 2*rank for boss)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {"type": "string"},
                            "rank": {"type": "integer"},
                            "is_boss": {"type": "boolean"},
                        },
                        "required": ["target", "rank"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "roll_challenge",
                    "description": "Roll 1-3d6 vs difficulty 4-6 (3-7 with perks). GM assigns trait/difficulty/effort; dice_count auto from archetype if omitted; out_of_scope -1 die; effort_target deducts on successes. Returns rolls/success/exceptional/critical/effort_remaining.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "trait": {"type": "string", "enum": ["agile", "brawny", "crafty"]},
                            "difficulty": {"type": "integer"},
                            "dice_count": {"type": "integer"},
                            "out_of_scope": {"type": "boolean"},
                            "effort_target": {"type": "string"},
                        },
                        "required": ["character", "trait"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "invoke_quirk",
                    "description": "Declare quirk BEFORE roll: +1 difficulty next roll_challenge, then recover 1 karma (or 1 resolve if success) — max 1 per challenge",
                    "parameters": {
                        "type": "object",
                        "properties": {"character": {"type": "string"}, "quirk": {"type": "string"}},
                        "required": ["character", "quirk"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "choose_quirk_reward",
                    "description": "After successful quirk roll, choose karma or resolve reward",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "reward": {"type": "string", "enum": ["karma", "resolve"]},
                        },
                        "required": ["character"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "spend_karma",
                    "description": "Spend 1 karma AFTER roll to reduce difficulty by 1 (retroactive). Max 1 per challenge. Provide rolls+current difficulty.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "rolls": {"type": "array", "items": {"type": "integer"}},
                            "difficulty": {"type": "integer"},
                        },
                        "required": ["character", "rolls", "difficulty"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "bypass_challenge",
                    "description": "Spend 1 karma BEFORE roll to auto-bypass a challenge via perk (GM validates narrative)",
                    "parameters": {
                        "type": "object",
                        "properties": {"character": {"type": "string"}, "perk": {"type": "string"}},
                        "required": ["character", "perk"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "defense_roll",
                    "description": "Defense 1-3d6 vs difficulty (on enemy turn). Lose 1 resolve on fail, 2 on critical. Auto affliction at 0.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "trait": {"type": "string"},
                            "difficulty": {"type": "integer"},
                            "out_of_scope": {"type": "boolean"},
                        },
                        "required": ["character", "trait"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "apply_affliction",
                    "description": "Apply affliction at 0 resolve (victor chooses). permanent=true for critical failures.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {"type": "string"},
                            "name": {"type": "string"},
                            "permanent": {"type": "boolean"},
                            "recovery": {"type": "string"},
                            "location": {"type": "string"},
                        },
                        "required": ["target", "name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "recover_affliction",
                    "description": "Cure affliction: 1 karma (permanent costs permanent karma_max) + perk. Or via advance conversion (narrative).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {"type": "string"},
                            "affliction_name": {"type": "string"},
                            "perk": {"type": "string"},
                        },
                        "required": ["target", "affliction_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "update_resolve",
                    "description": "Update resolve by delta (negative damage, positive heal). Auto affliction at 0.",
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
                    "name": "check_resolve",
                    "description": "Get current resolve",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "opposed_challenge",
                    "description": "Opposed roll: both roll vs other's high die; tie-break most matches.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "char_a": {"type": "string"},
                            "char_b": {"type": "string"},
                            "trait_a": {"type": "string"},
                            "trait_b": {"type": "string"},
                        },
                        "required": ["char_a", "char_b"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fear_check",
                    "description": "Fear: crafty 3d6 else 2d6 -1 if inexperienced; fail -1 resolve.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "difficulty": {"type": "integer"},
                            "inexperienced": {"type": "boolean"},
                        },
                        "required": ["character"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "roll_initiative",
                    "description": "Roll initiative for all combatants (1d6+rank)",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "end_turn",
                    "description": "End turn bookkeeping (clear karma gate)",
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
                    "name": "print_affliction_log",
                    "description": "Print affliction log at end",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
        ]

    def dispatch(self, name: str, args: dict[str, Any]) -> Any:
        fn = getattr(self, name, None)
        if not fn:
            raise ValueError(f"Unknown tool {name}")
        return fn(**args)


# ---------------------------------------------------------------------------
# Campaign-level wrapper
# ---------------------------------------------------------------------------


class TricubeCampaignTools:
    """Wraps TricubeTools + TricubeCampaignState helpers."""

    def __init__(self, cstate: TricubeCampaignState):
        self.cstate = cstate
        self.inner_tools = TricubeTools(cstate.inner)

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

    # -- campaign helpers --------------------------------------------------

    def long_rest(self, name: str | None = None) -> dict[str, Any]:
        res = self.cstate.long_rest(name)
        self.cstate.inner.log_tool("long_rest", {"name": name}, res)
        self.cstate.checkpoint()
        return res

    def short_rest(self, name: str) -> dict[str, Any]:
        res = self.cstate.short_rest(name)
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
        loaded = TricubeCampaignState.load(path)
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
                    "description": "Long rest: full resolve + clear non-permanent afflictions (one or all players)",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "short_rest",
                    "description": "Short rest: reset per-turn gates",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "checkpoint",
                    "description": "Snapshot current scene to bounded history",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "save_checkpoint",
                    "description": "Persist snapshot + tail traces to file",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_summary",
                    "description": "Compact campaign summary for LLM context",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "prune_traces",
                    "description": "Prune tool_trace/transcript to last N",
                    "parameters": {"type": "object", "properties": {"keep_last": {"type": "integer"}}, "required": []},
                },
            },
        ]
        _ = Path
        return base + extra
