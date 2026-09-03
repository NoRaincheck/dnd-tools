"""CampaignSession — outer loop for long-horizon play.

Reuses dnd_tools.simulation.Simulation for per-encounter combat, but orchestrates
multiple encounters + rests + persistence at the campaign level. No edits to
simulation.py; this is a separate orchestrator.
"""

from __future__ import annotations

from typing import Any

from dnd_tools.simulation import Simulation, create_monster, create_player, initialize_encounter

from .state import CampaignState
from .tools import CampaignTools


class CampaignSession:
    def __init__(self, cstate: CampaignState, ctools: CampaignTools | None = None):
        self.cstate = cstate
        self.ctools = ctools or CampaignTools(cstate)

    def add_encounter(
        self,
        player_specs: list[tuple[str, str, str]] | None = None,
        monster_specs: list[str] | None = None,
        map_kind: str = "outdoor",
    ) -> None:
        """Initialize a new encounter on the existing CampaignState.

        player_specs: list of (name, class, tier) — if None, keeps existing players
        monster_specs: list of template names e.g. ["goblin","wolf"]
        """
        inner = self.cstate.inner
        seed = inner.seed + self.cstate.campaign_meta.get("encounters", 0) + 1
        if player_specs is not None:
            inner.players.clear()
            inner.players_pos.clear()
            for name, cls, tier in player_specs:
                inner.add_player(create_player(name, cls, tier=tier), (0, 0, 0))
        monsters = [create_monster(f"M{i + 1}_{tpl}", tpl) for i, tpl in enumerate(monster_specs or [])]
        # reset monsters dict for new encounter
        inner.monsters.clear()
        inner.monster_pos.clear()
        w, h = inner.map_size()
        _ = w, h
        initialize_encounter(inner, list(inner.players.values()), monsters, map_kind=map_kind, seed=seed)
        self.cstate.campaign_meta["encounters"] = self.cstate.campaign_meta.get("encounters", 0) + 1
        self.cstate.checkpoint()

    def run_encounter(self, max_turns: int = 20, use_heuristic: bool = True, llm: Any | None = None) -> dict[str, Any]:
        """Run one encounter via paper Simulation, then checkpoint + prune."""
        sim = Simulation(
            self.cstate.inner, self.ctools.inner_tools, llm=llm, use_heuristic=use_heuristic, max_turns=max_turns
        )
        res = sim.run()
        self.cstate.checkpoint()
        # keep context bounded for next encounter
        if len(self.cstate.inner.tool_trace) > 400:
            self.cstate.prune_traces(keep_last=300)
        return res

    def run_campaign(self, encounters: list[dict[str, Any]], max_turns_per_encounter: int = 20) -> list[dict[str, Any]]:
        """Run a sequence of encounters with long rests between."""
        results: list[dict[str, Any]] = []
        for enc in encounters:
            self.add_encounter(
                player_specs=enc.get("players"),
                monster_specs=enc.get("monsters", []),
                map_kind=enc.get("map", "outdoor"),
            )
            res = self.run_encounter(max_turns=max_turns_per_encounter)
            results.append(res)
            # long rest between encounters unless last
            if enc is not encounters[-1]:
                self.cstate.long_rest()
        return results
