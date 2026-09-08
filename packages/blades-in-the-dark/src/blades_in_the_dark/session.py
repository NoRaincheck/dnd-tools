"""Campaign session orchestration — multi-score with downtime."""

from __future__ import annotations

from typing import Any

from .simulation import BladesSimulation, create_blades_player
from .state import BladesCampaignState


class BladesSession:
    """Orchestrates multiple scores with inter-score downtime (vice/recovery)."""

    def __init__(self, cstate: BladesCampaignState, ctools: Any):
        self.cstate = cstate
        self.ctools = ctools

    def add_score(
        self,
        players: list | None = None,
        clocks: list[tuple[str, int, str]] | None = None,
        map_kind: str = "indoor",
        seed: int | None = None,
    ) -> None:
        if players:
            for p in players:
                if p.name not in self.cstate.inner.players:
                    self.cstate.inner.add_player(p, (0, 0, 0))
        if clocks:
            for name, seg, kind in clocks:
                self.cstate.inner.set_clock(name, seg, kind)
        else:
            self.cstate.inner.set_clock("Score Clock", 6, "obstacle")
        # warm map if needed
        if seed is not None:
            from dnd_tools.mapgen import make_indoor_map, make_outdoor_map

            cells = make_indoor_map(seed) if map_kind == "indoor" else make_outdoor_map(seed)
            self.cstate.inner.set_map(cells)

    def run_score(
        self,
        max_turns: int = 10,
        use_heuristic: bool = True,
        llm: Any | None = None,
        plan: str = "infiltration",
        detail: str = "quietly",
    ) -> dict[str, Any]:
        sim = BladesSimulation(
            self.cstate,
            self.ctools,
            llm=llm,
            use_heuristic=use_heuristic,
            max_turns=max_turns,
            plan=plan,
            detail=detail,
        )
        result = sim.run()
        # checkpoint already done in run()
        self.cstate.campaign_meta["scores"] = self.cstate.campaign_meta.get("scores", 0) + 1
        self.cstate.campaign_meta["total_rounds"] = self.cstate.campaign_meta.get("total_rounds", 0) + result.get(
            "rounds", 0
        )
        # accumulate heat: each score adds at least 1? Simplified
        return result

    def run_campaign(
        self,
        scores: list[dict[str, Any]],
        max_turns_per_score: int = 10,
        use_heuristic: bool = True,
        llm: Any | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for idx, spec in enumerate(scores):
            # downtime between scores (except first): vice recovery
            if idx > 0:
                # indulge vice for all to clear some stress
                for name in list(self.cstate.inner.players.keys()):
                    try:
                        self.ctools.indulge_vice(name)
                    except Exception:
                        pass
                # clear danger clocks?
                for clk_name, clk in list(self.cstate.inner.clocks.items()):
                    if clk.kind == "danger":
                        clk.ticks = 0
                self.cstate.checkpoint()
            clocks = spec.get("clocks")
            plan = spec.get("plan", "infiltration")
            detail = spec.get("detail", "quietly")
            map_kind = spec.get("map", "indoor")
            seed = spec.get("seed", self.cstate.seed + idx + 1)
            # reset clocks for this score? keep existing + add new
            if clocks:
                # wipe previous score obstacle clocks? keep danger but add new obstacles
                for k in list(self.cstate.inner.clocks.keys()):
                    if self.cstate.inner.clocks[k].kind == "obstacle":
                        del self.cstate.inner.clocks[k]
                for name, seg, kind in clocks:
                    self.cstate.inner.set_clock(name, seg, kind)
            else:
                # ensure at least score clock
                if not any(v.kind == "obstacle" for v in self.cstate.inner.clocks.values()):
                    self.cstate.inner.set_clock("Score Clock", 6, "obstacle")
            # ensure map
            if "map_kind" not in spec and "map" not in spec:
                map_kind = "indoor"
            from dnd_tools.mapgen import make_indoor_map, make_outdoor_map

            cells = make_indoor_map(seed) if map_kind == "indoor" else make_outdoor_map(seed)
            self.cstate.inner.set_map(cells)
            res = self.run_score(
                max_turns=max_turns_per_score, use_heuristic=use_heuristic, llm=llm, plan=plan, detail=detail
            )
            results.append(res)
        return results


def create_blades_campaign(seed: int = 42) -> tuple[BladesCampaignState, Any]:
    from .tools import BladesCampaignTools

    cstate = BladesCampaignState(seed_val=seed)
    # default crew of 4 scoundrels
    for name, pb in [("Silas", "Lurk"), ("Locke", "Spider"), ("Thorn", "Whisper"), ("Vex", "Cutter")]:
        cstate.inner.add_player(create_blades_player(name, playbook=pb), (0, 0, 0))
    cstate.inner.set_clock("Score Clock", 6, "obstacle")
    ctools = BladesCampaignTools(cstate)
    return cstate, ctools
