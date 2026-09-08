"""BladesTools — score-level tools, and BladesCampaignTools wrapper.

Mirrors dnd_tools.tools.Tools pattern: typed API + validation + OpenAI schemas,
all mutations through BladesState/CampaignState and logged to tool_trace.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .dice import roll_action, roll_fortune, roll_resistance
from .models import (
    ACTION_TO_ATTR,
    ACTIONS,
    EFFECT_TICKS,
    Effect,
    Position,
)
from .state import BladesCampaignState, BladesState

# ---------------------------------------------------------------------------
# Helpers: consequences table (SRD verbatim)
# ---------------------------------------------------------------------------

CONSEQUENCE_TABLE: dict[str, dict[str, list[str]]] = {
    "controlled": {
        "partial": [
            "minor complication occurs",
            "reduced effect (−1 tick or effect downgrade)",
            "lesser harm (level 1)",
            "fall to risky position",
        ],
        "failure": [
            "falter: press on by seizing a risky opportunity, or withdraw and try a different approach",
        ],
    },
    "risky": {
        "partial": [
            "harm (level 1-2)",
            "complication occurs",
            "reduced effect",
            "fall to desperate position",
        ],
        "failure": [
            "harm (level 1-2)",
            "complication occurs",
            "fall to desperate position",
            "lose this opportunity",
        ],
    },
    "desperate": {
        "partial": [
            "severe harm (level 2-3)",
            "serious complication occurs",
            "reduced effect",
        ],
        "failure": [
            "severe harm (level 2-3)",
            "serious complication occurs",
            "lose this opportunity for action",
        ],
    },
}


def _effect_ticks(effect: str, critical: bool) -> int:
    base = EFFECT_TICKS.get(effect.lower(), 2)
    if critical:
        # critical = increased effect: +1 tick (SRD) or effect tier up
        # For Limited=1, critical => 2 ticks (treat as +1); Standard 2→3; Great 3→5 extreme-ish but cap at 5
        if effect.lower() == "limited":
            base = 2
        elif effect.lower() == "standard":
            base = 3
        elif effect.lower() == "great":
            base = 5  # treat as extreme bump
        else:
            base = base + 1
    return base


class BladesTools:
    """Score-level tool surface for LLM."""

    def __init__(self, state: BladesState):
        self.state = state
        # track pending position/effect gates: already stored on character, but also global validation

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
        r = {
            "name": ch.name,
            "playbook": ch.playbook,
            "actions": dict(ch.actions),
            "stress": ch.stress,
            "stress_max": ch.stress_max,
            "trauma": list(ch.trauma),
            "harm": [{"level": h.level, "name": h.name} for h in ch.harm],
            "vice": ch.vice,
            "xp": ch.xp,
            "pos": ch.pos,
            "alive": ch.alive,
            "retired": ch.retired,
            "armor": ch.armor,
            "heavy": ch.heavy,
        }
        self.state.log_tool("check_character", {"name": name}, r)
        return r

    def check_stress(self, name: str) -> dict[str, Any]:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        r = {"name": name, "stress": ch.stress, "max": ch.stress_max, "trauma": list(ch.trauma), "retired": ch.retired}
        self.state.log_tool("check_stress", {"name": name}, r)
        return r

    def check_harm(self, name: str) -> dict[str, Any]:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        r = {"name": name, "harm": [{"level": h.level, "name": h.name} for h in ch.harm], "alive": ch.alive}
        self.state.log_tool("check_harm", {"name": name}, r)
        return r

    def check_clock(self, name: str) -> dict[str, Any] | None:
        r = self.state.check_clock(name)
        self.state.log_tool("check_clock", {"name": name}, r)
        return r

    def list_actions(self) -> dict[str, Any]:
        r = {
            "actions": ACTIONS,
            "attributes": {
                a: [k for k, v in ACTION_TO_ATTR.items() if v == a] for a in ["Insight", "Prowess", "Resolve"]
            },
        }
        self.state.log_tool("list_actions", {}, r)
        return r

    def visualize_clocks(self) -> dict[str, Any]:
        r = {
            k: {"ticks": v.ticks, "segments": v.segments, "completed": v.completed, "kind": v.kind}
            for k, v in self.state.clocks.items()
        }
        # also textual
        lines = []
        for k, v in self.state.clocks.items():
            filled = "■" * v.ticks + "□" * (v.segments - v.ticks)
            lines.append(f"{k} [{v.kind}] {filled} {v.ticks}/{v.segments} {'✓' if v.completed else ''}")
        self.state.log_tool("visualize_clocks", {}, {"clocks": r, "ascii": "\n".join(lines) or "(no clocks)"})
        return {"clocks": r, "ascii": "\n".join(lines) or "(no clocks)"}

    def check_valid_attack_line(self, attacker_name: str, defender_name: str) -> bool:
        result = self.state.line_of_sight(attacker_name, defender_name)
        self.state.log_tool(
            "check_valid_attack_line", {"attacker_name": attacker_name, "defender_name": defender_name}, result
        )
        return result

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
    # Position & Effect gate (must precede action_roll)
    # ------------------------------------------------------------------
    def set_position_and_effect(
        self,
        character: str,
        action: str,
        position: str,
        effect: str,
    ) -> dict[str, Any]:
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        pos = position.lower()
        eff = effect.lower()
        if pos not in {p.value for p in Position}:
            raise ValueError(f"position must be one of {[p.value for p in Position]}, got {position}")
        if eff not in {e.value for e in Effect}:
            raise ValueError(f"effect must be one of {[e.value for e in Effect]}, got {effect}")
        # normalize action
        from .models import _norm_action

        try:
            norm_action = _norm_action(action)
        except ValueError as e:
            res = {"valid": False, "reason": str(e)}
            self.state.log_tool("set_position_and_effect", {"character": character, "action": action}, res)
            return res
        ch._pending_position = pos
        ch._pending_effect = eff
        ch._pending_action = norm_action
        res = {
            "valid": True,
            "character": character,
            "action": norm_action,
            "position": pos,
            "effect": eff,
            "note": f"Agreed: {pos}/{eff} for {norm_action}. Call action_roll next; do not re-negotiate mid-roll.",
        }
        self.state.log_tool(
            "set_position_and_effect",
            {"character": character, "action": norm_action, "position": pos, "effect": eff},
            res,
        )
        return res

    def set_clock(self, name: str, segments: int = 6, kind: str = "obstacle") -> dict[str, Any]:
        clk = self.state.set_clock(name, segments=int(segments), kind=kind)
        res = {"name": clk.name, "segments": clk.segments, "ticks": clk.ticks, "kind": clk.kind}
        self.state.log_tool("set_clock", {"name": name, "segments": segments, "kind": kind}, res)
        return res

    def tick_clock(self, name: str, ticks: int) -> dict[str, Any]:
        res = self.state.tick_clock(name, int(ticks))
        self.state.log_tool("tick_clock", {"name": name, "ticks": ticks}, res)
        return res

    # ------------------------------------------------------------------
    # Bonus dice helpers
    # ------------------------------------------------------------------
    def push_yourself(self, character: str, bonus: str = "dice") -> dict[str, Any]:
        """Spend 2 stress for +1d or +1 effect. Must be before action_roll."""
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        bonus = bonus.lower()
        if bonus not in ("dice", "effect"):
            raise ValueError("bonus must be 'dice' or 'effect'")
        if ch.stress + 2 > ch.stress_max:
            # per SRD you can still push at 8/9 but you'll trauma; we allow and mark trauma if over
            # check trauma gate
            pass
        if ch._push_bonus:
            res = {"valid": False, "reason": "already pushed this action (max 1 push per roll)"}
            self.state.log_tool("push_yourself", {"character": character, "bonus": bonus}, res)
            return res
        # mark stress (will trauma if needed); we handle overflow via add_trauma? For now just add stress then check trauma
        stress_before = ch.stress
        # use state.mark_stress to handle logging
        self.state.mark_stress(character, 2)
        ch._push_bonus = bonus
        # check trauma overflow: if stress==max and we would exceed, trigger? But we capped at max, so need real overflow detection
        # Instead we detect: if stress_before +2 > ch.stress_max => trauma? But mark caps. Do explicit:
        if stress_before + 2 > ch.stress_max:
            # overflow: trauma occurs (choose first available trauma not yet taken, simple)
            from .models import TRAUMA_NAMES

            available = [t for t in TRAUMA_NAMES if t not in ch.trauma]
            chosen = available[0] if available else "Trauma"
            trauma_res = self.state.add_trauma(character, chosen)
            res = {
                "valid": True,
                "character": character,
                "bonus": bonus,
                "stress": ch.stress,
                "trauma": list(ch.trauma),
                "trauma_triggered": True,
                "trauma_result": trauma_res,
                "note": f"Pushed for +1 {bonus}: 2 stress; trauma '{chosen}' triggered (stress cleared to 0).",
            }
        else:
            res = {
                "valid": True,
                "character": character,
                "bonus": bonus,
                "stress": ch.stress,
                "note": f"Pushed for +1 {bonus}: 2 stress (now {ch.stress}/{ch.stress_max})",
            }
        self.state.log_tool("push_yourself", {"character": character, "bonus": bonus}, res)
        return res

    def assist(self, helper: str, target: str) -> dict[str, Any]:
        """Helper takes 1 stress to give target +1d next action_roll."""
        helper_ch = self.state.get_character(helper)
        target_ch = self.state.get_character(target)
        if not helper_ch or not target_ch:
            raise KeyError("helper or target not found")
        if helper_ch.stress + 1 > helper_ch.stress_max:
            # allow but trauma risk
            pass
        stress_before = helper_ch.stress
        self.state.mark_stress(helper, 1)
        target_ch._assist_bonus = 1
        overflow = stress_before + 1 > helper_ch.stress_max
        trauma_info = None
        if overflow:
            from .models import TRAUMA_NAMES

            available = [t for t in TRAUMA_NAMES if t not in helper_ch.trauma]
            chosen = available[0] if available else "Trauma"
            trauma_info = self.state.add_trauma(helper, chosen)
        res = {
            "valid": True,
            "helper": helper,
            "target": target,
            "helper_stress": helper_ch.stress,
            "target_assist_bonus": target_ch._assist_bonus,
            "trauma_triggered": bool(overflow),
            "trauma_result": trauma_info,
            "note": f"{helper} assists {target}: helper 1 stress, target +1d next roll",
        }
        self.state.log_tool("assist", {"helper": helper, "target": target}, res)
        return res

    def devil_bargain(self, character: str, description: str) -> dict[str, Any]:
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        if ch._devil_bargain:
            res = {
                "valid": False,
                "reason": "Devil's Bargain already set for this roll (max 1, cannot stack with push-dice)",
            }
            self.state.log_tool("devil_bargain", {"character": character, "description": description}, res)
            return res
        if ch._push_bonus == "dice":
            res = {
                "valid": False,
                "reason": "Cannot take Devil's Bargain after pushing for +1d (choose one). Push for +1 effect is allowed with Devil's Bargain.",
            }
            self.state.log_tool("devil_bargain", {"character": character, "description": description}, res)
            return res
        ch._devil_bargain = description
        res = {
            "valid": True,
            "character": character,
            "description": description,
            "note": "Devil's Bargain: +1d, complication occurs regardless of outcome. GM will tick a clock or add heat.",
        }
        self.state.log_tool("devil_bargain", {"character": character, "description": description}, res)
        return res

    # ------------------------------------------------------------------
    # Core rolls
    # ------------------------------------------------------------------
    def action_roll(
        self,
        character: str,
        action: str | None = None,
        position: str | None = None,
        effect: str | None = None,
        clock: str | None = None,
    ) -> dict[str, Any]:
        """Authoritative action roll. Requires prior set_position_and_effect unless position/effect supplied."""
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        # resolve action/position/effect: prefer explicit params, fall back to pending
        from .models import _norm_action

        if action:
            try:
                norm_action = _norm_action(action)
            except ValueError as e:
                res = {"valid": False, "reason": str(e)}
                self.state.log_tool("action_roll", {"character": character, "action": action}, res)
                return res
        else:
            norm_action = ch._pending_action
            if not norm_action:
                res = {
                    "valid": False,
                    "reason": "No action specified and no pending set_position_and_effect. Call set_position_and_effect first.",
                }
                self.state.log_tool("action_roll", {"character": character}, res)
                return res
        pos = position.lower() if position else ch._pending_position
        eff = effect.lower() if effect else ch._pending_effect
        if not pos or not eff:
            res = {
                "valid": False,
                "reason": "Position/effect not set. Call set_position_and_effect(character, action, position, effect) before action_roll.",
                "hint": "Example: set_position_and_effect(character='Silas', action='Prowl', position='desperate', effect='limited')",
            }
            self.state.log_tool("action_roll", {"character": character, "action": norm_action}, res)
            return res
        if pos not in {p.value for p in Position}:
            raise ValueError(f"position must be controlled/risky/desperate, got {pos}")
        if eff not in {e.value for e in Effect}:
            raise ValueError(f"effect must be {list(EFFECT_TICKS)}, got {eff}")
        # sync pending if explicit passed
        ch._pending_action = norm_action
        ch._pending_position = pos
        ch._pending_effect = eff

        rating = ch.action_rating(norm_action)
        bonus = 0
        devil = bool(ch._devil_bargain)
        pushed_dice = ch._push_bonus == "dice"
        pushed_effect = ch._push_bonus == "effect"
        assist = ch._assist_bonus
        if assist:
            bonus += 1
        if pushed_dice or devil:
            bonus += 1
        # Devil's Bargain and push-dice are mutually exclusive already enforced; if both set, devils wins? but gate prevents
        # Also note push for effect doesn't give dice
        pool = rating + bonus

        # effect bump if pushed for effect
        effective_effect = eff
        if pushed_effect:
            # +1 effect tier
            order = ["zero", "limited", "standard", "great", "extreme"]
            try:
                idx = order.index(eff)
                effective_effect = order[min(len(order) - 1, idx + 1)]
            except ValueError:
                effective_effect = eff

        result = roll_action(pool)
        outcome = result["outcome"]  # critical/success/partial/failure
        critical = result["critical"]
        highest = result["highest"]

        # consequence severity per table
        consequence: list[str] = []
        if outcome == "success" or outcome == "critical":
            # 6 / critical: no consequence (except devil's bargain still happens)
            consequence = []
        elif outcome == "partial":
            consequence = list(CONSEQUENCE_TABLE[pos]["partial"])
        else:  # failure
            consequence = list(CONSEQUENCE_TABLE[pos]["failure"])

        # devil's bargain complication independent of outcome
        devil_note = None
        if devil:
            devil_note = f"Devil's Bargain triggers: '{ch._devil_bargain}' (ticks complication clock or +1 heat) regardless of outcome."

        # ticks for clock
        ticks = 0
        if clock and clock not in self.state.clocks:
            self.state.set_clock(clock, segments=6)
        if outcome in ("critical", "success"):
            # success gives full effect ticks; critical gives +1
            ticks = _effect_ticks(effective_effect, critical)
        elif outcome == "partial":
            # partial gives reduced effect? SRD: partial is success but with reduced effect or consequence — for clocks we give half ticks? But for tool we still give full effect then note reduced
            # To reflect "reduced effect" we give ticks but flag reduced
            ticks = _effect_ticks(effective_effect, False)
            # on partial we note reduced effect as part of consequence; ticks may be reduced by 1 if consequence includes reduced effect? We'll keep full but narrate reduced
            # Optional: if consequence includes reduced effect, subtract 1 (min 0)
            ticks = max(0, ticks - 1) if "reduced effect" in " ".join(consequence) else ticks
            if critical:
                # partial cannot be critical; but just in case
                ticks = _effect_ticks(effective_effect, True)
        else:
            ticks = 0
            # desperate failure on great effect still 0; caller narrates lost opportunity

        if clock and ticks > 0:
            before = self.state.clocks[clock].ticks
            self.state.tick_clock(clock, ticks)
            after = self.state.clocks[clock].ticks
            clock_info = {
                "clock": clock,
                "ticks": ticks,
                "before": before,
                "after": after,
                "completed": self.state.clocks[clock].completed,
            }
        else:
            clock_info = {"clock": clock, "ticks": ticks} if clock else None

        # heat/entanglement hint for devil's bargain or failure (GM decides, but we expose metric)
        heat_delta = 0
        if devil:
            heat_delta += 1
        if outcome == "failure" and pos == "desperate":
            heat_delta += 1  # many desperate failures generate heat in Blades (optional)

        payload = {
            "valid": True,
            "character": character,
            "action": norm_action,
            "position": pos,
            "effect": effective_effect,
            "raw_effect": eff,
            "pool": pool,
            "rating": rating,
            "bonus_dice": bonus,
            "assist": bool(assist),
            "push": ch._push_bonus,
            "devil_bargain": ch._devil_bargain,
            "highest": highest,
            "rolls": result["rolls"],
            "outcome": outcome,
            "critical": critical,
            "consequence": consequence,
            "consequence_severity": pos,
            "devil_bargain_note": devil_note,
            "ticks": ticks,
            "clock": clock_info,
            "heat_delta": heat_delta,
            "requires_resistance": len(consequence) > 0,
            "resistance_prompt": f"If you fail ({outcome}) at {pos}/{effective_effect}, the GM inflicts: {', '.join(consequence) if consequence else 'no consequence, but Devil Bargain still applies'}. You may call resistance_roll(character, attribute) to reduce/avoid (cost 6−high stress), or use_armor to negate, or accept the consequence.",
        }
        self.state.log_tool(
            "action_roll",
            {
                "character": character,
                "action": norm_action,
                "position": pos,
                "effect": eff,
                "clock": clock,
            },
            payload,
        )
        # clear per-roll gates after roll (push/assist/devil consumed)
        ch._assist_bonus = 0
        ch._push_bonus = None
        ch._devil_bargain = None
        # keep pending position/effect for maybe resistance context? but clear after roll to force re-negotiation next time
        ch._pending_position = None
        ch._pending_effect = None
        ch._pending_action = None
        return payload

    def resistance_roll(self, character: str, attribute: str) -> dict[str, Any]:
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        attr = attribute.capitalize()
        if attr not in ["Insight", "Prowess", "Resolve"]:
            raise ValueError(f"attribute must be Insight/Prowess/Resolve, got {attribute}")
        rating = ch.attr_rating(attr)
        res = roll_resistance(rating)
        cost = res["stress_cost"]
        clears = res["clears_one"]
        before = ch.stress
        # apply stress (and trauma gate)
        # detect overflow
        if before + cost > ch.stress_max:
            # per SRD, you take trauma and clear stress to 0 then trauma triggers; but resistance costing would overflow => trauma
            from .models import TRAUMA_NAMES

            available = [t for t in TRAUMA_NAMES if t not in ch.trauma]
            chosen = available[0] if available else "Trauma"
            trauma_res = self.state.add_trauma(character, chosen)
            payload = {
                "character": character,
                "attribute": attr,
                "rating": rating,
                "rolls": res["rolls"],
                "highest": res["highest"],
                "critical": res["critical"],
                "stress_cost": cost,
                "stress_before": before,
                "stress_after": ch.stress,
                "clears_one": clears,
                "trauma_triggered": True,
                "trauma": list(ch.trauma),
                "trauma_result": trauma_res,
                "note": f"Resisted with {attr} ({rating}d): cost {cost} stress, but exceeded max → trauma '{chosen}' (stress cleared to 0). {'Critical: would clear 1 stress (already cleared).' if clears else ''} GM reduces consequence per resistance (harm down one level / ticks fewer).",
            }
        else:
            if clears:
                # critical clears 1 stress after cost
                ch.stress = max(0, before + cost - 1)
                cost_after_clear = ch.stress - before
            else:
                ch.stress = max(0, before + cost)
                cost_after_clear = cost
            # use state.mark_stress for consistency? we already mutated; log accordingly
            payload = {
                "character": character,
                "attribute": attr,
                "rating": rating,
                "rolls": res["rolls"],
                "highest": res["highest"],
                "critical": res["critical"],
                "stress_cost": cost,
                "stress_after_clear": ch.stress if clears else None,
                "applied_cost": cost_after_clear,
                "stress_before": before,
                "stress_after": ch.stress,
                "clears_one": clears,
                "trauma_triggered": False,
                "note": f"Resisted with {attr} ({rating}d): 6−{res['highest']} = {cost} stress{f' (critical: clear 1 → net {cost_after_clear})' if clears else ''}. Consequence reduced or avoided (GM decides).",
            }
        self.state.log_tool("resistance_roll", {"character": character, "attribute": attr}, payload)
        return payload

    def mark_stress(self, name: str, delta: int) -> dict[str, Any]:
        res = self.state.mark_stress(name, int(delta))
        self.state.log_tool("mark_stress", {"name": name, "delta": delta}, res)
        return res

    def clear_stress(self, name: str, amount: int | None = None) -> dict[str, Any]:
        ch = self.state.get_character(name)
        if not ch:
            raise KeyError(name)
        if amount is None:
            ch.stress = 0
        else:
            ch.stress = max(0, ch.stress - int(amount))
        res = {"name": name, "stress": ch.stress, "max": ch.stress_max}
        self.state.log_tool("clear_stress", {"name": name, "amount": amount}, res)
        return res

    def mark_trauma(self, name: str, trauma: str) -> dict[str, Any]:
        res = self.state.add_trauma(name, trauma)
        self.state.log_tool("mark_trauma", {"name": name, "trauma": trauma}, res)
        return res

    def apply_harm(self, target: str, level: int, name: str, description: str = "") -> dict[str, Any]:
        res = self.state.apply_harm(target, int(level), name, description)
        self.state.log_tool("apply_harm", {"target": target, "level": level, "name": name}, res)
        return res

    def heal_harm(self, target: str, harm_name: str) -> dict[str, Any]:
        res = self.state.heal_harm(target, harm_name)
        self.state.log_tool("heal_harm", {"target": target, "harm_name": harm_name}, res)
        return res

    def use_armor(self, character: str, kind: str = "armor") -> dict[str, Any]:
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        kind = kind.lower()
        if kind not in ("armor", "heavy"):
            raise ValueError("kind must be armor or heavy")
        if kind == "armor" and not ch.armor:
            # mark as used? In Blades armor is a box you mark; simplified we treat bool available
            # Initially armor available if load includes it; we expose it as toggle
            # For demo we assume if false means already used
            res = {"valid": False, "reason": "armor already marked (used) or not carried"}
            self.state.log_tool("use_armor", {"character": character, "kind": kind}, res)
            return res
        if kind == "heavy" and not ch.heavy:
            res = {"valid": False, "reason": "heavy armor not carried or already marked"}
            self.state.log_tool("use_armor", {"character": character, "kind": kind}, res)
            return res
        # mark it as used (consume)
        if kind == "armor":
            ch.armor = False
        else:
            ch.heavy = False
        res = {
            "valid": True,
            "character": character,
            "kind": kind,
            "note": "Armor marked to reduce/avoid consequence (no stress cost). Restored on next load selection.",
        }
        self.state.log_tool("use_armor", {"character": character, "kind": kind}, res)
        return res

    def regain_armor(self, character: str) -> dict[str, Any]:
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        ch.armor = True
        ch.heavy = True
        res = {"character": character, "armor": True, "heavy": True}
        self.state.log_tool("regain_armor", {"character": character}, res)
        return res

    def indulge_vice(self, character: str) -> dict[str, Any]:
        """Vice indulgence — roll to clear stress. SRD: clear = highest of vice roll; overindulge if you clear > need? Simplified."""
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        # fortune-like roll: use Resolve attribute? Actually vice uses specific action? Simplified: fortune with 1d6 + vice bond?
        # We'll roll_resistance with Resolve? But per SRD vice roll is attribute? We'll do fortune 1d6 + 1 if trauma? Simple: roll 1d6
        res = roll_fortune(1)
        cleared = res["highest"]
        # critical clears 3+? But just use highest
        before = ch.stress
        ch.stress = max(0, ch.stress - cleared)
        overindulge = cleared > before > 0  # narrative flag
        payload = {
            "character": character,
            "rolls": res["rolls"],
            "highest": res["highest"],
            "critical": res["critical"],
            "cleared": cleared,
            "stress_before": before,
            "stress_after": ch.stress,
            "overindulge": overindulge,
            "note": f"Vice ({ch.vice}): cleared {cleared} stress {' (overindulge!)' if overindulge else ''}",
        }
        self.state.log_tool("indulge_vice", {"character": character}, payload)
        return payload

    def engage_roll(self, plan: str, detail: str, dice: int = 1) -> dict[str, Any]:
        """Engagement fortune roll — determines starting position."""
        # dice baseline from plan quality; caller provides; fortune tier maps to position
        res = roll_fortune(int(dice))
        tier = res["tier"]
        if tier == "critical" or tier == "excellent":
            position = "controlled"
        elif tier == "good":
            position = "risky"
        else:
            position = "desperate"
        self.state._engagement_position = position
        payload = {
            "plan": plan,
            "detail": detail,
            "dice": dice,
            "rolls": res["rolls"],
            "highest": res["highest"],
            "tier": tier,
            "starting_position": position,
            "note": f"Engagement: {tier} ({res['rolls']}) → start at {position} position",
        }
        self.state.log_tool("engage_roll", {"plan": plan, "detail": detail, "dice": dice}, payload)
        return payload

    def gather_information(self, character: str, action: str, position: str = "risky") -> dict[str, Any]:
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        from .models import _norm_action

        norm_action = _norm_action(action)
        rating = ch.action_rating(norm_action)
        # info roll is action roll without effect? Use fortune-ish: roll pool, but apply same outcome semantics (info quality)
        res = roll_action(rating)
        quality = {
            "critical": "excellent info (extra detail)",
            "success": "good info",
            "partial": "mixed info (partial + complication)",
            "failure": "poor info / danger",
        }[res["outcome"]]
        consequence = []
        if res["outcome"] == "partial":
            consequence = ["complication / start 6-clock", "reduce info quality"]
        elif res["outcome"] == "failure":
            consequence = ["danger / tick danger clock", "false info"]
        payload = {
            "character": character,
            "action": norm_action,
            "position": position,
            "rolls": res["rolls"],
            "highest": res["highest"],
            "outcome": res["outcome"],
            "critical": res["critical"],
            "quality": quality,
            "consequence": consequence,
        }
        self.state.log_tool(
            "gather_information", {"character": character, "action": norm_action, "position": position}, payload
        )
        return payload

    def flashback(self, character: str, stress_cost: int, description: str) -> dict[str, Any]:
        ch = self.state.get_character(character)
        if not ch:
            raise KeyError(character)
        cost = max(0, int(stress_cost))
        # flashback cost = GM sets 0-2 stress (sometimes coin); we enforce via param
        before = ch.stress
        if before + cost > ch.stress_max:
            from .models import TRAUMA_NAMES

            available = [t for t in TRAUMA_NAMES if t not in ch.trauma]
            chosen = available[0] if available else "Trauma"
            trauma_res = self.state.add_trauma(character, chosen)
            payload = {
                "character": character,
                "description": description,
                "stress_cost": cost,
                "stress_before": before,
                "stress_after": ch.stress,
                "trauma_triggered": True,
                "trauma": list(ch.trauma),
                "trauma_result": trauma_res,
            }
        else:
            self.state.mark_stress(character, cost)
            payload = {
                "character": character,
                "description": description,
                "stress_cost": cost,
                "stress_before": before,
                "stress_after": ch.stress,
                "trauma_triggered": False,
            }
        self.state.log_tool(
            "flashback", {"character": character, "stress_cost": cost, "description": description}, payload
        )
        return payload

    def roll_initiative(self) -> list[dict[str, Any]]:
        res = self.state.roll_initiative()
        self.state.log_tool("roll_initiative", {}, res)
        return res

    def end_turn(self, character: str) -> dict[str, Any]:
        # clear any leftover per-roll gates if not consumed (should have been cleared by action_roll)
        ch = self.state.get_character(character)
        if ch:
            # don't clear pending if they never rolled? Keep for next? But strict recipe says re-negotiate each roll, so we keep until roll
            pass
        res = {"character": character, "note": "end of turn — renew position/effect negotiation next action"}
        self.state.log_tool("end_turn", {"character": character}, res)
        return res

    def print_trauma_log(self) -> dict[str, Any]:
        res = {"log": list(self.state.trauma_log), "harm_log": list(self.state.harm_log)}
        self.state.log_tool("print_trauma_log", {}, res)
        return res

    def print_death_point(self) -> dict[str, Any]:  # compat
        return self.print_trauma_log()

    def dispatch(self, name: str, args: dict[str, Any]) -> Any:
        fn = getattr(self, name, None)
        if not fn:
            raise ValueError(f"Unknown tool {name}")
        return fn(**args)

    # ------------------------------------------------------------------
    # Schemas
    # ------------------------------------------------------------------
    def tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_names_of_all_players",
                    "description": "List scoundrel names (PCs)",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_names_of_all_monsters",
                    "description": "List opposition/crew threat names",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_character",
                    "description": "Get Blades sheet: playbook, actions 0-4, stress/trauma, harm, vice, load/armor",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_stress",
                    "description": "Get stress and trauma",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_harm",
                    "description": "Get harm entries",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_clock",
                    "description": "Check progress clock ticks/segments/completed",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_actions",
                    "description": "List 12 actions and attribute grouping",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "visualize_clocks",
                    "description": "Visualize all clocks as ascii bars",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_valid_attack_line",
                    "description": "LoS between two characters (grid+height)",
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
                    "name": "visualize_map",
                    "description": "ASCII map (#=wall, upper=PC, lower=threat)",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "set_position_and_effect",
                    "description": "Gate: agree position (controlled/risky/desperate) and effect (limited/standard/great/zero/extreme) before action_roll. Required.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "action": {
                                "type": "string",
                                "description": "One of Hunt,Study,Survey,Tinker,Finesse,Prowl,Skirmish,Wreck,Attune,Command,Consort,Sway",
                            },
                            "position": {"type": "string", "enum": ["controlled", "risky", "desperate"]},
                            "effect": {"type": "string", "enum": ["limited", "standard", "great", "zero", "extreme"]},
                        },
                        "required": ["character", "action", "position", "effect"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "set_clock",
                    "description": "Create or update a progress clock (4/6/8 segments)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "segments": {"type": "integer"},
                            "kind": {"type": "string", "enum": ["obstacle", "danger", "project", "healing", "turf"]},
                        },
                        "required": ["name", "segments"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tick_clock",
                    "description": "Add ticks to a clock (1-5; completes at segments)",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}, "ticks": {"type": "integer"}},
                        "required": ["name", "ticks"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "push_yourself",
                    "description": "Push yourself: 2 stress for +1d OR +1 effect (choose one per roll; before action_roll)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "bonus": {"type": "string", "enum": ["dice", "effect"]},
                        },
                        "required": ["character"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "assist",
                    "description": "Helper takes 1 stress to give target +1d next action_roll",
                    "parameters": {
                        "type": "object",
                        "properties": {"helper": {"type": "string"}, "target": {"type": "string"}},
                        "required": ["helper", "target"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "devil_bargain",
                    "description": "Accept Devil's Bargain (+1d, complication occurs regardless of outcome; cannot stack with push-dice)",
                    "parameters": {
                        "type": "object",
                        "properties": {"character": {"type": "string"}, "description": {"type": "string"}},
                        "required": ["character", "description"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "action_roll",
                    "description": "Authoritative action roll: pool = action rating + bonus dice (assist/push/devil). Zero dice = 2d6 keep lowest. Highest die gives critical/success(6)/partial(4-5)/failure(1-3). Requires prior set_position_and_effect. Ticks clock per effect (limited1/standard2/great3, critical+1). Devil Bargain ticks regardless.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "action": {"type": "string"},
                            "position": {"type": "string", "enum": ["controlled", "risky", "desperate"]},
                            "effect": {"type": "string", "enum": ["limited", "standard", "great", "zero", "extreme"]},
                            "clock": {"type": "string", "description": "Optional progress clock to tick on success"},
                        },
                        "required": ["character"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "resistance_roll",
                    "description": "Resist consequence: roll attribute (Insight/Prowess/Resolve). Stress = 6−high (crit clears 1). Always reduces/avoides but costs stress.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "attribute": {"type": "string", "enum": ["Insight", "Prowess", "Resolve"]},
                        },
                        "required": ["character", "attribute"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mark_stress",
                    "description": "Mark stress by delta (positive = add)",
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
                    "name": "clear_stress",
                    "description": "Clear stress (all or amount)",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}, "amount": {"type": "integer"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mark_trauma",
                    "description": "Mark a trauma (4 triggers retirement; stress cleared to 0)",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}, "trauma": {"type": "string"}},
                        "required": ["name", "trauma"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "apply_harm",
                    "description": "Apply harm level 1-4 (fatal) by name",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {"type": "string"},
                            "level": {"type": "integer"},
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["target", "level", "name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "heal_harm",
                    "description": "Remove a harm entry by name (healing clock full)",
                    "parameters": {
                        "type": "object",
                        "properties": {"target": {"type": "string"}, "harm_name": {"type": "string"}},
                        "required": ["target", "harm_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "use_armor",
                    "description": "Mark armor/heavy to avoid/reduce consequence (no stress, once per score until restored)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "kind": {"type": "string", "enum": ["armor", "heavy"]},
                        },
                        "required": ["character"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "regain_armor",
                    "description": "Restore armor/heavy boxes (on load selection)",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "indulge_vice",
                    "description": "Indulge vice to clear stress (fortune; overindulge risk)",
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
                    "name": "engage_roll",
                    "description": "Fortune engagement roll (plan/detail) → starting position (controlled/risky/desperate)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "plan": {"type": "string"},
                            "detail": {"type": "string"},
                            "dice": {"type": "integer"},
                        },
                        "required": ["plan", "detail"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gather_information",
                    "description": "Information roll: action + position → info quality + complication",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "action": {"type": "string"},
                            "position": {"type": "string"},
                        },
                        "required": ["character", "action"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "flashback",
                    "description": "Flashback preparation (0-2 stress, GM sets cost)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "stress_cost": {"type": "integer"},
                            "description": {"type": "string"},
                        },
                        "required": ["character", "stress_cost", "description"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "roll_initiative",
                    "description": "Roll score turn order (fortune 1d6 per participant)",
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
                    "name": "print_trauma_log",
                    "description": "Print trauma and harm logs",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
        ]


# ---------------------------------------------------------------------------
# Campaign-level wrapper
# ---------------------------------------------------------------------------


class BladesCampaignTools:
    """Wraps BladesTools + BladesCampaignState helpers."""

    def __init__(self, cstate: BladesCampaignState):
        self.cstate = cstate
        self.inner_tools = BladesTools(cstate.inner)

    def __getattr__(self, name: str) -> Any:
        if hasattr(self.inner_tools, name):
            return getattr(self.inner_tools, name)
        raise AttributeError(name)

    def dispatch(self, name: str, args: dict[str, Any]) -> Any:
        if hasattr(self, name) and name in {
            "long_rest",
            "indulge_vice",
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
        # Blades downtime: vice + recovery; we map long_rest to indulge_vice for one or all
        if name:
            res = self.inner_tools.indulge_vice(name)
            self.cstate.inner.log_tool("long_rest", {"name": name}, res)
            self.cstate.checkpoint()
            return res
        out: dict[str, Any] = {}
        for p in list(self.cstate.inner.players.keys()):
            out[p] = self.inner_tools.indulge_vice(p)
        self.cstate.inner.log_tool("long_rest", {"name": name}, out)
        self.cstate.checkpoint()
        return out

    def indulge_vice(self, character: str) -> dict[str, Any]:
        res = self.inner_tools.indulge_vice(character)
        self.cstate.inner.log_tool("indulge_vice", {"character": character}, res)
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
        loaded = BladesCampaignState.load(path)
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
                    "description": "Downtime: indulge vice to clear stress (one or all scoundrels)",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "indulge_vice",
                    "description": "Indulge vice to clear stress (fortune roll)",
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
                    "name": "checkpoint",
                    "description": "Snapshot current score to bounded history",
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
