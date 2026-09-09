"""FusedTools — unified tool surface for fused campaign (joint SRD).

Implements the ideal joint SRD (§3.5): minimal LLM-facing schemas (~16) with
hard gates. Raw 5e tools (roll_attack etc.) remain internally via
``base_tools`` for the heuristic Simulation but are *not* exposed in
``tool_schemas`` — the LLM must go through
``propose_triple_o → roll_triple_o → set_position_and_effect → action_roll → resistance_roll``.

All mutations log to ``campaign.inner.tool_trace`` and append to the canonical
``events.jsonl`` via ``FusedState``.
"""

from __future__ import annotations

from typing import Any

from dnd_campaign.tools import CampaignTools as _CampaignTools
from dnd_tools.tools import Tools as _BaseTools
from triple_o.core import TripleO
from triple_o.tools import TripleOTools

from .models import CharacterTraits, Scene, SceneStatus
from .state import FusedState


class FusedTools:
    def __init__(self, fstate: FusedState):
        self.fstate = fstate
        self.base_tools = _BaseTools(fstate.campaign.inner)
        self.campaign_tools = _CampaignTools(fstate.campaign)
        self.triple_o = TripleO(seed=fstate.seed)
        self.triple_tools = TripleOTools(self.triple_o)

    # -- delegation (non-schema, for internal simulation/tests) ---------------
    def __getattr__(self, name: str) -> Any:
        if hasattr(self.base_tools, name):
            return getattr(self.base_tools, name)
        if hasattr(self.campaign_tools, name):
            return getattr(self.campaign_tools, name)
        if hasattr(self.triple_tools, name):
            return getattr(self.triple_tools, name)
        raise AttributeError(name)

    def dispatch(self, name: str, args: dict[str, Any]) -> Any:
        fused_names = {
            "register_traits",
            "get_traits",
            "list_traits",
            "create_scene",
            "get_scene",
            "list_scenes",
            "advance_scene_beat",
            "record_effect",
            "traverse_history",
            "get_context",
            "summarize_fused",
            "set_position_and_effect",
            "action_roll",
            "resistance_roll",
            "mark_stress",
            "set_clock",
            "tick_clock",
            "visualize_clocks",
            "visualize_map",
            "get_names_of_all_players",
            "get_names_of_all_monsters",
            "roll_initiative",
        }
        if name in fused_names and hasattr(self, name):
            return getattr(self, name)(**args)
        if hasattr(self.triple_tools, name):
            try:
                return self.triple_tools.dispatch(name, args)
            except ValueError:
                pass
        try:
            return self.campaign_tools.dispatch(name, args)
        except Exception:
            pass
        return self.base_tools.dispatch(name, args)

    # -- traits (separate from event state) --------------------------------
    def register_traits(
        self,
        name: str,
        ancestry: str = "human",
        background: str = "adventurer",
        archetype: str = "fighter",
        alignment: str = "neutral",
        traits: list[str] | None = None,
        flaws: list[str] | None = None,
        fears: list[str] | None = None,
        favored_skills: list[str] | None = None,
        bonds: list[str] | None = None,
        ideals: list[str] | None = None,
        concept: str = "",
        perk: str = "",
        quirk: str = "",
    ) -> dict[str, Any]:
        ct = CharacterTraits(
            name=name,
            ancestry=ancestry,
            background=background,
            archetype=archetype,
            alignment=alignment,
            traits=list(traits or []),
            flaws=list(flaws or []),
            fears=list(fears or []),
            favored_skills=list(favored_skills or []),
            bonds=list(bonds or []),
            ideals=list(ideals or []),
            concept=concept,
            perk=perk,
            quirk=quirk,
        )
        self.fstate.register_traits(ct)
        res = {"name": name, "registered": True, "summary": ct.trait_summary()}
        self.fstate.campaign.inner.log_tool("register_traits", {"name": name}, res)
        return res

    def get_traits(self, name: str) -> dict[str, Any]:
        ct = self.fstate.get_traits(name)
        if not ct:
            res: dict[str, Any] = {"found": False, "name": name}
            self.fstate.campaign.inner.log_tool("get_traits", {"name": name}, res)
            return res
        from dataclasses import asdict

        res = {"found": True, **asdict(ct)}
        self.fstate.campaign.inner.log_tool("get_traits", {"name": name}, res)
        return res

    def list_traits(self) -> list[str]:
        r = list(self.fstate.traits_registry.keys())
        self.fstate.campaign.inner.log_tool("list_traits", {}, r)
        return r

    # -- scenes (narrative structure, beats→clocks) --------------------------
    def create_scene(
        self,
        scene_id: str,
        title: str,
        objective: str,
        location: str = "wilderlands",
        patron: str = "Guild",
        threat: str = "unknown",
        beats: list[str] | None = None,
        cast: list[str] | None = None,
        clocks: list[dict[str, Any]] | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        s_seed = seed if seed is not None else self.fstate.seed + len(self.fstate.scenes) + 1
        from .models import Clock

        clock_objs: list[Clock] = []
        if clocks:
            for c in clocks:
                try:
                    clock_objs.append(
                        Clock(name=c["name"], segments=int(c.get("segments", 6)), kind=c.get("kind", "obstacle"))
                    )
                except Exception:  # noqa: S112
                    continue
        sc = Scene(
            scene_id=scene_id,
            title=title,
            objective=objective,
            location=location,
            patron=patron,
            threat=threat,
            beats=list(beats or []),
            cast=list(cast or []),
            clocks=clock_objs,
            seed=s_seed,
        )
        self.fstate.add_scene(sc)
        res = {"scene_id": scene_id, "title": title, "status": sc.status.value}
        self.fstate.campaign.inner.log_tool("create_scene", {"scene_id": scene_id}, res)
        return res

    def get_scene(self, scene_id: str) -> dict[str, Any]:
        for s in self.fstate.scenes:
            if s.scene_id == scene_id:
                from dataclasses import asdict

                res = asdict(s)
                res["status"] = s.status.value
                self.fstate.campaign.inner.log_tool("get_scene", {"scene_id": scene_id}, res)
                return res
        res = {"found": False, "scene_id": scene_id}
        self.fstate.campaign.inner.log_tool("get_scene", {"scene_id": scene_id}, res)
        return res

    def list_scenes(self) -> list[dict[str, Any]]:
        r = [
            {"scene_id": s.scene_id, "title": s.title, "status": s.status.value, "objective": s.objective}
            for s in self.fstate.scenes
        ]
        self.fstate.campaign.inner.log_tool("list_scenes", {}, r)
        return r

    def advance_scene_beat(self, scene_id: str, note: str = "") -> dict[str, Any]:
        for s in self.fstate.scenes:
            if s.scene_id == scene_id:
                if s.status == SceneStatus.planned:
                    s.status = SceneStatus.active
                s.status = SceneStatus.active if s.status == SceneStatus.planned else s.status
                self.fstate.record_effect(
                    "scene-beat", "GM", f"Advance {scene_id}: {note or s.title}", payload={"note": note}
                )
                res: dict[str, Any] = {"scene_id": scene_id, "status": s.status.value, "note": note}
                self.fstate.campaign.inner.log_tool("advance_scene_beat", {"scene_id": scene_id}, res)
                return res
        res = {"found": False, "scene_id": scene_id}  # type: ignore[return-value]
        self.fstate.campaign.inner.log_tool("advance_scene_beat", {"scene_id": scene_id}, res)
        return res

    # -- clocks (joint SRD) -------------------------------------------------
    def set_clock(self, name: str, segments: int = 6, kind: str = "obstacle") -> dict[str, Any]:
        clk = self.fstate.set_clock(name, segments=int(segments), kind=kind)
        res = {"name": clk.name, "segments": clk.segments, "ticks": clk.ticks, "kind": clk.kind}
        self.fstate.campaign.inner.log_tool("set_clock", {"name": name, "segments": segments, "kind": kind}, res)
        return res

    def tick_clock(self, name: str, ticks: int) -> dict[str, Any]:
        res = self.fstate.tick_clock(name, int(ticks))
        self.fstate.campaign.inner.log_tool("tick_clock", {"name": name, "ticks": ticks}, res)
        return res

    def visualize_clocks(self) -> dict[str, Any]:
        txt = self.fstate.visualize_clocks()
        res = {
            "ascii": txt,
            "clocks": {
                k: {"ticks": v.ticks, "segments": v.segments, "completed": v.completed}
                for k, v in self.fstate.clocks.items()
            },
        }
        self.fstate.campaign.inner.log_tool("visualize_clocks", {}, res)
        return res

    # -- position/effect gate + resolution (joint SRD) -----------------------
    def set_position_and_effect(self, actor: str, action: str, position: str, effect: str) -> dict[str, Any]:
        res = self.fstate.set_position_and_effect(actor, action, position, effect)
        self.fstate.campaign.inner.log_tool(
            "set_position_and_effect", {"actor": actor, "action": action, "position": position, "effect": effect}, res
        )
        return res

    def action_roll(self, actor: str, clock: str | None = None) -> dict[str, Any]:
        res = self.fstate.action_roll(actor, clock=clock)
        self.fstate.campaign.inner.log_tool("action_roll", {"actor": actor, "clock": clock}, res)
        return res

    def resistance_roll(self, actor: str, attribute: str = "Resolve") -> dict[str, Any]:
        res = self.fstate.resistance_roll(actor, attribute=attribute)
        self.fstate.campaign.inner.log_tool("resistance_roll", {"actor": actor, "attribute": attribute}, res)
        return res

    def mark_stress(self, actor: str, delta: int) -> dict[str, Any]:
        res = self.fstate.mark_stress(actor, int(delta))
        self.fstate.campaign.inner.log_tool("mark_stress", {"actor": actor, "delta": delta}, res)
        return res

    # -- effects / history traversal -----------------------------------------
    def record_effect(
        self, kind: str, actor: str, summary: str, payload: dict[str, Any] | None = None, scene_id: str | None = None
    ) -> dict[str, Any]:
        eff = self.fstate.record_effect(kind, actor, summary, payload=payload, scene_id=scene_id)
        from dataclasses import asdict

        res = asdict(eff)
        self.fstate.campaign.inner.log_tool("record_effect", {"kind": kind, "actor": actor}, res)
        return res

    def traverse_history(
        self,
        scene_id: str | None = None,
        actor: str | None = None,
        kind: str | None = None,
        last_n: int | None = None,
    ) -> list[dict[str, Any]]:
        from dataclasses import asdict

        effs = self.fstate.traverse_history(scene_id=scene_id, actor=actor, kind=kind, last_n=last_n)
        r = [asdict(e) for e in effs]
        self.fstate.campaign.inner.log_tool(
            "traverse_history", {"scene_id": scene_id, "actor": actor, "kind": kind}, {"count": len(r)}
        )
        return r

    def get_context(self, actor: str, last_n: int = 20) -> dict[str, Any]:
        ctx = self.fstate.context_for_actor(actor, last_n=last_n)
        self.fstate.campaign.inner.log_tool(
            "get_context", {"actor": actor}, {"traits": ctx["traits"], "effects": len(ctx["recent_effects"])}
        )
        return ctx

    def summarize_fused(self) -> dict[str, Any]:
        from .memory import summarize_fused

        s = summarize_fused(self.fstate)
        self.fstate.campaign.inner.log_tool("summarize_fused", {}, s)
        return s

    # -- sense (minimal) -----------------------------------------------------
    def visualize_map(self) -> str:
        out = self.base_tools.visualize_map()
        return out

    def get_names_of_all_players(self) -> list[str]:
        return self.base_tools.get_names_of_all_players()

    def get_names_of_all_monsters(self) -> list[str]:
        return self.base_tools.get_names_of_all_monsters()

    def roll_initiative(self) -> list[dict]:
        return self.base_tools.roll_initiative()

    # -- schemas (minimal LLM-facing, hides raw 5e tools) --------------------
    def tool_schemas(self) -> list[dict[str, Any]]:
        # keep triple-o schemas as-is (propose/roll)
        trip = self.triple_tools.tool_schemas()
        extra: list[dict[str, Any]] = [
            {
                "type": "function",
                "function": {
                    "name": "register_traits",
                    "description": "Register stable character traits (separate from event state). Call before campaign; traits persist across scenes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "ancestry": {"type": "string"},
                            "background": {"type": "string"},
                            "archetype": {"type": "string"},
                            "alignment": {"type": "string"},
                            "traits": {"type": "array", "items": {"type": "string"}},
                            "flaws": {"type": "array", "items": {"type": "string"}},
                            "fears": {"type": "array", "items": {"type": "string"}},
                            "favored_skills": {"type": "array", "items": {"type": "string"}},
                            "bonds": {"type": "array", "items": {"type": "string"}},
                            "ideals": {"type": "array", "items": {"type": "string"}},
                            "concept": {"type": "string"},
                            "perk": {"type": "string"},
                            "quirk": {"type": "string"},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_traits",
                    "description": "Get stable traits for a character (separate store).",
                    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_traits",
                    "description": "List registered trait names.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_scene",
                    "description": "Create a narrative scene with objective, location, patron, threat, beats, cast, and optional clocks [{name, segments, kind}]. Beats auto-create a default 6-clock if no clocks supplied. Beats are shorthand for clocks.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "scene_id": {"type": "string"},
                            "title": {"type": "string"},
                            "objective": {"type": "string"},
                            "location": {"type": "string"},
                            "patron": {"type": "string"},
                            "threat": {"type": "string"},
                            "beats": {"type": "array", "items": {"type": "string"}},
                            "cast": {"type": "array", "items": {"type": "string"}},
                            "clocks": {"type": "array", "items": {"type": "object"}},
                            "seed": {"type": "integer"},
                        },
                        "required": ["scene_id", "title", "objective"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_scene",
                    "description": "Get scene by id.",
                    "parameters": {
                        "type": "object",
                        "properties": {"scene_id": {"type": "string"}},
                        "required": ["scene_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_scenes",
                    "description": "List all scenes.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "advance_scene_beat",
                    "description": "Advance scene narrative beat.",
                    "parameters": {
                        "type": "object",
                        "properties": {"scene_id": {"type": "string"}, "note": {"type": "string"}},
                        "required": ["scene_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "set_clock",
                    "description": "Create or update a progress clock (4/6/8 segments, kind obstacle/danger/project/healing/turf).",
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
                    "description": "Tick a clock by N (1-5; completes at segments). Called after action_roll ticks or as GM move.",
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
                    "name": "visualize_clocks",
                    "description": "Visualize all clocks as ascii bars.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "set_position_and_effect",
                    "description": "GATE: agree Position (controlled/risky/desperate) and Effect (limited/standard/great/zero/extreme) before action_roll. Required — action_roll will fail without this.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "actor": {"type": "string"},
                            "action": {
                                "type": "string",
                                "description": "Fiction action (e.g. Prowl, Skirmish, Attune, or freeform like 'sneak past')",
                            },
                            "position": {"type": "string", "enum": ["controlled", "risky", "desperate"]},
                            "effect": {"type": "string", "enum": ["limited", "standard", "great", "zero", "extreme"]},
                        },
                        "required": ["actor", "action", "position", "effect"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "action_roll",
                    "description": "Gated resolution: Blades-style pool (derived from Traits), zero-dice 2d6kL, critical on 2×6, 6 success /4-5 partial+consequence /1-3 fail+consequence where consequence severity=position. Ticks clock per effect (limited1/standard2/great3, crit+1, partial reduced -1). Requires set_position_and_effect first. Record tick via payload.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "actor": {"type": "string"},
                            "clock": {"type": "string", "description": "Optional clock to auto-tick on success"},
                        },
                        "required": ["actor"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "resistance_roll",
                    "description": "Resist a consequence: roll attribute (Insight/Prowess/Resolve style; here generic Resolve). Cost = 6−high stress (crit clears 1). Reduces/negates consequence but costs stress.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "actor": {"type": "string"},
                            "attribute": {
                                "type": "string",
                                "enum": ["Insight", "Prowess", "Resolve", "Resolve", "insight", "prowess", "resolve"],
                            },
                        },
                        "required": ["actor"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mark_stress",
                    "description": "Mark stress delta (positive = add). 0-9; trauma at overflow handled via fiction.",
                    "parameters": {
                        "type": "object",
                        "properties": {"actor": {"type": "string"}, "delta": {"type": "integer"}},
                        "required": ["actor", "delta"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "record_effect",
                    "description": "Record an effect/event to the append-only JSONL log (event state, separate from traits).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string"},
                            "actor": {"type": "string"},
                            "summary": {"type": "string"},
                            "payload": {"type": "object"},
                            "scene_id": {"type": "string"},
                        },
                        "required": ["kind", "actor", "summary"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "traverse_history",
                    "description": "Traverse campaign history (JSONL event log) with optional filters. Agent uses this before acting.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "scene_id": {"type": "string"},
                            "actor": {"type": "string"},
                            "kind": {"type": "string"},
                            "last_n": {"type": "integer"},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_context",
                    "description": "Get combined context for an actor: stable traits + recent effects + active scene + clocks.",
                    "parameters": {
                        "type": "object",
                        "properties": {"actor": {"type": "string"}, "last_n": {"type": "integer"}},
                        "required": ["actor"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "summarize_fused",
                    "description": "Compact fused state summary for LLM context.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            # sense (minimal, map remains valuable for journalistic “where”)
            {
                "type": "function",
                "function": {
                    "name": "visualize_map",
                    "description": "ASCII map (#=wall, upper=PC, lower=threat) for spatial sense.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_names_of_all_players",
                    "description": "List PC names.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_names_of_all_monsters",
                    "description": "List threat names.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "roll_initiative",
                    "description": "Roll initiative if using 5e turn order (optional in journalistic mode).",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
        ]
        # de-duplicate triple-o by name
        seen = {s["function"]["name"] for s in extra}
        filtered_trip = [s for s in trip if s["function"]["name"] not in seen]
        return extra + filtered_trip
