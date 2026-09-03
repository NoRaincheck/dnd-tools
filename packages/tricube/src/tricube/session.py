"""TricubeCampaignSession — outer loop for whole campaigns (multiple scenes).

Reuses TricubeSimulation for per-scene play, orchestrates scenes + rests + persistence.
Mirrors dnd_campaign.session.CampaignSession but for Tricube.
"""

from __future__ import annotations

from typing import Any

from .simulation import (
    TricubeSimulation,
    create_tricube_monster,
    create_tricube_player,
    initialize_tricube_scene,
)
from .state import TricubeCampaignState
from .tools import TricubeCampaignTools


class TricubeSession:
    def __init__(self, cstate: TricubeCampaignState, ctools: TricubeCampaignTools | None = None):
        self.cstate = cstate
        self.ctools = ctools or TricubeCampaignTools(cstate)

    def add_scene(
        self,
        player_specs: list[tuple[str, str, str, str, str]] | None = None,
        monster_specs: list[tuple[str, str, int, bool]] | None = None,
        effort_pools: dict[str, int] | None = None,
        map_kind: str = "outdoor",
    ) -> None:
        """Initialize a new scene on existing CampaignState.

        player_specs: list of (name, trait, concept, perk, quirk) — if None keeps existing players (but resets positions)
        monster_specs: list of (name, trait, rank, is_boss) — trait is monster trait for rank mods
        effort_pools: optional explicit effort pools (overrides monster-based pools), e.g. {"Horde":6}
        """
        inner = self.cstate.inner
        seed = inner.seed + self.cstate.campaign_meta.get("scenes", 0) + 1
        if player_specs is not None:
            inner.players.clear()
            inner.players_pos.clear()
            for spec in player_specs:
                name, trait, concept, perk, quirk = spec
                inner.add_player(
                    create_tricube_player(name, trait=trait, concept=concept, perk=perk, quirk=quirk, rank=1), (0, 0, 0)
                )
        # monsters: clear previous
        inner.monsters.clear()
        inner.monster_pos.clear()
        inner.effort_pools.clear()
        if monster_specs:
            mons = []
            for name, trait, rank, is_boss in monster_specs:
                m = create_tricube_monster(name, trait=trait, concept=name.lower(), rank=rank, is_boss=is_boss)
                mons.append(m)
            # need players list for placement
            initialize_tricube_scene(inner, list(inner.players.values()), mons, map_kind=map_kind, seed=seed)
        else:
            # no monsters: still init map + place players
            initialize_tricube_scene(inner, list(inner.players.values()), [], map_kind=map_kind, seed=seed)
        if effort_pools:
            inner.effort_pools.update(effort_pools)
        self.cstate.campaign_meta["scenes"] = self.cstate.campaign_meta.get("scenes", 0) + 1
        self.cstate.checkpoint()

    def run_scene(self, max_turns: int = 20, use_heuristic: bool = True, llm: Any | None = None) -> dict[str, Any]:
        sim = TricubeSimulation(self.cstate, self.ctools, llm=llm, use_heuristic=use_heuristic, max_turns=max_turns)
        res = sim.run()
        return res

    def run_campaign(
        self,
        scenes: list[dict[str, Any]],
        max_turns_per_scene: int = 20,
        use_heuristic: bool = True,
        llm: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Run sequence of scenes with long rests between (clears scene afflictions).

        scenes: list of dicts with keys: players (optional), monsters, effort_pools (optional), map
        """
        results: list[dict[str, Any]] = []
        for idx, enc in enumerate(scenes):
            self.add_scene(
                player_specs=enc.get("players"),
                monster_specs=enc.get("monsters", []),
                effort_pools=enc.get("effort_pools"),
                map_kind=enc.get("map", "outdoor"),
            )
            res = self.run_scene(max_turns=max_turns_per_scene, use_heuristic=use_heuristic, llm=llm)
            results.append(res)
            if idx < len(scenes) - 1:
                # long rest between scenes to recover scene afflictions; keep campaign afflictions
                self.cstate.long_rest()
                self.cstate.checkpoint()
                if len(self.cstate.inner.tool_trace) > 500:
                    self.cstate.prune_traces(keep_last=350)
        return results
