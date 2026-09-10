"""Engine — single-scene loop on top of FusedState."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import asdict, dataclass, field
from typing import Any

from fused.models import CharacterTraits, Clock, Scene, SceneStatus
from fused.state import FusedState

from .llm import generate_beat_choices, narrate_outcome
from .scenes import SCENE_TEMPLATES


def _game_id() -> str:
    return secrets.token_hex(4)


def _pick_clock(state: FusedState, scene: Scene) -> Clock | None:
    # primary progress clock is first scene clock; fallback global
    if scene.clocks:
        # sync name lookup
        for c in scene.clocks:
            if c.name in state.clocks:
                return state.clocks[c.name]
        return state.clocks.get(scene.clocks[0].name)
    return next(iter(state.clocks.values()), None)


@dataclass
class Turn:
    seq: int
    beat_idx: int
    beat_title: str
    situation: str
    choices: dict[str, str]  # obvious/option/odd
    position: str
    effect: str
    picked: str | None = None  # obvious/option/odd
    pick_text: str | None = None
    roll: dict[str, Any] | None = None  # action_roll payload
    narration: str | None = None
    choice_id: str | None = None
    # resolved via rolled / forced / say_yes
    resolved_via: str | None = None


@dataclass
class Game:
    game_id: str
    seed: int
    template_id: str
    actor: str
    scene: Scene
    fstate: FusedState = field(repr=False)
    turns: list[Turn] = field(default_factory=list)
    beat_idx: int = 0
    completed: bool = False
    # traits for pool derivation
    traits: CharacterTraits | None = None

    def clock(self) -> dict[str, Any]:
        clk = _pick_clock(self.fstate, self.scene)
        if not clk:
            return {"name": "progress", "ticks": 0, "segments": 6, "completed": False, "kind": "obstacle"}
        return {
            "name": clk.name,
            "ticks": clk.ticks,
            "segments": clk.segments,
            "completed": clk.completed,
            "kind": clk.kind,
        }

    def turns_view(self) -> list[dict[str, Any]]:
        return [asdict(t) for t in self.turns]

    def story_text(self) -> str:
        parts: list[str] = []
        for t in self.turns:
            if t.narration:
                parts.append(t.narration)
        return "\n\n".join(parts) if parts else "(story not yet started)"


class AdventureEngine:
    """In-memory session store — one Game per game_id."""

    def __init__(self) -> None:
        self.games: dict[str, Game] = {}

    def list_templates(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for tid, t in SCENE_TEMPLATES.items():
            beats_val = t.get("beats", [])
            segs_val = t.get("segments", 6)
            out.append(
                {
                    "template_id": tid,
                    "title": str(t["title"]),
                    "objective": str(t["objective"]),
                    "location": str(t["location"]),
                    "threat": str(t["threat"]),
                    "beats": list(beats_val) if isinstance(beats_val, list) else [],  # type: ignore[arg-type]
                    "segments": int(segs_val) if isinstance(segs_val, int) else 6,  # type: ignore[call-overload]
                }
            )
        return out

    def create_game(
        self,
        template_id: str = "veiled-archive",
        actor: str = "Elaria",
        seed: int | None = None,
        segments: int | None = None,
        bundle_root: Any | None = None,
    ) -> Game:
        tpl = SCENE_TEMPLATES.get(template_id) or SCENE_TEMPLATES["veiled-archive"]
        seed_v = (
            int(seed) if seed is not None else int.from_bytes(hashlib.sha256(actor.encode()).digest()[:2], "big") % 9999
        )
        fstate = FusedState(seed_val=seed_v, bundle_root=bundle_root)  # ephemeral if None

        # traits — enough to give pool 1-2, not trivial 0
        traits = CharacterTraits(
            name=actor,
            ancestry="elf",
            background="tracker",
            archetype="ranger",
            traits=["Suspicious of authority", "Always ready to fight"],
            favored_skills=["stealth", "arcana"],
        )
        fstate.register_traits(traits)

        # scene — beats→clock auto-seeds in state, but we make explicit clock for UI predictability
        tpl_segs = tpl.get("segments", 6)
        segs = int(segments) if segments is not None else (int(tpl_segs) if isinstance(tpl_segs, int) else 6)
        scene_id = str(tpl["scene_id"]) + "-" + secrets.token_hex(2)
        tpl_beats = tpl.get("beats", [])
        beats = list(tpl_beats) if isinstance(tpl_beats, list) else []  # type: ignore[arg-type]
        scene = Scene(
            scene_id=scene_id,
            title=str(tpl["title"]),
            objective=str(tpl["objective"]),
            location=str(tpl["location"]),
            patron=str(tpl["patron"]),
            threat=str(tpl["threat"]),
            beats=beats,
            cast=[actor],
            seed=seed_v,
        )
        # add scene via state so clocks hash is right, then force progress clock segments to requested
        fstate.add_scene(scene)
        # Ensure progress clock uses requested segments
        prog_name = scene.clocks[0].name if scene.clocks else f"{scene_id}-progress"
        if prog_name in fstate.clocks:
            clk = fstate.clocks[prog_name]
            clk.segments = int(segs)
            # also patch scene copy
            for c in scene.clocks:
                if c.name == prog_name:
                    c.segments = int(segs)
        else:
            fstate.set_clock(prog_name, segments=int(segs), kind="obstacle")
        scene.status = SceneStatus.active

        game = Game(
            game_id=_game_id(),
            seed=seed_v,
            template_id=template_id,
            actor=actor,
            scene=scene,
            fstate=fstate,
            traits=traits,
        )
        # seed first turn
        self._ensure_next_turn(game)
        self.games[game.game_id] = game
        return game

    def get_game(self, game_id: str) -> Game:
        g = self.games.get(game_id)
        if not g:
            raise KeyError(game_id)
        return g

    def _ensure_next_turn(self, game: Game) -> Turn | None:
        if game.completed:
            return None
        clk = _pick_clock(game.fstate, game.scene)
        if clk and clk.completed:
            game.completed = True
            game.scene.status = SceneStatus.resolved
            return None
        # beats cycle if we run out (rare — segment > beats)
        beat_idx = game.beat_idx % max(1, len(game.scene.beats))
        beat_title = game.scene.beats[beat_idx] if game.scene.beats else f"Beat {beat_idx + 1}"
        ch = generate_beat_choices(False, game.template_id, beat_idx, game.actor)
        turn = Turn(
            seq=len(game.turns),
            beat_idx=beat_idx,
            beat_title=str(beat_title),
            situation=str(ch["situation"]),
            choices={"obvious": str(ch["obvious"]), "option": str(ch["option"]), "odd": str(ch["odd"])},
            position=str(ch.get("position", "risky")),
            effect=str(ch.get("effect", "standard")),
        )
        # persist as pending
        game.turns.append(turn)
        # also log proposal via FusedState so site timeline knows
        try:
            choice = game.fstate.propose_choice(
                game.actor,
                turn.situation,
                turn.choices["obvious"],
                turn.choices["option"],
                turn.choices["odd"],
                traits=list(game.traits.traits) if game.traits else [],
                position=turn.position,
                effect=turn.effect,
            )
            turn.choice_id = choice.choice_id
        except Exception:
            turn.choice_id = None
        return turn

    def current_turn(self, game: Game) -> dict[str, Any] | None:
        if not game.turns:
            return None
        # pending is last turn with picked==None and not completed
        for t in reversed(game.turns):
            if t.picked is None and not game.completed:
                return asdict(t)
        return None

    def resolve_pick(self, game_id: str, pick: str, auto: bool = False) -> dict[str, Any]:
        game = self.get_game(game_id)
        if game.completed:
            return {"completed": True, "clock": game.clock(), "story": game.story_text(), "turns": game.turns_view()}
        # normalize pick
        raw = pick.strip().lower()
        alias = {"0": "obvious", "1": "option", "2": "odd", "o": "obvious"}
        cat = alias.get(raw, raw)
        if cat not in ("obvious", "option", "odd"):
            raise ValueError("pick must be obvious|option|odd (or 0/1/2)")

        # locate pending turn (last unpicked)
        pending: Turn | None = None
        for t in reversed(game.turns):
            if t.picked is None:
                pending = t
                break
        if pending is None:
            # no pending — create next
            pending = self._ensure_next_turn(game)
            if pending is None:
                return {
                    "completed": True,
                    "clock": game.clock(),
                    "story": game.story_text(),
                    "turns": game.turns_view(),
                }
            # if we just created, loop again to resolve it
            return self.resolve_pick(game_id, pick, auto=auto)

        # Auto mode: override pick via TripleO roll distribution
        resolved_via = "forced"
        if auto:
            from triple_o.core import TripleO

            triple = TripleO(seed=game.seed + pending.seq + 97)
            # we reuse dice sequence continuity via game.seed drift; use fresh triple to avoid global reseed clobber
            roll_res = triple.roll()
            cat = roll_res.category
            resolved_via = "rolled"

        pick_text = pending.choices[cat]
        pending.picked = cat
        pending.pick_text = pick_text

        # --- gated roll: set_position_and_effect → action_roll ---
        # The gate is hard — action_roll fails without it (state.py:232)
        try:
            game.fstate.set_position_and_effect(game.actor, pick_text[:120], pending.position, pending.effect)
        except Exception as e:
            raise ValueError(str(e)) from e

        clk = _pick_clock(game.fstate, game.scene)
        clock_name = clk.name if clk else None
        roll = game.fstate.action_roll(game.actor, clock=clock_name)
        if not roll.get("valid", True):
            # surface gate error
            roll = {"valid": False, "reason": roll.get("reason", "gate failed")}
            pending.roll = roll
            return {"error": roll, "clock": game.clock()}

        pending.roll = roll
        pending.resolved_via = resolved_via if roll.get("outcome") else "rolled"

        # side-effect: record the chosen branch visibility via effect (not just choice)
        try:
            game.fstate.record_effect(
                "adventure-turn",
                game.actor,
                f"Turn {pending.seq}: {pending.beat_title} — {cat} → {roll.get('outcome')} ticks {roll.get('ticks')}",
                payload={
                    "turn": asdict(pending),
                    "action_roll": roll,
                    "pick": cat,
                    "pick_text": pick_text,
                },
                scene_id=game.scene.scene_id,
            )
        except Exception:
            pass

        # narration — template-aware flavor (see llm.py _TEMPLATE_FLAVOR)
        clk_now = _pick_clock(game.fstate, game.scene)
        completed = bool(clk_now.completed) if clk_now else False
        narration = narrate_outcome(game.actor, pending.beat_title, pick_text, roll, completed, game.template_id)
        pending.narration = narration

        # advance beat index regardless of success — success ticks clock, failure still moves fiction forward
        game.beat_idx += 1

        # check completion
        clk_after = _pick_clock(game.fstate, game.scene)
        if clk_after and clk_after.completed:
            game.completed = True
            game.scene.status = SceneStatus.resolved
            try:
                game.fstate.record_effect(
                    "scene-end",
                    "GM",
                    f"Scene {game.scene.scene_id} resolved — {game.scene.objective}",
                    payload={"result": "completed", "clock": game.clock()},
                    scene_id=game.scene.scene_id,
                )
            except Exception:
                pass
            return {
                "completed": True,
                "turn": asdict(pending),
                "clock": game.clock(),
                "story": game.story_text(),
                "turns": game.turns_view(),
            }

        # seed next turn proposal so UI has no gap
        nxt = self._ensure_next_turn(game)
        return {
            "completed": False,
            "turn": asdict(pending),
            "next_turn": asdict(nxt) if nxt else None,
            "clock": game.clock(),
            "story": game.story_text(),
            "turns": game.turns_view(),
        }

    def to_dict(self, game: Game) -> dict[str, Any]:
        pending = self.current_turn(game)
        return {
            "game_id": game.game_id,
            "seed": game.seed,
            "template_id": game.template_id,
            "actor": game.actor,
            "scene": {
                "scene_id": game.scene.scene_id,
                "title": game.scene.title,
                "objective": game.scene.objective,
                "location": game.scene.location,
                "threat": game.scene.threat,
                "beats": list(game.scene.beats),
                "status": game.scene.status.value,
            },
            "clock": game.clock(),
            "completed": game.completed,
            "turns": game.turns_view(),
            "pending": pending,
            "story": game.story_text(),
        }
