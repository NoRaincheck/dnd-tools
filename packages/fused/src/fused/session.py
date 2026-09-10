"""FusedSession — scene-based campaign orchestrator with Triple-O + JSONL log (joint SRD).

Reuses dnd_tools.simulation.Simulation for combat within a scene, but
surrounds it with:
  - traits registration (stable, separate; GH #4)
  - scene creation / beat→clock progression (narrative structure; beats auto-seed a 6-clock)
  - Triple-O propose→roll per player dilemma (creativity harness, triple_o/middleware.py)
  - Position/Effect gate + gated action_roll + resistance (Blades-grade “cannot soften”, ref/blades-in-the-dark.md §7)
  - JSONL event log + snapshots + idempotent projection (traversable memory; GH #8 / PR #9)

Per-turn journalistic loop (GH #11): ``get_traits+get_context → propose→roll → set_position_and_effect → action_roll → resistance → record → tick_clock``.
MVP still delegates combat to 5e Simulation; the gated roll is exercised via
direct ``FusedTools`` calls (exposed to the LLM) and recorded alongside
heuristic triple-o effects. No edits to dnd_tools or dnd_campaign.
"""

from __future__ import annotations

import random
from typing import Any

from dnd_tools.simulation import Simulation, create_monster, create_player, initialize_encounter
from triple_o.middleware import TripleOMiddleware

from .models import CharacterTraits, Scene, SceneStatus
from .state import FusedState
from .tools import FusedTools


