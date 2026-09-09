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
from dnd_tools.dice import roll_dice
from dnd_tools.dice import seed as dice_seed

from .models import (
    CONSEQUENCE_TABLE,
    EFFECT_TICKS,
    CharacterTraits,
    Clock,
    Effect,
    EffectLevel,
    Position,
    Scene,
)


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
        # joint SRD: clocks + position/effect gates + stress
        self.clocks: dict[str, Clock] = {}
        self._pending: dict[str, dict[str, str]] = {}  # actor -> {action, position, effect}
        self._stress: dict[str, int] = {}  # actor -> stress 0-9
        self._stress_max: int = 9

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

    # -- clocks (joint SRD beats→clocks) ---------------------------------
    def set_clock(self, name: str, segments: int = 6, kind: str = "obstacle") -> Clock:
        clk = self.clocks.get(name)
        if clk:
            clk.segments = int(segments)
            clk.kind = kind
        else:
            clk = Clock(name=name, segments=int(segments), kind=kind)
            self.clocks[name] = clk
        # also mirror into current scene clocks if active
        cur = self.current_scene()
        if cur is not None and not any(c.name == name for c in cur.clocks):
            cur.clocks.append(Clock(name=name, segments=int(segments), kind=kind))
        self.record_effect(
            "clock-set",
            "GM",
            f"Clock {name} {clk.ticks}/{clk.segments}",
            payload={"name": name, "segments": segments, "kind": kind},
        )
        return clk

    def tick_clock(self, name: str, ticks: int) -> dict[str, Any]:
        clk = self.clocks.get(name)
        if not clk:
            clk = self.set_clock(name)
        before = clk.ticks
        clk.add_ticks(int(ticks))
        # sync scene copy
        for s in self.scenes:
            for c in s.clocks:
                if c.name == name:
                    c.ticks = clk.ticks
        self.record_effect(
            "clock-tick",
            "GM",
            f"Clock {name} {before}→{clk.ticks}/{clk.segments}",
            payload={
                "name": name,
                "ticks": int(ticks),
                "before": before,
                "after": clk.ticks,
                "completed": clk.completed,
            },
        )
        return {
            "name": name,
            "before": before,
            "after": clk.ticks,
            "completed": clk.completed,
            "segments": clk.segments,
        }

    def get_clock(self, name: str) -> Clock | None:
        return self.clocks.get(name)

    def visualize_clocks(self) -> str:
        if not self.clocks:
            return "(no clocks)"
        lines = []
        for k, v in self.clocks.items():
            filled = "■" * v.ticks + "□" * (v.segments - v.ticks)
            lines.append(f"{k} [{v.kind}] {filled} {v.ticks}/{v.segments} {'✓' if v.completed else ''}")
        return "\n".join(lines)

    # -- position/effect gate (must precede action_roll) -------------------
    def set_position_and_effect(self, actor: str, action: str, position: str, effect: str) -> dict[str, Any]:
        pos = position.lower()
        eff = effect.lower()
        if pos not in {p.value for p in Position}:
            raise ValueError(f"position must be one of {[p.value for p in Position]}, got {position}")
        if eff not in {e.value for e in EffectLevel}:
            raise ValueError(f"effect must be one of {[e.value for e in EffectLevel]}, got {effect}")
        self._pending[actor] = {"action": action, "position": pos, "effect": eff}
        self.campaign.inner.add_transcript(f"[gate {actor}] {action} {pos}/{eff}")
        return {"valid": True, "actor": actor, "action": action, "position": pos, "effect": eff}

    def _clear_pending(self, actor: str) -> None:
        self._pending.pop(actor, None)

    # -- gated resolution (Blades-style pool over dnd_tools dice) ----------
    def action_roll(
        self,
        actor: str,
        clock: str | None = None,
        _pending_action: str | None = None,
        _pending_position: str | None = None,
        _pending_effect: str | None = None,
    ) -> dict[str, Any]:
        pending = self._pending.get(actor, {})
        action = _pending_action or pending.get("action")
        position = _pending_position or pending.get("position")
        effect = _pending_effect or pending.get("effect")
        if not action or not position or not effect:
            return {
                "valid": False,
                "reason": "Position/effect not set. Call set_position_and_effect(actor, action, position, effect) before action_roll.",
                "hint": "set_position_and_effect(actor='A', action='Prowl', position='risky', effect='standard')",
            }
        # derive pool: baseline 2 + (traits count //3) capped 4, mirrors blades action rating without requiring playbook
        traits = self.traits_registry.get(actor)
        base = 2
        if traits:
            base = min(4, 2 + len(traits.traits) // 2 + len(traits.favored_skills) // 3)
        pool = base
        # zero-dice case
        if pool <= 0:
            rolls = [roll_dice("1d6"), roll_dice("1d6")]
            highest = min(rolls)
            critical = False
            outcome = "failure" if highest <= 3 else "partial" if highest <= 5 else "success"
            # zero dice cannot crit in blades — enforce
            critical = False
        else:
            rolls = [roll_dice("1d6") for _ in range(pool)]
            highest = max(rolls)
            crit_count = rolls.count(6)
            critical = crit_count >= 2
            if critical:
                outcome = "critical"
            elif highest == 6:
                outcome = "success"
            elif highest >= 4:
                outcome = "partial"
            else:
                outcome = "failure"
        # consequence per table
        if outcome in ("success", "critical"):
            consequence: list[str] = []
        elif outcome == "partial":
            consequence = list(CONSEQUENCE_TABLE[position]["partial"])
        else:
            consequence = list(CONSEQUENCE_TABLE[position]["failure"])
        # ticks
        base_ticks = EFFECT_TICKS.get(effect, 2)
        if critical:
            # +1 tier bump
            order = ["zero", "limited", "standard", "great", "extreme"]
            try:
                idx = order.index(effect)
                bumped = order[min(len(order) - 1, idx + 1)]
                ticks = EFFECT_TICKS[bumped]
            except ValueError:
                ticks = base_ticks + 1
        else:
            ticks = base_ticks
        if outcome == "partial" and any("reduced effect" in c for c in consequence):
            ticks = max(0, ticks - 1)
        if outcome == "failure":
            ticks = 0
        # tick clock if supplied
        clock_info = None
        if clock:
            if clock not in self.clocks:
                self.set_clock(clock, segments=6)
            before = self.clocks[clock].ticks
            self.clocks[clock].add_ticks(ticks)
            # sync scene copy
            for s in self.scenes:
                for c in s.clocks:
                    if c.name == clock:
                        c.ticks = self.clocks[clock].ticks
            clock_info = {
                "clock": clock,
                "ticks": ticks,
                "before": before,
                "after": self.clocks[clock].ticks,
                "completed": self.clocks[clock].completed,
            }
        payload = {
            "valid": True,
            "actor": actor,
            "action": action,
            "position": position,
            "effect": effect,
            "pool": pool,
            "rolls": rolls,
            "highest": highest,
            "critical": critical,
            "outcome": outcome,
            "consequence": consequence,
            "consequence_severity": position,
            "ticks": ticks,
            "clock": clock_info,
            "requires_resistance": len(consequence) > 0,
        }
        # record as effect so history captures the roll
        self.record_effect(
            "action-roll",
            actor,
            f"{action} {position}/{effect} → {outcome} (highest {highest}, ticks {ticks})",
            payload={
                "action_roll": payload,
                "position": position,
                "effect": effect,
                "outcome": outcome,
                "ticks": ticks,
                "clock": clock,
            },
        )
        self._clear_pending(actor)
        self.campaign.inner.add_transcript(f"[action {actor}] {payload}")
        return payload

    def resistance_roll(self, actor: str, attribute: str = "Resolve") -> dict[str, Any]:
        attr = attribute.capitalize()
        rating = 2  # baseline; could derive from traits
        # roll = roll pool (like blades Insight/Prowess/Resolve) — simple 1d6 pool
        ch = self.traits_registry.get(actor)
        if ch and attr.lower() in [s.lower() for s in ch.favored_skills]:
            rating = 3
        rolls = [roll_dice("1d6") for _ in range(max(1, rating))]
        highest = max(rolls)
        critical = rolls.count(6) >= 2
        cost = 6 - highest
        if critical:
            cost = max(0, cost - 1)  # clear 1
        before = self._stress.get(actor, 0)
        after = min(self._stress_max, before + cost)
        # trauma gate: overflow would be stress>max, but we cap and mark trauma notion via effect
        self._stress[actor] = after
        self.campaign.inner.add_transcript(f"[resist {actor}] {highest} cost {cost} stress {before}->{after}")
        self.record_effect(
            "resistance-roll",
            actor,
            f"Resist with {attr}: {highest} → {cost} stress",
            payload={
                "attribute": attr,
                "highest": highest,
                "cost": cost,
                "before": before,
                "after": after,
                "critical": critical,
            },
        )
        return {
            "actor": actor,
            "attribute": attr,
            "highest": highest,
            "rolls": rolls,
            "cost": cost,
            "before": before,
            "after": after,
            "critical": critical,
        }

    def mark_stress(self, actor: str, delta: int) -> dict[str, Any]:
        before = self._stress.get(actor, 0)
        after = max(0, min(self._stress_max, before + int(delta)))
        self._stress[actor] = after
        return {"actor": actor, "before": before, "after": after, "delta": delta}

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
        # beats → clocks: if beats exist but no explicit clocks, create a default 6-clock for the objective
        if scene.beats and not scene.clocks:
            # one clock per scene seeded from beats length (beats→segments heuristic)
            segs = 6 if len(scene.beats) <= 3 else 8
            scene.clocks.append(Clock(name=f"{scene.scene_id}-progress", segments=segs, kind="obstacle"))
            for c in scene.clocks:
                self.clocks[c.name] = Clock(name=c.name, segments=c.segments, kind=c.kind, ticks=c.ticks)
        else:
            for c in scene.clocks:
                self.clocks[c.name] = Clock(name=c.name, segments=c.segments, kind=c.kind, ticks=c.ticks)
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

    # -- snapshot / restore (includes traits + scenes + effects + clocks) -------
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
            "clocks": {k: asdict(v) for k, v in self.clocks.items()},
            "stress": dict(self._stress),
        }

    def restore(self, snap: dict[str, Any]) -> None:
        self.seed = snap.get("seed", 0)
        dice_seed(self.seed)
        self.campaign.restore(snap.get("campaign_snapshot", {}))
        self.traits_registry = {k: CharacterTraits(**v) for k, v in snap.get("traits", {}).items()}
        from .models import Clock as _Clock
        from .models import SceneStatus

        scenes: list[Scene] = []
        for d in snap.get("scenes", []):
            if isinstance(d.get("status"), str):
                try:
                    d["status"] = SceneStatus(d["status"])
                except Exception:
                    d["status"] = SceneStatus.planned
            # clocks may be list of dicts — rebuild
            if "clocks" in d and isinstance(d["clocks"], list):
                rebuilt = []
                for c in d["clocks"]:
                    if isinstance(c, dict):
                        try:
                            rebuilt.append(_Clock(**c))
                        except Exception:  # noqa: S112
                            continue
                    elif isinstance(c, _Clock):
                        rebuilt.append(c)
                d["clocks"] = rebuilt
            scenes.append(Scene(**d))
        self.scenes = scenes
        self.effects = [Effect(**e) for e in snap.get("effects", [])]
        self.active_scene_id = snap.get("active_scene_id")
        self._effect_counter = int(snap.get("effect_counter", len(self.effects)))
        # clocks
        raw_clocks = snap.get("clocks", {})
        self.clocks = {}
        for k, v in raw_clocks.items():
            if isinstance(v, dict):
                try:
                    self.clocks[k] = _Clock(**v)
                except Exception:  # noqa: S112
                    continue
            elif isinstance(v, _Clock):
                self.clocks[k] = v
        # if clocks missing but scenes have clocks, hydrate
        if not self.clocks:
            for s in self.scenes:
                for c in s.clocks:
                    if c.name not in self.clocks:
                        self.clocks[c.name] = Clock(name=c.name, segments=c.segments, kind=c.kind, ticks=c.ticks)
        self._stress = dict(snap.get("stress", {}))
        self._pending = {}

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

        # replay events after snapshot — count non-snapshot events, not log index
        # Snapshot events (fused.snapshot.taken) are appended to the log but do
        # not increment self.effects / snapshot seq, so log index drifts from
        # effect count when 3+ snapshots exist. Counting only non-snapshot
        # events avoids duplicate replay (see PR review reproducer: 6 effects
        # with snapshot_every=2 duplicated the last effect).
        replayed = 0
        for evt in iter_events(ep):
            if evt.get("type") == "fused.snapshot.taken":
                continue
            if replayed < latest_seq:
                replayed += 1
                continue
            if at_seq is not None and replayed >= at_seq:
                break
            fs._apply_event(evt)
            replayed += 1
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
            # generic effect — also hydrate clocks/stress if this was a clock effect
            if kind in ("clock-set", "clock-tick", "clock-set", "clock-tick"):
                name = str(payload.get("name", ""))
                if name:
                    if kind == "clock-set":
                        from .models import Clock as _Clk

                        segs = int(payload.get("segments", 6))
                        kind_s = str(payload.get("kind", "obstacle"))
                        self.clocks[name] = _Clk(
                            name=name, segments=segs, kind=kind_s, ticks=int(payload.get("ticks", 0))
                        )
                        for s in self.scenes:
                            for c in s.clocks:
                                if c.name == name:
                                    c.segments = segs
                                    c.kind = kind_s
                                    break
                    elif kind == "clock-tick":
                        clk = self.clocks.get(name)
                        if clk:
                            clk.add_ticks(int(payload.get("ticks", 0)))
                            for s in self.scenes:
                                for c in s.clocks:
                                    if c.name == name:
                                        c.ticks = clk.ticks
                                        break
                        elif "after" in payload:
                            # fallback: create clock with after ticks if missing (replay before snapshot)
                            from .models import Clock as _Clk2

                            segs2 = int(payload.get("segments", 6))
                            self.clocks[name] = _Clk2(name=name, segments=segs2, ticks=int(payload.get("after", 0)))
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
