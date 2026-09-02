"""Simulation framework — generation + turn loop (Fig. 1)."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from .agents import (  # Tau-native; DMAgent/PlayerAgent shimmed
    LLMClient,
    heuristic_player_turn,
)
from .mapgen import make_indoor_map, make_outdoor_map
from .models import ALL_WEAPONS, MONSTER_TEMPLATES, SPELLS_NORM, Character
from .state import GameState
from .tools import Tools

# ------------------------------------------------------------------
# Generation
# ------------------------------------------------------------------


def _random_stats(tier: str = "medium") -> dict:
    """Generate stats by tier. Low: 8-12, medium: 10-16, high: 14-18."""
    rng = random
    if tier == "low":
        low, high = 8, 12
    elif tier == "high":
        low, high = 14, 18
    else:
        low, high = 10, 16
    return {
        "strength": rng.randint(low, high),
        "dexterity": rng.randint(low, high),
        "constitution": rng.randint(low, high),
        "intelligence": rng.randint(low, high),
        "wisdom": rng.randint(low, high),
        "charisma": rng.randint(low, high),
    }


def create_player(name: str, char_class: str, tier: str = "medium", level: int = 1) -> Character:
    stats = _random_stats(tier)
    # weapon choice based on class
    if char_class in ("fighter", "paladin", "barbarian"):
        weap = "longsword"
        hp = 12 + (stats["constitution"] - 10) // 2
    elif char_class in ("rogue", "ranger"):
        weap = "short bow"
        hp = 10 + (stats["constitution"] - 10) // 2
    elif char_class in ("wizard", "sorcerer", "warlock"):
        weap = "dagger"
        hp = 6 + (stats["constitution"] - 10) // 2
    else:
        weap = "club"
        hp = 8 + (stats["constitution"] - 10) // 2
    # spell list for casters
    spells = []
    if char_class in (
        "wizard",
        "sorcerer",
        "warlock",
        "cleric",
        "druid",
        "bard",
        "paladin",
        "ranger",
    ):
        pool = list(SPELLS_NORM.keys())
        spells = random.sample(pool, k=min(3, len(pool)))
    slots = {1: 2} if spells else {}
    ac = 10 + (stats["dexterity"] - 10) // 2 + (2 if char_class in ("fighter", "paladin") else 0)
    return Character(
        name=name,
        max_hp=max(6, hp),
        hp=max(6, hp),
        ac=ac,
        char_class=char_class,
        equipped_mainhand=weap,
        inventory=[weap],
        spell_list=spells,
        spell_slots=dict(slots),
        spell_slots_max=dict(slots),
        **stats,
    )


def create_monster(name: str, template: str = "goblin") -> Character:
    tpl = MONSTER_TEMPLATES.get(template, MONSTER_TEMPLATES["goblin"])
    return Character(
        name=name,
        max_hp=tpl["max_hp"],
        hp=tpl["max_hp"],
        ac=tpl["ac"],
        char_class="monster",
        equipped_mainhand=tpl["weapon"],
        inventory=[tpl["weapon"]],
        monster_type=tpl["type"],
        size=tpl["size"],
        strength=tpl["str"],
        dexterity=tpl["dex"],
        constitution=tpl["con"],
        intelligence=tpl["int"],
        wisdom=tpl["wis"],
        charisma=tpl["cha"],
        is_player=False,
    )


def initialize_encounter(
    state: GameState,
    players: list[Character],
    monsters: list[Character],
    map_kind: str = "outdoor",
    seed: int = 0,
):
    # map
    if map_kind == "indoor":
        cells = make_indoor_map(seed)
    else:
        cells = make_outdoor_map(seed)
    state.set_map(cells)
    w, h = state.map_size()
    # Place teams near center at tactical distance ~25-40ft (5-8 cells) for faster engagement
    # Players cluster around (w//2 -3, h//2), monsters opposite
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
    return state


# Scenario save/load (27 scenarios design 3x3x3)
def generate_scenarios(seed: int = 42, out_dir: Path | str = "scenarios") -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    groups = [
        ["fighter", "wizard", "cleric", "rogue"],
        ["ranger", "paladin", "bard", "druid"],
        ["barbarian", "monk", "sorcerer", "warlock"],
    ]
    tiers = ["low", "medium", "high"]
    monster_sets = [
        {
            "name": "Goblin Ambush",
            "mobs": ["goblin", "goblin", "goblin", "goblin"],
            "map": "outdoor",
        },
        {
            "name": "Kennel",
            "mobs": ["wolf", "wolf", "goblin", "goblin"],
            "map": "indoor",
        },
        {
            "name": "Klarg's Cave",
            "mobs": ["klarg", "goblin", "goblin", "wolf"],
            "map": "indoor",
        },
    ]
    paths = []
    sid = 0
    for g in groups:
        for tier in tiers:
            for ms in monster_sets:
                sid += 1
                data = {
                    "scenario_id": sid,
                    "seed": seed + sid,
                    "group": g,
                    "tier": tier,
                    "monster_set": ms,
                }
                p = out / f"scenario_{sid:02d}.json"
                with open(p, "w") as f:
                    json.dump(data, f, indent=2)
                paths.append(p)
    return paths


def load_scenario(path: Path | str) -> tuple[GameState, Tools]:
    with open(path) as f:
        spec = json.load(f)
    seed = spec.get("seed", 0)
    random.seed(seed)
    state = GameState(seed_val=seed)
    players = [
        create_player(f"P{i + 1}_{cls}", cls, tier=spec.get("tier", "medium")) for i, cls in enumerate(spec["group"])
    ]
    mobs = spec["monster_set"]
    monsters = [create_monster(f"M{i + 1}_{tpl}", tpl) for i, tpl in enumerate(mobs["mobs"])]
    initialize_encounter(state, players, monsters, map_kind=mobs["map"], seed=seed)
    tools = Tools(state)
    return state, tools


# ------------------------------------------------------------------
# Simulation Loop
# ------------------------------------------------------------------


class Simulation:
    def __init__(
        self,
        state: GameState,
        tools: Tools,
        llm: LLMClient | None = None,
        use_heuristic: bool = True,
        max_turns: int = 10,
    ):
        self.state = state
        self.tools = tools
        # llm is now a TauLLM (tau provider) — still constructed via LLMClient alias for CLI compat
        self.llm = llm
        if llm is None and not use_heuristic:
            # create default Tau provider (LMStudio) if caller asked for LLM without providing one
            try:
                self.llm = LLMClient()
            except Exception:
                self.llm = None
                use_heuristic = True
        self.use_heuristic = use_heuristic
        self.max_turns = max_turns
        # per-player harnesses are created on demand; keep dict for backwards compat
        self.player_agents: dict[str, Any] = {}
        for name, ch in list(state.players.items()):
            self.player_agents[name] = {"name": name, "class": ch.char_class}

    def _monster_turn(self, name: str):
        """DM controls monster — query, move, validate, resolve, bookkeep."""
        ch = self.state.get_character(name)
        if not ch or not ch.alive:
            return
        # 1. query side
        self.tools.check_side(name)
        # 2. choose target: nearest alive player (paper's monster is tactical but simple nearest for demo)
        alive_players = [(n, c) for n, c in self.state.players.items() if c.alive]
        if not alive_players:
            return
        # nearest by distance, fall back to lowest HP if distance tie
        best = None
        best_d = 1e9
        for n, _ in alive_players:
            try:
                d = self.state.distance_feet(name, n)
                if d < best_d:
                    best_d = d
                    best = n
            except:
                pass
        target = best or min(alive_players, key=lambda x: x[1].hp)[0]
        # 3. gates — handle LoS and melee range
        # If melee, ensure within 5ft; otherwise close distance
        weap = ch.equipped_mainhand
        w = ALL_WEAPONS.get(weap.lower()) if weap else None
        is_melee = w.category.value == "melee" if w else True
        # First check distance: if melee and too far, move greedily up to speed
        dist = self.state.distance_feet(name, target)
        if is_melee and dist > 5:
            # move towards target stepwise using available speed
            cur = self.state.get_pos(name)
            tgt = self.state.get_pos(target)
            # opportunity checks before leaving
            for pn, pc in list(self.state.players.items()):
                pos_pn = self.state.get_pos(pn)
                if pc.alive and cur and pos_pn and max(abs(cur[0] - pos_pn[0]), abs(cur[1] - pos_pn[1])) <= 1:
                    self.tools.opportunity_attack(name, pn)
            # step loop: move up to 6 cells (30ft)
            steps = min(6, int(dist // 5))
            for _ in range(steps):
                cur = self.state.get_pos(name)
                tgt = self.state.get_pos(target)
                if not cur or not tgt:
                    break
                if max(abs(cur[0] - tgt[0]), abs(cur[1] - tgt[1])) <= 1:
                    break
                nx = cur[0] + (1 if tgt[0] > cur[0] else -1 if tgt[0] < cur[0] else 0)
                ny = cur[1] + (1 if tgt[1] > cur[1] else -1 if tgt[1] < cur[1] else 0)
                res = self.tools.move(name, nx, ny)
                if not res.get("valid"):
                    # try dash if blocked or out of speed
                    if ch.speed_remaining < 5:
                        self.tools.dash(name)
                        continue
                    break
                # after move check if now in range
                if max(abs(nx - tgt[0]), abs(ny - tgt[1])) <= 1:
                    break
        los = self.tools.check_valid_attack_line(name, target)
        if not los:
            # try one more lateral move to gain LoS
            cur = self.state.get_pos(name)
            tgt = self.state.get_pos(target)
            if cur and tgt:
                # try perpendicular offset
                nx = cur[0] + (1 if cur[0] <= tgt[0] else -1)
                ny = cur[1]
                self.tools.move(name, nx, ny)
                los = self.tools.check_valid_attack_line(name, target)
        # 4. resolve
        if los:
            # re-evaluate distance after moves
            dist = self.state.distance_feet(name, target)
            if is_melee and dist > 5:
                self.state.add_transcript(
                    f"{name} closes but still {dist:.0f}ft from {target} — out of melee range, tries ranged or holds"
                )
                # if has no ranged, skip attack
            else:
                mod = 3
                try:
                    if w:
                        stat = "dexterity" if w.category.value == "ranged" else "strength"
                        mod = ch.ability_mod(stat) + ch.pb
                except:
                    pass
                atk = self.tools.roll_attack(
                    name,
                    target,
                    roll_type="normal",
                    ac=10,
                    modifier=mod,
                    weapon_name=weap,
                    action_cost=1,
                )
                if atk.get("out_of_range"):
                    self.state.add_transcript(f"{name} cannot reach {target} (out_of_range) — moves next turn")
                else:
                    self.state.add_transcript(
                        f"{name} (monster) attacks {target}: roll {atk.get('roll')} vs AC {atk.get('ac')} -> {'HIT' if atk.get('success') else 'MISS'}"
                    )
                    if atk.get("success"):
                        dice_expr = w.damage_dice if w else "1d6"
                        dmg = self.tools.roll_dmg(
                            name,
                            target,
                            dice_expr,
                            w.damage_type.value if w else "slashing",
                            is_critical=atk.get("critical", False),
                        )
                        true_dmg = dmg["damage"]
                        resists = self.tools.check_resist(target)
                        for e in resists:
                            if e["damage_type"] == dmg["damage_type"]:
                                if e["kind"] == "resist":
                                    true_dmg //= 2
                                elif e["kind"] == "immune":
                                    true_dmg = 0
                                elif e["kind"] == "vulner":
                                    true_dmg *= 2
                        self.tools.update_hp(target, -true_dmg)
                        self.state.add_transcript(
                            f"  Damage {true_dmg} ({dmg['damage_type']}) to {target} HP now {self.state.check_hp(target)}"
                        )
        else:
            self.state.add_transcript(f"{name} cannot see {target}, holds position")
        # 5. bookkeep
        self._end_of_turn_bookkeeping(name)

    def _player_turn(self, name: str):
        ch = self.state.get_character(name)
        if not ch or not ch.alive:
            return
        self.tools.check_side(name)
        if self.use_heuristic or not self.llm:
            line = heuristic_player_turn(name, self.tools, self.state)
            self.state.add_transcript(line)
        else:
            # Tau-native player turn — fully in-process, no subprocess
            try:
                from .agents import run_tau_player_turn_sync

                # llm is TauLLM holding provider + model
                provider = getattr(self.llm, "provider", None) or getattr(self.llm, "_provider", None)
                model = getattr(self.llm, "model", "qwen3.6-35b-a3b-mtp")
                if provider is None:
                    # fallback to constructing provider from base_url if llm was bare
                    from .agents import make_tau_provider

                    provider = make_tau_provider(
                        getattr(self.llm, "base_url", "http://127.0.0.1:1234/v1"),
                        getattr(self.llm, "api_key", "lm-studio"),
                    )
                line = run_tau_player_turn_sync(
                    player_name=name,
                    player_class=ch.char_class,
                    tools=self.tools,
                    state=self.state,
                    provider=provider,
                    model=model,
                    max_turns=6,
                )
                self.state.add_transcript(line)
            except Exception as e:
                # Keep simulation alive; log and fall back to heuristic for this turn
                self.state.add_transcript(f"{name}: [tau fallback {e}] <DM/>")
                line = heuristic_player_turn(name, self.tools, self.state)
                self.state.add_transcript(line)
        self._end_of_turn_bookkeeping(name)

    def _end_of_turn_bookkeeping(self, name: str):
        # Paper's 6 things at end of each turn
        self.tools.reset_resources(name)
        self.tools.reset_speed(name)
        # check buffs etc. — decrement durations
        ch = self.state.get_character(name)
        if ch:
            # buff expiry
            new_buffs = []
            for b in ch.buffs:
                if b.remaining_turns > 0:
                    b.remaining_turns -= 1
                    if b.remaining_turns > 0:
                        new_buffs.append(b)
                elif b.remaining_turns == -1:
                    new_buffs.append(b)
            ch.buffs = new_buffs
            # resists expiry
            new_r = []
            for e in ch.resists:
                if e.remaining_turns > 0:
                    e.remaining_turns -= 1
                    if e.remaining_turns != 0:
                        new_r.append(e)
                elif e.remaining_turns == -1:
                    new_r.append(e)
            ch.resists = new_r
            # concentration expiry handled similarly
            if ch.concentration and ch.concentration_turns > 0:
                ch.concentration_turns -= 1
                if ch.concentration_turns <= 0:
                    self.tools.remove_a_concentration(name)
        self.state.add_transcript("<End Turn/>")

    def run(self) -> dict:
        # Initiative
        init = self.tools.roll_initiative()
        self.state.add_transcript(f"Initiative: {init}")
        self.state.add_transcript("<End Turn/>")
        turn_count = 0
        while turn_count < self.max_turns:
            # check combat ends: one side dead
            players_alive = any(c.alive for c in self.state.players.values())
            monsters_alive = any(c.alive for c in self.state.monsters.values())
            if not players_alive or not monsters_alive:
                break
            actor = self.state.current_actor()
            if not actor:
                break
            ch = self.state.get_character(actor)
            if not ch or not ch.alive:
                self.state.advance_turn()
                continue
            is_monster = actor in self.state.monsters
            # check_hp audit at start of round: when turn idx wraps, do full round HP check
            if self.state.current_turn_idx % len(self.state.initiative_order) == 0:
                for n in list(self.state.players.keys()) + list(self.state.monsters.keys()):
                    self.tools.check_hp(n)
            if is_monster:
                self.state.add_transcript(f"--- Monster Turn: {actor} (round {self.state.round}) ---")
                self._monster_turn(actor)
            else:
                self.state.add_transcript(f"--- Player Turn: {actor} (round {self.state.round}) ---")
                self._player_turn(actor)
            self.state.advance_turn()
            turn_count += 1
            # export transcript chunk? Paper segments by <End Turn/>
        # combat end
        death = self.tools.print_death_point()
        self.state.add_transcript(f"Combat ended after {turn_count} turns. Deaths: {death}")
        return {
            "transcript": self.state.transcript,
            "tool_trace": self.state.tool_trace,
            "death": death,
            "players": {n: {"hp": c.hp, "max": c.max_hp, "alive": c.alive} for n, c in self.state.players.items()},
            "monsters": {n: {"hp": c.hp, "max": c.max_hp, "alive": c.alive} for n, c in self.state.monsters.items()},
            "rounds": self.state.round,
        }