class FusedSession:
    def __init__(self, fstate: FusedState, ftools: FusedTools | None = None):
        self.fstate = fstate
        self.ftools = ftools or FusedTools(fstate)
        self.triple_mw = TripleOMiddleware(seed=fstate.seed)

    # -- party / traits setup ------------------------------------------------
    def register_party_traits(self, traits_list: list[CharacterTraits]) -> None:
        for tr in traits_list:
            self.fstate.register_traits(tr)

    # -- encounter helpers ---------------------------------------------------
    def _ensure_players(self, player_specs: list[tuple[str, str, str]] | None) -> None:
        if player_specs is None:
            return
        self.fstate.campaign.inner.players.clear()
        self.fstate.campaign.inner.players_pos.clear()
        for name, cls, tier in player_specs:
            ch = create_player(name, cls, tier=tier)
            self.fstate.campaign.inner.add_player(ch, (0, 0, 0))
            # auto-register minimal traits if not already present
            if name not in self.fstate.traits_registry:
                self.fstate.register_traits(
                    CharacterTraits(
                        name=name,
                        archetype=cls,
                        traits=[f"{cls} training"],
                        background="adventurer",
                    )
                )

    def add_scene_with_encounter(
        self,
        scene: Scene,
        player_specs: list[tuple[str, str, str]] | None = None,
        monster_specs: list[str] | None = None,
        map_kind: str = "outdoor",
    ) -> None:
        """Create a scene and initialize its encounter map/positions."""
        self.fstate.add_scene(scene)
        self._ensure_players(player_specs)
        seed = scene.seed or self.fstate.seed + len(self.fstate.scenes)
        monsters = [create_monster(f"M{i + 1}_{tpl}", tpl) for i, tpl in enumerate(monster_specs or [])]
        self.fstate.campaign.inner.monsters.clear()
        self.fstate.campaign.inner.monster_pos.clear()
        initialize_encounter(
            self.fstate.campaign.inner,
            list(self.fstate.campaign.inner.players.values()),
            monsters,
            map_kind=map_kind,
            seed=seed,
        )
        self.fstate.record_effect(
            "encounter-start",
            "GM",
            f"Scene {scene.scene_id}: {scene.title} — {scene.objective} ({len(monsters)} foes, {map_kind})",
            payload={"monsters": monster_specs or [], "map": map_kind},
            scene_id=scene.scene_id,
        )
        self.fstate.campaign.checkpoint()

    # -- per-scene run -------------------------------------------------------
    def run_scene(
        self,
        max_turns: int = 12,
        use_heuristic: bool = True,
        use_triple_o: bool = True,
        llm: Any | None = None,
    ) -> dict[str, Any]:
        """Run the active scene as a combat encounter with fused bookkeeping.

        If use_triple_o, each player turn first goes through Triple-O
        propose→roll for creativity, then the chosen branch informs the
        tactical move/attack. LLM is optional; falls back to heuristic.
        """
        scene = self.fstate.current_scene()
        if not scene:
            raise RuntimeError("no active scene — call add_scene_with_encounter first")
        scene.status = SceneStatus.active

        # inject campaign Choices (Triple-O + Position/Effect + Say Yes) before combat
        # Each player gets a dilemma via the ChoiceResolver; trivial choices Say Yes
        # automatically to Obvious but remain visible as logged choices.
        if use_triple_o and use_heuristic:
            for pname in list(self.fstate.campaign.inner.players.keys()):
                tr = self.fstate.get_traits(pname)
                trait_list = tr.traits if tr else [self.fstate.campaign.inner.players[pname].char_class]
                situation = f"Scene {scene.scene_id}: {scene.objective} — what does {pname} do?"
                obvious = f"{pname} holds position and attacks the nearest foe"
                option = f"{pname} repositions for flanking"
                odd = f"{pname} tries an impulsive stunt"
                # risk assessment: trivial for first player in low-threat scenes
                # Demonstrate both paths: controlled→Say Yes, risky/desparate→roll
                if len(self.fstate.choices) % 3 == 0 and scene.threat.lower() in ("unknown", "none", ""):
                    position, effect = "controlled", "limited"
                elif pname == next(iter(self.fstate.campaign.inner.players.keys())):
                    position, effect = "controlled", "standard"
                else:
                    position, effect = "risky", "standard"
                choice = self.fstate.propose_choice(
                    pname, situation, obvious, option, odd, traits=trait_list, position=position, effect=effect
                )
                resolved = self.fstate.resolve_choice(choice.choice_id)
                # keep legacy triple-o effect for backward compat, but also log choice
                self.fstate.campaign.inner.add_transcript(
                    f"[choice {resolved.choice_id}] {pname} {resolved.category} via {resolved.resolved_via}: {resolved.choice_text}{' — Say Yes trivial: ' + resolved.trivial_reason if resolved.trivial else ''}"
                )

        sim = Simulation(
            self.fstate.campaign.inner,
            self.ftools.base_tools,
            llm=llm,
            use_heuristic=use_heuristic,
            max_turns=max_turns,
        )
        res = sim.run()
        # record scene outcome as effect
        outcome = f"Scene {scene.scene_id} ended after {res['rounds']} rounds — players {res['players']}"
        self.fstate.record_effect(
            "scene-end", "GM", outcome, payload={"result": res["players"]}, scene_id=scene.scene_id
        )
        scene.status = SceneStatus.resolved
        # log is already canonical; snapshot if needed
        try:
            if len(self.fstate.effects) % self.fstate._snapshot_every == 0:
                self.fstate.take_snapshot()
        except Exception:
            pass
        self.fstate.campaign.checkpoint()
        if len(self.fstate.campaign.inner.tool_trace) > 400:
            self.fstate.campaign.prune_traces(keep_last=300)
        return res

    def run_campaign_via_choices(
        self,
        choice_specs: list[dict[str, Any]],
        scene_id: str = "scene-choices",
        scene_title: str = "Choice-driven Campaign",
        scene_objective: str = "Unfold campaign through LLM-derived choices",
    ) -> list[dict[str, Any]]:
        """Run a pure choice-driven campaign (no combat) — sequence of dilemmas.

        Each spec is a Choice proposal: {actor, situation, obvious, option, odd, position, effect, traits}
        LLM would generate these; heuristic supplies defaults. Demonstrates Say Yes for trivial.
        """
        cur = self.fstate.current_scene()
        if not cur or cur.scene_id != scene_id:
            scene = Scene(scene_id=scene_id, title=scene_title, objective=scene_objective, beats=[], cast=[])
            self.fstate.add_scene(scene)
        results: list[dict[str, Any]] = []
        for spec in choice_specs:
            actor = spec.get("actor", "GM")
            situation = spec.get("situation", "dilemma")
            obvious = spec["obvious"]
            option = spec["option"]
            odd = spec["odd"]
            position = spec.get("position", "risky")
            effect = spec.get("effect", "standard")
            traits = spec.get("traits")
            ch = self.fstate.propose_choice(
                actor, situation, obvious, option, odd, traits=traits, position=position, effect=effect
            )
            resolved = self.fstate.resolve_choice(ch.choice_id, advantage=spec.get("advantage"))
            results.append(
                {
                    "choice_id": resolved.choice_id,
                    "situation": situation,
                    "proposal": {"obvious": obvious, "option": option, "odd": odd},
                    "position": position,
                    "effect": effect,
                    "trivial": resolved.trivial,
                    "resolved_via": resolved.resolved_via,
                    "category": resolved.category,
                    "choice": resolved.choice_text,
                    "reason": resolved.trivial_reason,
                }
            )
        return results

    def run_campaign(
        self,
        scenes: list[dict[str, Any]],
        max_turns_per_scene: int = 12,
        use_triple_o: bool = True,
    ) -> list[dict[str, Any]]:
        """Run a sequence of scenes with long rests between (like dnd_campaign)."""
        random.seed(self.fstate.seed)
        results: list[dict[str, Any]] = []
        for idx, spec in enumerate(scenes):
            scene = Scene(
                scene_id=spec.get("scene_id", f"scene-{idx + 1:02d}"),
                title=spec.get("title", f"Scene {idx + 1}"),
                objective=spec.get("objective", "Explore"),
                location=spec.get("location", "wilderlands"),
                patron=spec.get("patron", "Guild"),
                threat=spec.get("threat", "unknown"),
                beats=list(spec.get("beats", [])),
                cast=list(spec.get("cast", [])),
                seed=self.fstate.seed + idx + 1,
            )
            self.add_scene_with_encounter(
                scene,
                player_specs=spec.get("players"),
                monster_specs=spec.get("monsters", []),
                map_kind=spec.get("map", "outdoor"),
            )
            res = self.run_scene(max_turns=max_turns_per_scene, use_heuristic=True, use_triple_o=use_triple_o)
            results.append(res)
            if spec is not scenes[-1]:
                self.fstate.campaign.long_rest()
                self.fstate.record_effect(
                    "long-rest", "GM", "Party takes a night's rest; HP/slots restored", scene_id=scene.scene_id
                )
        # final snapshot
        try:
            self.fstate.take_snapshot()
        except Exception:
            pass
        return results
