#!/usr/bin/env python3
"""Render fused knowledge JSONL → single-file HTML via python-liquid.

Usage:
  uv run python scripts/render_fused_knowledge.py --bundle knowledge/fused-demo
  uv run python scripts/render_fused_knowledge.py --bundle knowledge/fused-demo --out knowledge/fused-demo/index.html
  uv run python scripts/render_fused_knowledge.py --bundle knowledge/fused-demo --out packages/fused/docs/knowledge.html

The template is packages/fused/templates/knowledge.liquid (single-file, inline CSS/JS, no external deps).
Output is a self-contained HTML that embeds all knowledge (events pretty-printed via Liquid loops + JS filters).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "packages/fused/templates/knowledge.liquid"
DEFAULT_BUNDLE = ROOT / "knowledge/fused-demo"


def _pretty(obj: object) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


def load_bundle(bundle: pathlib.Path) -> dict:
    bundle = pathlib.Path(bundle)
    events_path = bundle / "events.jsonl"
    manifest_path = bundle / "manifest.json"
    db_path = bundle / "projections/campaign.db"
    # snapshots count
    snapshots = list((bundle / "snapshots").glob("*.json")) if (bundle / "snapshots").exists() else []

    events: list[dict] = []
    if events_path.exists():
        with events_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except Exception:
                    continue

    # add pretty for template
    for e in events:
        e["pretty"] = _pretty(e)

    # stats
    by_type = Counter(e.get("type", "") for e in events)
    by_kind = Counter(e.get("fused", {}).get("kind", "") for e in events)
    stats = {
        "by_type": [{"type": k or "(empty)", "count": v} for k, v in sorted(by_type.items())],
        "by_kind": [{"kind": k or "(empty)", "count": v} for k, v in sorted(by_kind.items())],
    }

    # scenes from events payload.scene
    scenes: list[dict] = []
    seen_scenes: set[str] = set()
    for e in events:
        if e.get("type") == "fused.scene.created":
            sc = e.get("data", {}).get("payload", {}).get("scene")
            if isinstance(sc, dict) and sc.get("scene_id") not in seen_scenes:
                seen_scenes.add(sc["scene_id"])
                scenes.append(sc)

    # traits from events
    traits: list[dict] = []
    for e in events:
        if e.get("type") == "fused.trait.registered":
            payload = e.get("data", {}).get("payload", {})
            traits.append(
                {
                    "name": e.get("subject", ""),
                    "ancestry": payload.get("ancestry", ""),
                    "background": payload.get("background", ""),
                    "archetype": payload.get("archetype", ""),
                    "traits": payload.get("traits", []),
                }
            )

    # choices from events (choice payload)
    choices: list[dict] = []
    for e in events:
        if e.get("type", "").startswith("fused.choice."):
            choice = e.get("data", {}).get("payload", {}).get("choice") or {}
            if isinstance(choice, dict) and choice.get("choice_id"):
                choices.append(
                    {
                        "choice_id": choice.get("choice_id", ""),
                        "scene_id": choice.get("scene_id", ""),
                        "actor": choice.get("actor", ""),
                        "situation": choice.get("situation", ""),
                        "obvious": choice.get("obvious", ""),
                        "option": choice.get("option", ""),
                        "odd": choice.get("odd", ""),
                        "position": choice.get("position", ""),
                        "effect": choice.get("effect", ""),
                        "trivial": choice.get("trivial", False),
                        "category": choice.get("category", ""),
                        "choice_text": choice.get("choice_text", ""),
                        "roll": choice.get("roll"),
                        "rolls": choice.get("rolls", []),
                        "ticks": choice.get("ticks", 0),
                        "resolved_via": choice.get("resolved_via", ""),
                        "pretty": _pretty(choice),
                    }
                )
    # dedupe choices by id keep last
    dedup: dict[str, dict] = {}
    for c in choices:
        dedup[c["choice_id"]] = c
    choices = list(dedup.values())

    # wounds from payload.wound
    wounds: list[dict] = []
    for e in events:
        wound = e.get("data", {}).get("payload", {}).get("wound")
        if wound is not None:
            wounds.append(
                {
                    "actor": e.get("subject", ""),
                    "scene_id": e.get("fused", {}).get("scene_id", ""),
                    "wound": str(wound),
                    "summary": e.get("data", {}).get("summary", ""),
                }
            )

    # clocks: aggregate from scene clocks + clock-tick events last state
    clocks: dict[str, dict] = {}
    for sc in scenes:
        for c in sc.get("clocks", []) or []:
            if isinstance(c, dict) and c.get("name"):
                clocks[c["name"]] = {
                    "name": c["name"],
                    "segments": c.get("segments", 6),
                    "ticks": c.get("ticks", 0),
                    "kind": c.get("kind", "obstacle"),
                    "completed": c.get("ticks", 0) >= c.get("segments", 6),
                }

    # also update from clock-tick events
    for e in events:
        if e.get("fused", {}).get("kind") == "clock-tick":
            payload = e.get("data", {}).get("payload", {}) or {}
            name = payload.get("name", "")
            if name:
                clocks[name] = {
                    "name": name,
                    "segments": payload.get("segments", clocks.get(name, {}).get("segments", 6)),
                    "ticks": payload.get("after", payload.get("ticks", 0)),
                    "kind": clocks.get(name, {}).get("kind", "obstacle"),
                    "completed": payload.get("after", 0) >= payload.get("segments", 6),
                }

    clocks_list = list(clocks.values())

    # manifest
    manifest: dict = {}
    manifest_pretty = "{}"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_pretty = _pretty(manifest)
        except Exception:
            manifest = {}
    manifest["pretty"] = manifest_pretty

    # raw preview first 20 lines pretty
    raw_preview: list[str] = []
    if events_path.exists():
        with events_path.open(encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 20:
                    break
                try:
                    raw_preview.append(_pretty(json.loads(line)))
                except Exception:
                    raw_preview.append(line.strip())

    # filter types/kinds for dropdowns
    filter_types = sorted({e.get("type", "") for e in events if e.get("type")})
    filter_kinds = sorted({e.get("fused", {}).get("kind", "") for e in events if e.get("fused", {}).get("kind")})

    # validation
    validation_errors: list[str] = []
    try:
        from fused.events import validate_log

        if events_path.exists():
            validation_errors = validate_log(events_path)
    except Exception:
        validation_errors = []

    # events sha
    events_sha = ""
    if events_path.exists():
        events_sha = hashlib.sha256(events_path.read_bytes()).hexdigest()

    campaign = {
        "title": "Fused Campaign — Knowledge Viewer",
        "subtitle": "JSONL · CloudEvents · Snapshots · Projections",
        "bundle": str(bundle.relative_to(ROOT)) if bundle.is_relative_to(ROOT) else str(bundle),
        "events_path": str(events_path.relative_to(ROOT)) if events_path.is_relative_to(ROOT) else str(events_path),
        "manifest_path": str(manifest_path.relative_to(ROOT))
        if manifest_path.is_relative_to(ROOT)
        else str(manifest_path),
        "db_path": str(db_path.relative_to(ROOT)) if db_path.is_relative_to(ROOT) else str(db_path),
        "seed": (events[0].get("fused", {}).get("seed", "") if events else ""),
        "events_count": len(events),
        "scenes_count": len(scenes),
        "traits_count": len(traits),
        "snapshots_count": len(snapshots),
        "events_sha256": events_sha,
        "manifest_head": manifest.get("head_id", ""),
        "validation_errors": validation_errors,
    }

    # choices stats
    say_yes = sum(1 for c in choices if c.get("trivial"))
    rolled = len(choices) - say_yes
    odd = sum(1 for c in choices if c.get("category") == "odd")
    stats["choices_say_yes"] = say_yes
    stats["choices_rolled"] = rolled
    stats["choices_odd"] = odd

    return {
        "campaign": campaign,
        "scenes": scenes,
        "traits": traits,
        "choices": choices,
        "events": events,
        "wounds": wounds,
        "clocks": clocks_list,
        "manifest": manifest,
        "raw_preview": raw_preview,
        "filter_types": filter_types,
        "filter_kinds": filter_kinds,
        "stats": stats,
    }


def render(bundle: pathlib.Path, out: pathlib.Path) -> pathlib.Path:
    try:
        from liquid import Template
    except ImportError as e:
        raise SystemExit("Missing python-liquid. Install with: uv add --group dev python-liquid") from e

    if not TEMPLATE_PATH.exists():
        raise SystemExit(f"Template not found: {TEMPLATE_PATH}")

    ctx = load_bundle(bundle)
    # add render meta
    try:
        import importlib.metadata as im

        lv = im.version("python-liquid")
    except Exception:
        lv = "2.x"
    ctx["render_date"] = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    ctx["liquid_version"] = lv

    src = TEMPLATE_PATH.read_text(encoding="utf-8")
    tmpl = Template(src)
    html = tmpl.render(**ctx)
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Render fused knowledge JSONL → HTML via Liquid")
    p.add_argument("--bundle", type=str, default=str(DEFAULT_BUNDLE), help="Bundle root (default knowledge/fused-demo)")
    p.add_argument("--out", type=str, default="", help="Output HTML path (default <bundle>/index.html)")
    args = p.parse_args()
    bundle = pathlib.Path(args.bundle)
    out = pathlib.Path(args.out) if args.out else bundle / "index.html"
    rendered = render(bundle, out)
    print(f"Rendered {TEMPLATE_PATH} + {bundle} -> {rendered} ({rendered.stat().st_size} bytes)")
    # also build projection if missing for completeness
    try:
        from fused.projection import build_projection

        db = bundle / "projections/campaign.db"
        if (bundle / "events.jsonl").exists():
            build_projection(bundle / "events.jsonl", db)
            print(f"Projection ready: {db}")
    except Exception as e:
        print(f"Projection skipped: {e}")


if __name__ == "__main__":
    main()
