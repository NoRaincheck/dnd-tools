"""FusedTools — unified tool surface for fused campaign.

Delegates all dnd_tools.Tools via CampaignState inner, plus:
  - traits: register_traits / get_traits / list_traits
  - scenes: create_scene / get_scene / list_scenes / advance_scene_beat
  - effects: record_effect / traverse_history / get_context / export_okf
  - creativity: delegated Triple-O tools (propose_triple_o etc. via inner TripleOTools)
  - campaign: long_rest / short_rest / checkpoint etc. via CampaignTools

All mutations are logged to campaign.inner.tool_trace for audit.
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
        # Triple-O engine seeded from fused seed
        self.triple_o = TripleO(seed=fstate.seed)
        self.triple_tools = TripleOTools(self.triple_o)
        # ensure trait registry is visible to triple_o via payloads

    # -- delegation for paper tools --------------------------------------
    def __getattr__(self, name: str) -> Any:
        # try base tools first, then campaign tools, then triple
        if hasattr(self.base_tools, name):
            return getattr(self.base_tools, name)
        if hasattr(self.campaign_tools, name):
            return getattr(self.campaign_tools, name)
        if hasattr(self.triple_tools, name):
            return getattr(self.triple_tools, name)
        raise AttributeError(name)

    def dispatch(self, name: str, args: dict[str, Any]) -> Any:
        # fused-level tools first
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
            "export_okf",
            "summarize_fused",
        }
        if name in fused_names and hasattr(self, name):
            return getattr(self, name)(**args)
        # triple-o
        if hasattr(self.triple_tools, name):
            try:
                return self.triple_tools.dispatch(name, args)
            except ValueError:
                pass
        # campaign
        try:
            return self.campaign_tools.dispatch(name, args)
        except Exception:
            pass
        # base
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
        self.fstate.record_effect(
            "trait-register", name, f"Registered traits for {name}: {ct.trait_summary()}", payload={"traits": ct.traits}
        )
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

    # -- scenes (narrative structure) ----------------------------------------
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
        seed: int | None = None,
    ) -> dict[str, Any]:
        # seed defaults to fused seed + scenes count
        s_seed = seed if seed is not None else self.fstate.seed + len(self.fstate.scenes) + 1
        sc = Scene(
            scene_id=scene_id,
            title=title,
            objective=objective,
            location=location,
            patron=patron,
            threat=threat,
            beats=list(beats or []),
            cast=list(cast or []),
            seed=s_seed,
        )
        self.fstate.add_scene(sc)
        res = {"scene_id": scene_id, "title": title, "status": sc.status.value}
        self.fstate.campaign.inner.log_tool("create_scene", {"scene_id": scene_id}, res)
        self.fstate.record_effect(
            "scene-create",
            "GM",
            f"Scene {scene_id}: {title} — {objective}",
            payload={"location": location, "threat": threat},
        )
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
                # beats are narration steps; we pop or mark progress via status
                if s.status == SceneStatus.planned:
                    s.status = SceneStatus.active
                elif s.status == SceneStatus.active and len(s.beats) > 0:
                    # resolve last beat as done (we treat beats as queued)
                    pass
                s.status = SceneStatus.active if s.status == SceneStatus.planned else s.status
                # record as effect so OKF history captures narrative progression
                self.fstate.record_effect(
                    "scene-beat", "GM", f"Advance {scene_id}: {note or s.title}", payload={"note": note}
                )
                res: dict[str, Any] = {"scene_id": scene_id, "status": s.status.value, "note": note}
                self.fstate.campaign.inner.log_tool("advance_scene_beat", {"scene_id": scene_id}, res)
                return res
        res = {"found": False, "scene_id": scene_id}  # type: ignore[return-value]
        self.fstate.campaign.inner.log_tool("advance_scene_beat", {"scene_id": scene_id}, res)
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

    def export_okf(self, bundle_root: str | None = None) -> dict[str, Any]:
        root = self.fstate.export_okf(bundle_root=bundle_root) if bundle_root else self.fstate.export_okf()
        res = {
            "bundle_root": str(root),
            "effects": len(self.fstate.effects),
            "concepts": len(self.fstate._okf._concepts if self.fstate._okf else []),
        }
        # already logged inside export_okf
        return res

    def summarize_fused(self) -> dict[str, Any]:
        from .memory import summarize_fused

        s = summarize_fused(self.fstate)
        self.fstate.campaign.inner.log_tool("summarize_fused", {}, s)
        return s

    # -- schemas -------------------------------------------------------------
    def tool_schemas(self) -> list[dict[str, Any]]:
        base = self.base_tools.tool_schemas()
        camp = [s for s in self.campaign_tools.tool_schemas() if s not in base]
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
                    "description": "Create a narrative scene with objective, location, patron, threat, beats, cast.",
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
                    "name": "record_effect",
                    "description": "Record an effect/event to the append-only OKF log (event state, separate from traits).",
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
                    "description": "Traverse campaign history (OKF event log) with optional filters. Agent uses this before acting.",
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
                    "description": "Get combined context for an actor: stable traits + recent effects + active scene.",
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
                    "name": "export_okf",
                    "description": "Export campaign as OKF bundle (markdown+YAML per okf.md/spec).",
                    "parameters": {"type": "object", "properties": {"bundle_root": {"type": "string"}}, "required": []},
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
        ]
        # de-duplicate by name
        seen = {s["function"]["name"] for s in base}
        filtered_camp = [s for s in camp if s["function"]["name"] not in seen]
        seen.update(s["function"]["name"] for s in filtered_camp)
        filtered_trip = [s for s in trip if s["function"]["name"] not in seen]
        return base + filtered_camp + filtered_trip + extra
