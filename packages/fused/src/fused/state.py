"""FusedState — campaign with traits separate from event/effect state.

Wraps dnd_campaign.CampaignState (which itself wraps dnd_tools.GameState)
for authoritative mechanics, but keeps:
  - traits_registry: dict[name -> CharacterTraits]  (stable, separate)
  - scenes: list[Scene]                             (narrative structure)
  - effects: list[Effect]                           (append-only event log)
  - okf bundle builder (OKFBundle) for disk persistence + traversal

Determinism: every roll goes through dnd_tools.dice seeded RNG.
History is traversable via OKF bundle (file per concept) plus in-memory
effects list + CampaignState history snapshots.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dnd_campaign.state import CampaignState
from dnd_tools.dice import seed as dice_seed

from .models import CharacterTraits, Effect, Scene


class FusedState:
    """Long-horizon fused state."""

    def __init__(
        self,
        seed_val: int = 0,
        map_w: int = 20,
        map_h: int = 20,
        max_history: int = 100,
        bundle_root: str | Path | None = None,
    ):
        self.seed = seed_val
        dice_seed(seed_val)
        # authoritative mechanics (HP/pos/initiative/LoS) — unchanged paper code
        self.campaign = CampaignState(seed_val=seed_val, map_w=map_w, map_h=map_h, max_history=max_history)
        # trait registry — separate per issue #4
        self.traits_registry: dict[str, CharacterTraits] = {}
        # narrative structure
        self.scenes: list[Scene] = []
        self.active_scene_id: str | None = None
        # append-only event log (this is the "event state")
        self.effects: list[Effect] = []
        self._effect_counter: int = 0
        # OKF bundle (optional — built on demand or at bundle_root)
        self.bundle_root = Path(bundle_root) if bundle_root else None
        from .okf import OKFBundle

        self._okf: OKFBundle | None = None
        if self.bundle_root:
            self._okf = OKFBundle(self.bundle_root, meta_name="fused-campaign", seed=seed_val)

    # -- traits --------------------------------------------------------
    def register_traits(self, traits: CharacterTraits) -> None:
        self.traits_registry[traits.name] = traits

    def get_traits(self, name: str) -> CharacterTraits | None:
        return self.traits_registry.get(name)

    # -- scenes --------------------------------------------------------
    def add_scene(self, scene: Scene) -> Scene:
        self.scenes.append(scene)
        self.active_scene_id = scene.scene_id
        # also track in campaign meta
        self.campaign.campaign_meta["scenes"] = len(self.scenes)
        self.campaign.campaign_meta["active_scene"] = scene.scene_id
        return scene

    def current_scene(self) -> Scene | None:
        if not self.active_scene_id:
            return None
        for s in self.scenes:
            if s.scene_id == self.active_scene_id:
                return s
        return None

    # -- effects (event state) -----------------------------------------
    def record_effect(
        self,
        kind: str,
        actor: str,
        summary: str,
        payload: dict[str, Any] | None = None,
        scene_id: str | None = None,
    ) -> Effect:
        sid = scene_id or self.active_scene_id or "scene-00"
        eid = Effect.make_id(sid, self._effect_counter, kind, actor)
        self._effect_counter += 1
        eff = Effect(
            effect_id=eid,
            scene_id=sid,
            actor=actor,
            kind=kind,
            summary=summary,
            round=self.campaign.inner.round,
            turn_actor=self.campaign.inner.current_actor(),
            payload=dict(payload or {}),
        )
        self.effects.append(eff)
        # attach to scene
        for s in self.scenes:
            if s.scene_id == sid:
                s.effect_ids.append(eid)
                break
        # transcript + tool trace also get a marker for LLM context
        self.campaign.inner.add_transcript(f"[effect {eid}] {actor} {kind}: {summary}")
        # if OKF bundle is active, we could defer writes to flush()
        return eff

    # -- snapshot / restore (includes traits + scenes + effects) -------
    def snapshot(self) -> dict[str, Any]:
        from dataclasses import asdict

        return {
            "seed": self.seed,
            "campaign_snapshot": self.campaign.snapshot(),
            "traits": {k: asdict(v) for k, v in self.traits_registry.items()},
            "scenes": [asdict(s) for s in self.scenes],
            "effects": [asdict(e) for e in self.effects],
            "active_scene_id": self.active_scene_id,
            "effect_counter": self._effect_counter,
        }

    def restore(self, snap: dict[str, Any]) -> None:
        self.seed = snap.get("seed", 0)
        dice_seed(self.seed)
        self.campaign.restore(snap.get("campaign_snapshot", {}))
        # traits
        self.traits_registry = {k: CharacterTraits(**v) for k, v in snap.get("traits", {}).items()}
        # scenes
        from .models import SceneStatus

        scenes: list[Scene] = []
        for d in snap.get("scenes", []):
            # coerce status enum
            if isinstance(d.get("status"), str):
                try:
                    d["status"] = SceneStatus(d["status"])
                except Exception:
                    d["status"] = SceneStatus.planned
            scenes.append(Scene(**d))
        self.scenes = scenes
        # effects
        self.effects = [Effect(**e) for e in snap.get("effects", [])]
        self.active_scene_id = snap.get("active_scene_id")
        self._effect_counter = int(snap.get("effect_counter", len(self.effects)))

    # -- persistence ---------------------------------------------------
    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.snapshot(), indent=2))
        return p

    @classmethod
    def load(cls, path: str | Path) -> FusedState:
        data = json.loads(Path(path).read_text())
        seed = data.get("seed", data.get("campaign_snapshot", {}).get("seed", 0))
        fs = cls(seed_val=seed)
        fs.restore(data)
        return fs

    # -- OKF bundle export ---------------------------------------------
    def export_okf(self, bundle_root: str | Path | None = None) -> Path:
        """Export full fused state as an OKF bundle. Returns bundle root path."""
        from .okf import OKFBundle

        root = Path(bundle_root) if bundle_root else (self.bundle_root or Path("knowledge/fused"))
        bundle = OKFBundle(root, meta_name="fused-campaign", seed=self.seed)

        # traits — one concept per trait (stable, separate)
        for name, traits in sorted(self.traits_registry.items()):
            fm = traits.to_okf_frontmatter()
            # ensure description covers OKF required fields
            body = OKFBundle.body_for_trait(name, traits.traits, traits.flaws, traits.bonds)
            bundle.write_trait(name, fm, body)

        # characters — thin wrapper linking to traits (game state chars)
        for cname, ch in {**self.campaign.inner.players, **self.campaign.inner.monsters}.items():
            slug = cname.lower().replace(" ", "-")
            fm = {
                "type": "Character",
                "title": cname,
                "description": f"{ch.char_class} HP {ch.hp}/{ch.max_hp} at {ch.pos}",
                "tags": ["character", ch.char_class],
                "character_class": ch.char_class,
                "hp": ch.hp,
                "max_hp": ch.max_hp,
                "pos": list(ch.pos),
                "alive": ch.alive,
            }
            trait_ref = (
                f"/traits/{slug}.md"
                if slug in [k.lower().replace(" ", "-") for k in self.traits_registry]
                else "/traits/index.md"
            )
            body = OKFBundle.body_for_character(cname, f"Character {cname} ({ch.char_class})", trait_ref)
            bundle.write_character(cname, fm, body)

        # scenes
        for sc in self.scenes:
            fm = sc.to_okf_frontmatter()
            body = OKFBundle.body_for_scene(sc)
            bundle.write_scene(sc.scene_id, fm, body)

        # events/effects — append-only log, traversable history
        for eff in self.effects:
            fm = eff.to_okf_frontmatter()
            body = OKFBundle.body_for_event(eff)
            bundle.write_event(eff.effect_id, fm, body)

        # references: add attested computation marker for OKF 0.2
        bundle.write_raw(
            "references/attesters/fused_run.md",
            {
                "type": "Attested Computation",
                "title": "Fused campaign run",
                "description": "Deterministic campaign run via FusedState",
                "runtime": "bash",
                "parameters": [{"name": "bundle_root", "type": "string", "required": True}],
            },
            "# Fused Run Attester\n\nRun `uv run fused demo --seed 42` to reproduce.\n",
        )

        # log
        if not bundle._log_entries:
            # seed from effects history
            for eff in self.effects[-10:]:
                bundle.add_log(f"Effect {eff.effect_id} — {eff.summary}", kind="Update")
            if self.scenes:
                for sc in self.scenes:
                    bundle.add_log(f"Scene {sc.scene_id}: {sc.title} — {sc.objective}", kind="Create")

        bundle.flush()
        # validate
        errs = OKFBundle.validate_bundle(root)
        if errs:
            raise RuntimeError(f"OKF validation failed: {errs}")
        # update handles
        self.bundle_root = root
        self._okf = bundle
        # also log to inner transcript for audit
        self.campaign.inner.log_tool(
            "export_okf", {"bundle_root": str(root)}, {"effects": len(self.effects), "concepts": len(bundle._concepts)}
        )
        return root

    # -- traversal helpers for agents ----------------------------------
    def traverse_history(
        self,
        *,
        scene_id: str | None = None,
        actor: str | None = None,
        kind: str | None = None,
        last_n: int | None = None,
    ) -> list[Effect]:
        """Filter effects — agent traverses history before acting."""
        result = list(self.effects)
        if scene_id:
            result = [e for e in result if e.scene_id == scene_id]
        if actor:
            result = [e for e in result if e.actor == actor]
        if kind:
            result = [e for e in result if e.kind == kind]
        if last_n:
            result = result[-last_n:]
        return result

    def context_for_actor(self, actor: str, *, last_n: int = 20) -> dict[str, Any]:
        """Compact context an agent should load before acting — traits + history."""
        traits = self.traits_registry.get(actor)
        recent = self.traverse_history(last_n=last_n)
        scene = self.current_scene()
        return {
            "actor": actor,
            "traits": (traits.trait_summary() if traits else None),
            "traits_detail": (traits.__dict__ if traits else None),
            "active_scene": (scene.title if scene else None),
            "scene_objective": (scene.objective if scene else None),
            "recent_effects": [
                {"id": e.effect_id, "kind": e.kind, "actor": e.actor, "summary": e.summary, "round": e.round}
                for e in recent
            ],
            "allies": [k for k in self.campaign.inner.players if k != actor],
            "adversaries": list(self.campaign.inner.monsters.keys()),
        }
