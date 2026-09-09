"""Canonical JSONL event log — replaces OKF bundle as source of truth.

One JSON object per line (https://jsonlines.org/), CloudEvents-compatible
envelope (specversion/id/source/type/time/subject) + fused extension + data.
Append-only, git-diffable, jq/duckdb/sqlite-queryable, replayable into
FusedState via snapshots.

Schema: see ``schemas/event.schema.json``. This module is the single writer;
projections and snapshots are derived and rebuildable.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import pathlib as _pl
from typing import Any

REQUIRED_TOP_LEVEL = ("specversion", "id", "source", "type", "time", "subject", "fused", "data")

# Controlled vocabulary for ``type`` — CloudEvents type
VALID_TYPES = {
    "fused.trait.registered",
    "fused.scene.created",
    "fused.scene.beat_advanced",
    "fused.scene.resolved",
    "fused.effect.recorded",
    "fused.effect.triple_o",
    "fused.snapshot.taken",
    "fused.campaign.rest",
    "fused.campaign.checkpoint",
}


def _iso_now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).isoformat().replace("+00:00", "Z")


def make_event(
    *,
    effect_id: str,
    type: str,
    actor: str,
    scene_id: str,
    kind: str,
    summary: str,
    payload: dict[str, Any] | None = None,
    seed: int = 0,
    round: int = 0,
    beats_index: int | None = None,
    scene_title: str | None = None,
    source: str | None = None,
    extra_data: dict[str, Any] | None = None,
    snapshot_ref: str | None = None,
) -> dict[str, Any]:
    """Build a CloudEvents-compatible event dict.

    ``effect_id`` becomes CloudEvents ``id``. ``actor`` becomes ``subject``.
    ``fused`` extension holds deterministic replay fields (seed/round/scene).
    """
    if type not in VALID_TYPES and not type.startswith("fused."):
        raise ValueError(f"unknown event type: {type}")
    now = _iso_now()
    src = source or f"fused://campaign/{scene_id}"
    fused: dict[str, Any] = {
        "seed": seed,
        "round": round,
        "scene_id": scene_id,
        "kind": kind,
    }
    if scene_title is not None:
        fused["scene_title"] = scene_title
    if beats_index is not None:
        fused["beats_index"] = beats_index
    data: dict[str, Any] = {"summary": summary, "payload": payload or {}}
    if extra_data:
        data.update(extra_data)
    evt: dict[str, Any] = {
        "specversion": "1.0",
        "id": effect_id,
        "source": src,
        "type": type,
        "time": now,
        "subject": actor,
        "fused": fused,
        "data": data,
        "generated": {"by": "process:fused", "at": now},
        "tags": ["effect", kind, scene_id] if kind else ["effect", scene_id],
    }
    if snapshot_ref is not None:
        evt["snapshot_ref"] = snapshot_ref
    else:
        evt["snapshot_ref"] = None
    return evt


def validate_event(evt: dict[str, Any]) -> list[str]:
    """Lightweight schema check — returns error strings (empty = valid)."""
    errs: list[str] = []
    for k in REQUIRED_TOP_LEVEL:
        if k not in evt:
            errs.append(f"missing required field: {k}")
    if evt.get("specversion") != "1.0":
        errs.append("specversion must be '1.0'")
    for f in ("id", "source", "type", "time", "subject"):
        v = evt.get(f)
        if not isinstance(v, str) or not v.strip():
            errs.append(f"{f} must be non-empty string")
    if not isinstance(evt.get("fused"), dict):
        errs.append("fused must be object")
    if not isinstance(evt.get("data"), dict):
        errs.append("data must be object")
    t = evt.get("type", "")
    if isinstance(t, str) and t not in VALID_TYPES and not t.startswith("fused."):
        errs.append(f"unknown type: {t}")
    return errs


def append_event(log_path: str | _pl.Path, evt: dict[str, Any]) -> _pl.Path:
    """Atomically append one event as a JSON line. Validates before write."""
    errs = validate_event(evt)
    if errs:
        raise ValueError(f"event validation failed: {errs}")
    p = _pl.Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(evt, separators=(",", ":"), default=str)
    # atomic append + fsync for durability (WAL semantics)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        try:
            import os

            os.fsync(f.fileno())
        except Exception:
            pass
    return p


def iter_events(log_path: str | _pl.Path) -> Any:
    """Yield events in order; skips blank lines."""
    p = _pl.Path(log_path)
    if not p.exists():
        return
        yield  # make it a generator
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def read_all(log_path: str | _pl.Path) -> list[dict[str, Any]]:
    return list(iter_events(log_path))


def snapshot_hash(snap: dict[str, Any]) -> str:
    """Stable sha256 of canonical JSON snapshot (for attestation)."""
    blob = json.dumps(snap, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(blob).hexdigest()


def write_snapshot(
    snapshots_dir: str | _pl.Path,
    snap: dict[str, Any],
    seq: int,
) -> _pl.Path:
    """Write full FusedState snapshot to ``snapshots/<seq>.json``."""
    d = _pl.Path(snapshots_dir)
    d.mkdir(parents=True, exist_ok=True)
    name = f"{seq:05d}.json"
    p = d / name
    payload = {"seq": seq, "hash": snapshot_hash(snap), "snapshot": snap}
    p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return p


def read_snapshot(path: str | _pl.Path) -> dict[str, Any]:
    data = json.loads(_pl.Path(path).read_text(encoding="utf-8"))
    # support both wrapped {snapshot: ...} and raw snapshot
    return data.get("snapshot", data)


def write_manifest(
    bundle_root: str | _pl.Path,
    *,
    head_seq: int,
    head_id: str | None,
    snapshot_ref: str | None,
    events_path: str | _pl.Path,
) -> _pl.Path:
    """Write ``manifest.json`` pointer for cheap ``restore(latest_snapshot)+replay``."""
    root = _pl.Path(bundle_root)
    root.mkdir(parents=True, exist_ok=True)
    # sha256 of events file for integrity
    import hashlib as _hl

    ep = _pl.Path(events_path)
    h = ""
    if ep.exists():
        h = _hl.sha256(ep.read_bytes()).hexdigest()
    m = {
        "head_seq": head_seq,
        "head_id": head_id,
        "snapshot_ref": snapshot_ref,
        "events_sha256": h,
        "generated_at": _iso_now(),
    }
    p = root / "manifest.json"
    p.write_text(json.dumps(m, indent=2), encoding="utf-8")
    return p


def validate_log(log_path: str | _pl.Path) -> list[str]:
    """Validate entire log file — returns error strings."""
    errs: list[str] = []
    for idx, evt in enumerate(iter_events(log_path)):
        e = validate_event(evt)
        if e:
            errs.append(f"line {idx + 1} ({evt.get('id', '?')}): {'; '.join(e)}")
    return errs
