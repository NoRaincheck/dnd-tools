"""SnSSession — multi-scene campaigns with night rests."""

from __future__ import annotations

from typing import Any

from .simulation import SnSSimulation, create_sns_monster, create_sns_player, initialize_sns_scene
from .state import SnSCampaignState
from .tools import SnSCampaignTools


class SnSSession:
    def __init__(self, cstate: SnSCampaignState, ctools: SnSCampaignTools | None = None):
        self.cstate = cstate
        self.ctools = ctools or SnSCampaignTools(cstate)

    def add_scene(
        self,
        player_specs: list[tuple[str, str, str, int]] | None = None,
        monster_specs: list[tuple[str, str]] | None = None,
        map_kind: str = "outdoor",
        adventure: dict[str, str] | None = None,
    ) -> None:
        inner = self.cstate.inner
        seed = inner.seed + self.cstate.campaign_meta.get("scenes", 0) + 1
        if player_specs is not None:
            inner.players.clear()
            inner.players_pos.clear()
            for spec in player_specs:
                name, ancestry, background, sns = spec
                inner.add_player(create_sns_player(name, ancestry=ancestry, background=background, sns=sns), (0, 0, 0))
        inner.monsters.clear()
        inner.monster_pos.clear()
        if monster_specs:
            mons = []
            for name, threat in monster_specs:
                m = create_sns_monster(name, threat=threat)
                mons.append(m)
            initialize_sns_scene(
                inner, list(inner.players.values()), mons, map_kind=map_kind, seed=seed, adventure=adventure
            )
        else:
            initialize_sns_scene(
                inner, list(inner.players.values()), [], map_kind=map_kind, seed=seed, adventure=adventure
            )
        self.cstate.campaign_meta["scenes"] = self.cstate.campaign_meta.get("scenes", 0) + 1
        self.cstate.checkpoint()

    def run_scene(self, max_turns: int = 20, use_heuristic: bool = True, llm: Any | None = None) -> dict[str, Any]:
        sim = SnSSimulation(self.cstate, self.ctools, llm=llm, use_heuristic=use_heuristic, max_turns=max_turns)
        res = sim.run()
        return res

    def run_campaign(
        self,
        scenes: list[dict[str, Any]],
        max_turns_per_scene: int = 20,
        use_heuristic: bool = True,
        llm: Any | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for idx, enc in enumerate(scenes):
            self.add_scene(
                player_specs=enc.get("players"),
                monster_specs=enc.get("monsters", []),
                map_kind=enc.get("map", "outdoor"),
                adventure=enc.get("adventure"),
            )
            res = self.run_scene(max_turns=max_turns_per_scene, use_heuristic=use_heuristic, llm=llm)
            results.append(res)
            if idx < len(scenes) - 1:
                self.cstate.long_rest()
                self.cstate.checkpoint()
                if len(self.cstate.inner.tool_trace) > 500:
                    self.cstate.prune_traces(keep_last=350)
        return results
