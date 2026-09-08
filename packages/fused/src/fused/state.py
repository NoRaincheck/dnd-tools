"""FusedState — campaign with traits separate from event/effect state.

Wraps dnd_campaign.CampaignState (which itself wraps dnd_tools.GameState)
for authoritative mechanics, but keeps:
  - traits_registry: dict[name -> CharacterTraits]  (stable, separate)
  - scenes: list[Scene]                             (narrative structure)
  - effects: list[Effect]                           (append-only event log)

Persistence is via canonical JSONL event log (events.jsonl) + periodic
snapshots (snapshots/<seq>.json) + manifest.json. DB projections
(projections/campaign.db) are derived and idempotent — rebuildable from log.

Determinism: every roll goes through dnd_tools.dice seeded RNG.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dnd_campaign.state import CampaignState
from dnd_tools.dice import seed as dice_seed

from .models import CharacterTraits, Effect, Scene


class FusedState:
    """Long-horizon fused state with event-sourced persistence."""

    def __init__(
        self,
        seed_val: int = 0,
        map_w: int = 20,
        map_h: int = 20,
        max_history: int = 100,
        bundle_root: str | Path | None = None,
        event_log: str | Path | None = None,
        snapshot_every: int = 50,
    ):
        self.seed = seed_val
        dice_seed(seed_val)
        self.campaign = CampaignState(seed_val=seed_val, map_w=map_w, map_h=map_h, max_history=max_history)
        self.traits_registry: dict[str, CharacterTraits] = {}
        self.scenes: list[Scene] = []
        self.active_scene_id: str | None = None
        self.effects: list[Effect] = []
        self._effect_counter: int = 0

        # --- event log layout ---
        # bundle_root is the campaign directory: events.jsonl + snapshots/ + manifest.json + projections/
        # If neither bundle_root nor event_log is given, state is ephemeral (no file I/O) — useful for unit tests.
        self.bundle_root = Path(bundle_root) if bundle_root else None
        if event_log is not None:
            self.event_log_path: Path | None = Path(event_log)
        elif self.bundle_root is not None:
            self.event_log_path = self.bundle_root / "events.jsonl"
        else:
            self.event_log_path = None

        if self.bundle_root is not None:
            self.snapshots_dir: Path | None = self.bundle_root / "snapshots"
            self.manifest_path: Path | None = self.bundle_root / "manifest.json"
            self.projection_path: Path | None = self.bundle_root / "projections" / "campaign.db"
        elif self.event_log_path is not None:
            self.snapshots_dir = self.event_log_path.parent / "snapshots"
            self.manifest_path = self.event_log_path.parent / "manifest.json"
            self.projection_path = self.event_log_path.parent / "projections" / "campaign.db"
        else:
            self.snapshots_dir = None
            self.manifest_path = None
            self.projection_path = None

        self._snapshot_every = snapshot_every

    # -- internal event log helpers ---------------------------------------
    def _ensure_dirs(self) -> None:
        if self.event_log_path is None:
            return
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        if self.snapshots_dir is not None:
            self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        if self.projection_path is not None:
            self.projection_path.parent.mkdir(parents=True, exist_ok=True)

    def _append_event(self, evt: dict[str, Any]) -> None:
        if self.event_log_path is None:
            return
        from .events import append_event

        self._ensure_dirs()
        append_event(self.event_log_path, evt)

    def _maybe_snapshot(self) -> Path | None:
        if self.event_log_path is None or self.snapshots_dir is None:
            return None
        if len(self.effects) > 0 and len(self.effects) % self._snapshot_every == 0:
            return self.take_snapshot()
        return None

    def _update_manifest(self, snapshot_ref: str | None = None) -> None:
        if self.event_log_path is None:
            return
        from .events import write_manifest

        head_id = self.effects[-1].effect_id if self.effects else None
        write_manifest(
            self.event_log_path.parent,
            head_seq=len(self.effects),
            head_id=head_id,
            snapshot_ref=snapshot_ref,
            events_path=self.event_log_path,
        )

    # -- traits --------------------------------------------------------
    def register_traits(self, traits: CharacterTraits) -> None:
        self.traits_registry[traits.name] = traits
        # also record as event for replayability
        self.record_effect(
            "trait-register",
            traits.name,
            f"Registered traits for {traits.name}: {traits.trait_summary()}",
            payload={"traits": traits.traits, "archetype": traits.archetype, "ancestry": traits.ancestry},
            _event_type="fused.trait.registered",
        )

    def get_traits(self, name: str) -> CharacterTraits | None:
        return self.traits_registry.get(name)

    # -- scenes --------------------------------------------------------
    def add_scene(self, scene: Scene) -> Scene:
        self.scenes.append(scene)
        self.active_scene_id = scene.scene_id
        self.campaign.campaign_meta["scenes"] = len(self.scenes)
        self.campaign.campaign_meta["active_scene"] = scene.scene_id
        from dataclasses import asdict

        self.record_effect(
            "scene-create",
            "GM",
            f"Scene {scene.scene_id}: {scene.title} — {scene.objective}",
            payload={"scene": asdict(scene), "location": scene.location, "threat": scene.threat},
            scene_id=scene.scene_id,
            _event_type="fused.scene.created",
        )
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
        _event_type: str | None = None,
        _snapshot_ref: str | None = None,
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
        for s in self.scenes:
            if s.scene_id == sid:
                s.effect_ids.append(eid)
                break
        self.campaign.inner.add_transcript(f"[effect {eid}] {actor} {kind}: {summary}")

        # append to canonical log
        from .events import make_event

        # choose CloudEvents type: fused.effect.* vs explicit
        if _event_type is not None:
            ce_type = _event_type
        elif kind == "triple-o":
            ce_type = "fused.effect.triple_o"
        elif kind in ("long-rest", "short-rest"):
            ce_type = "fused.campaign.rest"
        else:
            ce_type = "fused.effect.recorded"
        cur = self.current_scene()
        evt = make_event(
            effect_id=eid,
            type=ce_type,
            actor=actor,
            scene_id=sid,
            kind=kind,
            summary=summary,
            payload=dict(payload or {}),
            seed=self.seed,
            round=self.campaign.inner.round,
            scene_title=cur.title if cur else None,
        )
        if _snapshot_ref:
            evt["snapshot_ref"] = _snapshot_ref
        try:
            self._append_event(evt)
        except Exception:
            pass
        self._maybe_snapshot()
        self._update_manifest()
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
        self.traits_registry = {k: CharacterTraits(**v) for k, v in snap.get("traits", {}).items()}
        from .models import SceneStatus

        scenes: list[Scene] = []
        for d in snap.get("scenes", []):
            if isinstance(d.get("status"), str):
                try:
                    d["status"] = SceneStatus(d["status"])
                except Exception:
                    d["status"] = SceneStatus.planned
            scenes.append(Scene(**d))
        self.scenes = scenes
        self.effects = [Effect(**e) for e in snap.get("effects", [])]
        self.active_scene_id = snap.get("active_scene_id")
        self._effect_counter = int(snap.get("effect_counter", len(self.effects)))

    # -- file snapshot helpers --------------------------------------------
    def take_snapshot(self, seq: int | None = None) -> Path:
        """Write full snapshot to ``snapshots/<seq>.json`` and log a snapshot event."""
        if self.event_log_path is None or self.snapshots_dir is None:
            # ephemeral state — return a temp path without I/O
            raise RuntimeError("cannot take snapshot without bundle_root/event_log")
        from .events import make_event, snapshot_hash, write_snapshot

        self._ensure_dirs()
        s = seq if seq is not None else len(self.effects)
        snap = self.snapshot()
        snap_path = write_snapshot(self.snapshots_dir, snap, s)
        h = snapshot_hash(snap)
        # log snapshot event (for manifest + hash attestation)
        eid = f"snapshot-{s:05d}-{h[:8]}"
        evt = make_event(
            effect_id=eid,
            type="fused.snapshot.taken",
            actor="system",
            scene_id=self.active_scene_id or "scene-00",
            kind="snapshot",
            summary=f"Snapshot at seq {s}",
            payload={},
            seed=self.seed,
            round=self.campaign.inner.round,
            extra_data={"snapshot_hash": h, "seq": s},
            snapshot_ref=str(snap_path.relative_to(self.event_log_path.parent))
            if snap_path.is_relative_to(self.event_log_path.parent)
            else str(snap_path),
        )
        try:
            self._append_event(evt)
        except Exception:
            pass
        self._update_manifest(snapshot_ref=str(snap_path))
        return snap_path

    @classmethod
    def from_log(
        cls,
        events_path: str | Path,
        snapshots_dir: str | Path | None = None,
        at_seq: int | None = None,
    ) -> FusedState:
        """Replay ``events.jsonl`` (+ latest snapshot before ``at_seq``) into a new FusedState."""
        from .events import iter_events, read_snapshot

        ep = Path(events_path)
        sdir = Path(snapshots_dir) if snapshots_dir else ep.parent / "snapshots"

        # find latest snapshot <= at_seq
        latest_snap: dict[str, Any] | None = None
        latest_seq = -1
        if sdir.exists():
            for p in sorted(sdir.glob("*.json")):
                try:
                    seq = int(p.stem)
                except ValueError:
                    continue
                if at_seq is not None and seq > at_seq:
                    continue
                if seq > latest_seq:
                    latest_seq = seq
                    try:
                        latest_snap = read_snapshot(p)
                    except Exception:  # noqa: S112
                        continue

        seed = 0
        if latest_snap is not None:
            seed = latest_snap.get("seed", latest_snap.get("campaign_snapshot", {}).get("seed", 0))
        fs = cls(seed_val=seed)
        if latest_snap is not None:
            fs.restore(latest_snap)

        # replay events after snapshot
        for idx, evt in enumerate(iter_events(ep)):
            seq = idx
            if seq <= latest_seq:
                continue
            if at_seq is not None and seq >= at_seq:
                break
            if evt.get("type") == "fused.snapshot.taken":
                continue
            fs._apply_event(evt)
        return fs

    def _apply_event(self, evt: dict[str, Any]) -> None:
        """Apply a single log event to in-memory state (for replay). No I/O."""
        ce_type = evt.get("type", "")
        fused = evt.get("fused", {})
        data = evt.get("data", {})
        payload = data.get("payload", {})
        actor = evt.get("subject", "")
        scene_id = fused.get("scene_id", "scene-00")
        kind = fused.get("kind", "")
        summary = data.get("summary", "")
        eid = evt.get("id", "")

        if ce_type == "fused.trait.registered":
            # payload contains traits list; reconstruct minimal CharacterTraits
            name = actor
            if name not in self.traits_registry:
                self.traits_registry[name] = CharacterTraits(
                    name=name,
                    archetype=str(payload.get("archetype", "fighter")),
                    ancestry=str(payload.get("ancestry", "human")),
                    traits=list(payload.get("traits", [])),
                )
            # still record effect for traversal
            eff = Effect(
                effect_id=eid,
                scene_id=scene_id,
                actor=actor,
                kind=kind,
                summary=summary,
                round=int(fused.get("round", 0)),
                payload=dict(payload),
            )
            self.effects.append(eff)
            self._effect_counter = max(self._effect_counter, len(self.effects))
        elif ce_type == "fused.scene.created":
            scene_data = payload.get("scene")
            if scene_data and not any(s.scene_id == scene_data.get("scene_id") for s in self.scenes):
                from .models import SceneStatus

                if isinstance(scene_data.get("status"), str):
                    try:
                        scene_data["status"] = SceneStatus(scene_data["status"])
                    except Exception:
                        scene_data["status"] = SceneStatus.planned
                try:
                    sc = Scene(**scene_data)
                    self.scenes.append(sc)
                    self.active_scene_id = sc.scene_id
                except Exception:
                    pass
            eff = Effect(
                effect_id=eid,
                scene_id=scene_id,
                actor=actor,
                kind=kind,
                summary=summary,
                round=int(fused.get("round", 0)),
                payload=dict(payload),
            )
            self.effects.append(eff)
            for s in self.scenes:
                if s.scene_id == scene_id:
                    if eid not in s.effect_ids:
                        s.effect_ids.append(eid)
                    break
            self._effect_counter = max(self._effect_counter, len(self.effects))
        else:
            # generic effect
            eff = Effect(
                effect_id=eid,
                scene_id=scene_id,
                actor=actor,
                kind=kind,
                summary=summary,
                round=int(fused.get("round", 0)),
                turn_actor=fused.get("turn_actor"),
                payload=dict(payload),
            )
            self.effects.append(eff)
            for s in self.scenes:
                if s.scene_id == scene_id:
                    if eid not in s.effect_ids:
                        s.effect_ids.append(eid)
                    break
            self._effect_counter = max(self._effect_counter, len(self.effects))

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

    # -- projection (idempotent) ------------------------------------------
    def rebuild_projection(self, db_path: str | Path | None = None) -> Path:
        """Rebuild SQLite projection from canonical log. Idempotent."""
        if self.event_log_path is None:
            raise RuntimeError("cannot build projection without event_log")
        from .projection import build_projection

        db = Path(db_path) if db_path else self.projection_path
        if db is None:
            raise RuntimeError("no projection path")
        return build_projection(self.event_log_path, db)

    def validate_log(self) -> list[str]:
        if self.event_log_path is None:
            return []
        from .events import validate_log

        return validate_log(self.event_log_path)

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
