"""Static site generator from knowledge outputs (JSONL events + state).

Takes a fused ``knowledge/<campaign>`` bundle (events.jsonl + snapshots + manifest)
and emits a fully static, file://-friendly site with rewind/playthrough controls.

Outputs:
  <out_dir>/index.html  — self-contained HTML+CSS+JS (no external deps, no fetch)
  <out_dir>/events.json — copy of events (for jq/externals, optional)
  <out_dir>/data.json   — machine-readable bundle (events + timeline states)

Features:
  - Slider scrub across seq 0..N (0 = before any event, N = after all)
  - Prev/Next, Play/Pause, speed (0.5x/1x/2x), Start/End, keyboard (Space, arrows)
  - Hash deep-link #seq=10
  - Timeline dimming for future events, highlight current
  - State panel shows clocks/traits/scenes/active scene/effects count at seq
  - Filters (type/kind/text) remain, but work with scrub
  - No build step, no server required.

Design constraints:
  - File:// friendly — all data embedded via <script type="application/json"> (no fetch)
  - Derived states computed at build time via FusedState._apply_event replay,
    so JS is purely presentational (no Python reimplementation in JS).
  - Works with missing/empty log; degrades gracefully.

CLI wiring lives in packages/fused/src/fused/cli.py (fused build-site).
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib as _pl
from typing import Any


def _iso_now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).isoformat().replace("+00:00", "Z")


def _capture_state(fs: Any) -> dict[str, Any]:
    """Lightweight snapshot for timeline scrub — JSON-serializable."""
    # fs is FusedState (ephemeral) after applying some prefix
    try:
        clocks = {
            k: {"ticks": v.ticks, "segments": v.segments, "kind": v.kind, "completed": v.completed}
            for k, v in fs.clocks.items()
        }
    except Exception:
        clocks = {}
    try:
        traits = list(fs.traits_registry.keys())
        traits_detail = {
            k: {"archetype": v.archetype, "ancestry": v.ancestry, "traits": list(v.traits)}
            for k, v in fs.traits_registry.items()
        }
    except Exception:
        traits = []
        traits_detail = {}
    try:
        scenes = [
            {
                "scene_id": s.scene_id,
                "title": s.title,
                "status": s.status.value if hasattr(s.status, "value") else str(s.status),
                "objective": s.objective,
                "location": getattr(s, "location", ""),
                "threat": getattr(s, "threat", ""),
                "beats": list(getattr(s, "beats", [])),
                "cast": list(getattr(s, "cast", [])),
                "clocks": [
                    {"name": c.name, "ticks": c.ticks, "segments": c.segments, "kind": c.kind}
                    for c in getattr(s, "clocks", [])
                    if hasattr(c, "name")
                ],
            }
            for s in fs.scenes
        ]
    except Exception:
        scenes = []
    try:
        active = fs.active_scene_id
    except Exception:
        active = None
    try:
        eff_count = len(fs.effects)
    except Exception:
        eff_count = 0
    # campaign/mechanics — best-effort (may be empty before any encounter)
    try:
        players = {
            k: {"hp": v.hp, "max_hp": v.max_hp, "alive": v.alive, "pos": list(v.pos)}
            for k, v in fs.campaign.inner.players.items()
        }
        monsters = {
            k: {"hp": v.hp, "max_hp": v.max_hp, "alive": v.alive, "pos": list(v.pos)}
            for k, v in fs.campaign.inner.monsters.items()
        }
        round_v = int(fs.campaign.inner.round)
        turn = fs.campaign.inner.current_actor()
        transcript_tail = list(fs.campaign.inner.transcript[-6:])
    except Exception:
        players = {}
        monsters = {}
        round_v = 1
        turn = None
        transcript_tail = []
    try:
        stress = dict(fs._stress)
    except Exception:
        stress = {}
    return {
        "clocks": clocks,
        "traits": traits,
        "traits_detail": traits_detail,
        "scenes": scenes,
        "active_scene_id": active,
        "effects_count": eff_count,
        "players": players,
        "monsters": monsters,
        "round": round_v,
        "turn": turn,
        "stress": stress,
        "transcript_tail": transcript_tail,
    }


def collect_bundle(bundle_root: str | _pl.Path) -> dict[str, Any]:
    """Read bundle directory (events.jsonl + manifest + snapshots) into memory."""
    root = _pl.Path(bundle_root)
    # allow passing directly to events.jsonl
    if root.is_file() and root.name.endswith(".jsonl"):
        events_path = root
        root = root.parent
    else:
        events_path = root / "events.jsonl"
        if not events_path.exists():
            # try bundle_root itself is events path parent?
            alt = _pl.Path(bundle_root)
            if alt.is_file():
                events_path = alt
                root = alt.parent
    events: list[dict[str, Any]] = []
    if events_path.exists():
        from .events import iter_events as _iter

        events = list(_iter(events_path))
    # manifest
    manifest: dict[str, Any] | None = None
    mpath = root / "manifest.json"
    if mpath.exists():
        try:
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
        except Exception:
            manifest = None
    # snapshots list (just names)
    snaps: list[str] = []
    sdir = root / "snapshots"
    if sdir.exists():
        snaps = sorted(p.name for p in sdir.glob("*.json"))
    # seed heuristic
    seed = 0
    if events:
        try:
            seed = int(events[0].get("fused", {}).get("seed", 0))
        except Exception:
            seed = 0
    if manifest and "head_seq" in manifest:
        # prefer events[0] seed, else manifest doesn't carry seed
        pass
    return {
        "bundle_root": str(root),
        "events_path": str(events_path) if events_path else None,
        "events": events,
        "manifest": manifest,
        "snapshots": snaps,
        "seed": seed,
        "generated_at": _iso_now(),
    }


def build_timeline(bundle_root: str | _pl.Path, events: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Compute per-seq derived state by replaying events through FusedState."""
    from .state import FusedState

    data = collect_bundle(bundle_root) if events is None else {"events": events, "seed": 0}
    evts = events if events is not None else data["events"]
    seed = data.get("seed", 0) if events is None else 0
    if evts and events is None:
        try:
            seed = int(evts[0].get("fused", {}).get("seed", 0))
        except Exception:
            seed = int(data.get("seed", 0))
    fs = FusedState(seed_val=seed)
    # initial state before any event
    states: list[dict[str, Any]] = [_capture_state(fs)]
    for evt in evts:
        ce_type = evt.get("type", "")
        if ce_type == "fused.snapshot.taken":
            # snapshot is meta, does not mutate derived state
            states.append(_capture_state(fs))
            continue
        try:
            fs._apply_event(evt)
        except Exception:
            # still capture what we have — don't break site build
            pass
        states.append(_capture_state(fs))
    return states


def _render_html(bundle: dict[str, Any], timeline: list[dict[str, Any]], title: str | None = None) -> str:
    events: list[dict[str, Any]] = bundle.get("events", [])
    manifest = bundle.get("manifest")
    seed = bundle.get("seed", 0)
    # aggregates for overview
    by_type: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    by_scene: dict[str, int] = {}
    for e in events:
        by_type[e.get("type", "")] = by_type.get(e.get("type", ""), 0) + 1
        kind = e.get("fused", {}).get("kind", "") or "?"
        by_kind[kind] = by_kind.get(kind, 0) + 1
        sid = e.get("fused", {}).get("scene_id", "") or "?"
        by_scene[sid] = by_scene.get(sid, 0) + 1
    # scenes/traits from final state
    final_state = timeline[-1] if timeline else {"scenes": [], "traits": []}
    scenes_final = final_state.get("scenes", [])
    traits_final = final_state.get("traits", [])
    # embed data as JSON inside script tags (file:// friendly, no fetch)
    # keep payloads small: events + timeline states
    bundle_meta = {
        "title": title or f"Fused Campaign — {seed}",
        "bundle_root": bundle.get("bundle_root"),
        "seed": seed,
        "events_count": len(events),
        "snapshots": bundle.get("snapshots", []),
        "manifest": manifest,
        "generated_at": bundle.get("generated_at"),
    }
    # JSON-encode for embedding — escape </script> to avoid breaking HTML
    events_json = json.dumps(events, separators=(",", ":"), default=str).replace("</", "<\\/")
    timeline_json = json.dumps(timeline, separators=(",", ":"), default=str).replace("</", "<\\/")
    meta_json = json.dumps(bundle_meta, separators=(",", ":"), default=str).replace("</", "<\\/")

    # Pre-render static tables for initial load (before JS)
    def _table_by(d: dict[str, int]) -> str:
        rows = "".join(f"<tr><td><code>{k}</code></td><td>{v}</td></tr>" for k, v in sorted(d.items()))
        return rows or '<tr><td colspan="2" class="muted">—</td></tr>'

    title_h = title or "Fused Campaign — Knowledge Viewer"
    subtitle = f"seed {seed} · {len(events)} events · {len(scenes_final)} scenes · {len(traits_final)} traits · generated {bundle.get('generated_at', '')[:10]}"
    type_rows = _table_by(by_type)
    kind_rows = _table_by(by_kind)
    scene_rows = _table_by(by_scene)

    # Build scenes cards static (final state) for non-JS fallback — clickable to filter timeline to that scenario
    scenes_cards = ""
    for s in scenes_final[:12]:
        sid = s.get("scene_id", "")
        beats = "".join(f"<li>{b}</li>" for b in s.get("beats", [])[:6])
        scene_href = f"#scene-{sid}"
        scenes_cards += f'<div class="card clickable" onclick="window.__fused_filter_scene && window.__fused_filter_scene(\'{sid}\')" title="Click to filter timeline to this scenario" role="button" tabindex="0" onkeydown="if(event.key===\'Enter\') window.__fused_filter_scene(\'{sid}\')"><div class="k">{sid} <span class="pill" style="float:right">→ View scenario</span></div><div style="font-weight:700">{s.get("title")}<a href="{scene_href}" onclick="event.stopPropagation()" class="small muted" style="margin-left:8px;text-decoration:none">#</a></div><div class="small muted">{s.get("objective")}</div><div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap"><span class="pill">{s.get("location", "")}</span><span class="pill">{s.get("threat", "")}</span><span class="pill">{s.get("status", "")}</span></div><details><summary>beats {len(s.get("beats", []))}</summary><ol class="small">{beats}</ol></details></div>'
    if not scenes_cards:
        scenes_cards = '<div class="empty">No scenes yet — bundle empty or seed 0.</div>'
    # scene filter options for timeline
    scene_filter_options = "".join(
        f'<option value="{s.get("scene_id")}">{s.get("scene_id")} — {s.get("title", "")[:32]}</option>'
        for s in scenes_final
    )
    # per-scene detail sections (click-through target)
    scene_details_html = ""
    for s in scenes_final:
        sid = s.get("scene_id", "")
        scene_details_html += f'<section id="scene-{sid}" class="scene-detail" style="margin-top:10px"><div class="k">Scenario detail</div><div style="font-weight:700">{s.get("title")} <span class="pill">{sid}</span></div><div class="small muted">{s.get("objective")}</div><div class="small"><b>Cast:</b> {", ".join(s.get("cast", [])) or "<span class=muted>—</span>"} · <b>Threat:</b> {s.get("threat", "")} · <b>Status:</b> {s.get("status", "")}</div><div style="margin-top:6px"><a href="#timeline" onclick="window.__fused_filter_scene(\'{sid}\'); return false;" class="pill" style="text-decoration:none">▶ Filter timeline to this scenario</a> <a href="#scenes" class="pill" style="text-decoration:none">↑ Back to scenes</a></div></section>'

    # Traits table fallback
    traits_rows = ""
    final_traits_detail = final_state.get("traits_detail", {})
    for name in traits_final[:20]:
        td = final_traits_detail.get(name, {})
        traits_rows += f'<tr><td><strong>{name}</strong> <span class="muted">({td.get("ancestry", "")})</span></td><td>{td.get("archetype", "")}</td><td>{", ".join(td.get("traits", []))}</td></tr>'
    if not traits_rows:
        traits_rows = '<tr><td colspan="3" class="muted">— no traits registered —</td></tr>'

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_h}</title>
<meta name="description" content="Fused campaign static knowledge site — rewind/playthrough of JSONL events + state">
<style>
  :root{{--bg:#fcfcfa;--fg:#171717;--accent:#1d4ed8;--accent2:#7c3aed;--muted:#6b7280;--border:#e5e7eb;--code-bg:#f3f4f6;--max:1140px;--radius:12px;--ok:#16a34a;--warn:#d97706}}
  *{{box-sizing:border-box}} html{{scroll-behavior:smooth}}
  body{{margin:0;font:14px/1.6 ui-sans,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;background:var(--bg);color:var(--fg)}}
  header{{border-bottom:3px solid var(--accent);background:linear-gradient(180deg,#fff,#f0f7ff)}}
  .wrap{{max-width:var(--max);margin:0 auto;padding:0 18px}}
  header .wrap{{padding:24px 18px 14px}}
  h1{{margin:0 0 4px;font-size:1.55rem;letter-spacing:-.02em;color:var(--accent)}}
  .subtitle{{margin:0;color:var(--muted);font-size:.9rem}}
  .chips{{margin-top:10px;display:flex;gap:8px;flex-wrap:wrap}}
  .chip{{padding:3px 9px;border-radius:999px;background:#fff;border:1px solid var(--border);font-size:.75rem;color:var(--muted)}}
  .chip.accent{{background:var(--accent);color:#fff;border-color:var(--accent)}}
  nav.toc{{position:sticky;top:0;z-index:11;background:rgba(252,252,250,.94);backdrop-filter:blur(6px);border-bottom:1px solid var(--border)}}
  nav.toc .wrap{{display:flex;gap:10px;overflow:auto;white-space:nowrap;padding:8px 18px}}
  nav.toc a{{color:var(--muted);text-decoration:none;font-size:.84rem;padding:5px 10px;border-radius:999px}}
  nav.toc a:hover{{background:var(--code-bg);color:var(--accent)}}
  main .wrap{{padding:16px 18px 50px}}
  section{{margin:18px 0 22px;padding:18px;background:#fff;border:1px solid var(--border);border-radius:var(--radius);box-shadow:0 1px 2px rgba(0,0,0,.04)}}
  h2{{margin:0 0 8px;font-size:1.15rem;color:var(--accent);border-bottom:2px solid var(--border);padding-bottom:6px;display:flex;gap:8px;align-items:center}}
  h2 .count{{font-size:.75rem;background:var(--code-bg);border:1px solid var(--border);padding:2px 7px;border-radius:999px;color:var(--muted);font-weight:600}}
  h3{{margin:14px 0 6px;font-size:.98rem;color:#222}}
  p{{margin:6px 0}}
  .grid4{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:10px 0}}
  .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
  @media(max-width:900px){{.grid4{{grid-template-columns:1fr 1fr}}.grid2{{grid-template-columns:1fr}}}}
  @media(max-width:520px){{.grid4{{grid-template-columns:1fr}}}}
  .card{{border:1px solid var(--border);border-radius:10px;padding:10px 12px;background:#fff}}
  .card.clickable{{cursor:pointer;transition:box-shadow .15s,transform .15s,border-color .15s}} .card.clickable:hover{{box-shadow:0 4px 12px rgba(29,78,216,.15);transform:translateY(-1px);border-color:var(--accent)}} .card.clickable:focus{{outline:2px solid var(--accent);outline-offset:2px}}  .card .k{{font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:700}}
  .card .v{{font-size:1.35rem;font-weight:800;color:var(--accent)}}
  .card .sub{{font-size:.78rem;color:var(--muted)}}
  table{{width:100%;border-collapse:collapse;margin:8px 0 10px;font-size:.84rem}}
  th{{ text-align:left;background:#f9fafb;border-bottom:2px solid var(--border);padding:6px 7px;font-weight:700;font-size:.78rem;letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}}
  td{{padding:6px 7px;border-bottom:1px solid var(--border);vertical-align:top}}
  tr:last-child td{{border-bottom:none}}
  code,pre{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}
  pre{{background:var(--code-bg);border:1px solid var(--border);padding:10px;border-radius:8px;overflow:auto;font-size:.8rem;line-height:1.45}}
  code{{background:var(--code-bg);padding:1px 4px;border-radius:4px;font-size:.86em}}
  pre code{{background:none;padding:0}}
  .pill{{display:inline-block;padding:2px 7px;border-radius:999px;background:var(--code-bg);border:1px solid var(--border);font-size:.72rem;color:var(--muted)}}
  .pill.say_yes{{background:#dcfce7;border-color:#86efac;color:#166534}}
  .pill.rolled{{background:#dbeafe;border-color:#93c5fd;color:#1e40af}}
  .pill.odd{{background:#ffe4e6;border-color:#fda4af;color:#9f1239}}
  .pill.obvious{{background:#fef9c3;border-color:#fde047;color:#854d0e}}
  .pill.chosen{{background:var(--accent);color:#fff;border-color:var(--accent);font-weight:700}}
  .choice-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:8px 0}}
  @media(max-width:900px){{.choice-grid{{grid-template-columns:1fr}}}}
  .choice-card{{border:1px solid var(--border);border-radius:8px;padding:8px 9px;background:#fff;font-size:.82rem}}
  .choice-card.chosen{{border-color:var(--accent);background:#eff6ff;box-shadow:0 0 0 1px var(--accent);}}
  .choice-card .label{{font-size:.70rem;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);font-weight:700}}
  .choice-card.chosen .label{{color:var(--accent)}}
  .choice-meta{{font-size:.76rem;color:var(--muted);margin-top:4px;display:flex;gap:6px;flex-wrap:wrap}}
  .controls{{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 10px}}
  .controls select,.controls input{{padding:6px 8px;border:1px solid var(--border);border-radius:8px;background:#fff;font-size:.84rem}}
  .controls button{{padding:6px 10px;border:1px solid var(--border);border-radius:8px;background:var(--accent);color:#fff;font-weight:600;cursor:pointer}}
  .controls button.ghost{{background:#fff;color:var(--accent)}}
  .controls button:disabled{{opacity:.5;cursor:not-allowed}}
  .muted{{color:var(--muted)}} .small{{font-size:.82rem}}
  /* Player */
  .playbar{{position:sticky;top:42px;z-index:10;background:rgba(255,255,255,.96);backdrop-filter:blur(8px);border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:10px;padding:10px 12px;margin:12px 0;display:flex;gap:10px;align-items:center;flex-wrap:wrap;box-shadow:0 1px 6px rgba(0,0,0,.06)}}
  .playbar .seq{{font-weight:800;color:var(--accent);min-width:96px}}
  .playbar input[type=range]{{flex:1;min-width:180px;accent-color:var(--accent)}}
  .playbar .time{{font-family:ui-monospace,monospace;font-size:.78rem;color:var(--muted);min-width:120px;text-align:right}}
  .playbar button{{padding:6px 9px;font-size:.82rem}}
  .playbar button.active{{background:var(--accent2);border-color:var(--accent2)}}
  .player-meta{{display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
  .player-meta select{{padding:5px 7px;font-size:.82rem}}
  /* Timeline */
  .timeline{{border-left:2px solid var(--border);margin-left:8px;padding-left:0}}
  .tl-item{{position:relative;padding:8px 0 8px 16px;border-bottom:1px dashed var(--border);opacity:.96;transition:background .15s,opacity .15s}}
  .tl-item::before{{content:"";position:absolute;left:-6px;top:14px;width:10px;height:10px;border-radius:50%;background:var(--accent);border:2px solid #fff;box-shadow:0 0 0 1px var(--border)}}
  .tl-item.choice::before{{background:var(--accent2)}}
  .tl-item.future{{opacity:.42}}
  .tl-item.current{{background:#eff6ff;border-radius:8px;border:1px solid #bfdbfe;margin:4px 0;padding-left:15px}}
  .tl-item.current::before{{background:var(--accent2);width:12px;height:12px;left:-7px;top:13px}}
  .tl-meta{{font-size:.76rem;color:var(--muted);display:flex;gap:8px;flex-wrap:wrap}}
  .hl{{font-weight:700}}
  details{{border:1px solid var(--border);border-radius:8px;padding:8px 10px;background:#fcfcff;margin:8px 0}}
  details summary{{cursor:pointer;font-weight:600;color:var(--accent);font-size:.86rem}}
  .json{{white-space:pre-wrap;word-break:break-all}}
  footer{{border-top:1px solid var(--border);color:var(--muted);font-size:.78rem;padding:14px 0}}
  .empty{{padding:18px;text-align:center;color:var(--muted);background:var(--code-bg);border:1px dashed var(--border);border-radius:8px}}
  /* State panel */
  .state-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
  @media(max-width:860px){{.state-grid{{grid-template-columns:1fr}}}}
  .kv{{display:grid;grid-template-columns:94px 1fr;gap:6px;font-size:.84rem;padding:4px 0;border-bottom:1px dashed var(--border)}}
  .kv:last-child{{border-bottom:none}}
  .kv b{{color:var(--muted);font-weight:700;font-size:.78rem;letter-spacing:.03em;text-transform:uppercase}}
  .clock-bar{{height:10px;border-radius:999px;background:var(--code-bg);border:1px solid var(--border);overflow:hidden;flex:1}}
  .clock-fill{{height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2));border-radius:999px;transition:width .3s}}
  .hl-row{{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:8px 10px;margin:8px 0}}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="pill" style="margin-bottom:6px">Fused Knowledge · Static Site · Rewind/Playthrough</div>
    <h1>{title_h}</h1>
    <p class="subtitle">{subtitle}</p>
    <div class="chips">
      <span class="chip accent">seed {seed}</span>
      <span class="chip">{len(events)} events</span>
      <span class="chip">{len(scenes_final)} scenes</span>
      <span class="chip">{len(traits_final)} traits</span>
      <span class="chip">{len(bundle.get("snapshots", []))} snapshots</span>
      <span class="chip" id="chip-seq">seq 0 / {len(events)}</span>
      <span class="chip" id="chip-state-clocks">0 clocks</span>
    </div>
  </div>
</header>
<nav class="toc" aria-label="Table of contents">
  <div class="wrap">
    <a href="#overview">Overview</a>
    <a href="#player">Player</a>
    <a href="#state">State @ seq</a>
    <a href="#scenes">Scenes</a>
    <a href="#traits">Traits</a>
    <a href="#timeline">Timeline</a>
    <a href="#raw">Raw</a>
  </div>
</nav>
<main><div class="wrap">

  <section id="player" aria-label="Rewind and playthrough controls">
    <h2>Rewind / Playthrough <span class="count" id="count-player">{len(events)} events · seq 0→{len(events)}</span></h2>
    <div class="playbar" role="group" aria-label="Playback controls">
      <button id="btn-start" title="Jump to start (seq 0)" aria-label="Start">⏮</button>
      <button id="btn-prev" title="Previous event (←)" aria-label="Previous">◀</button>
      <button id="btn-play" title="Play/Pause (Space)" aria-label="Play">▶</button>
      <button id="btn-next" title="Next event (→)" aria-label="Next">▶▶</button>
      <button id="btn-end" title="Jump to end" aria-label="End">⏭</button>
      <input id="scrub" type="range" min="0" max="{len(events)}" value="0" step="1" aria-label="Scrub events">
      <span class="seq" id="seq-label">seq 0 / {len(events)}</span>
      <div class="player-meta">
        <label class="small muted">speed <select id="speed"><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option></select></label>
        <label class="small muted"><input type="checkbox" id="autoplay-wrap"> loop</label>
        <span class="time" id="time-label">—</span>
      </div>
    </div>
    <p class="small muted">File:// friendly — all events embedded. Use slider, buttons, or <code>←/→</code> / <code>Space</code>. Deep-link <code>#seq=10</code>. Future events dim; current event highlighted.</p>
    <div class="hl-row small" id="current-event-summary"><span class="muted">Current event:</span> <span id="current-event-text">— start (before any event) —</span></div>
    <div class="controls" style="margin-top:6px">
      <button onclick="document.getElementById('scrub').value=0; window.__fused_set_seq(0)" class="ghost small">Show start state</button>
      <button onclick="navigator.clipboard&&navigator.clipboard.writeText(location.href); alert('Link copied: '+location.href)" class="ghost small">Copy link (#seq)</button>
    </div>
  </section>

  <section id="overview">
    <h2>Overview <span class="count">{len(events)} events</span></h2>
    <div class="grid4">
      <div class="card"><div class="k">Events</div><div class="v">{len(events)}</div><div class="sub">append-only JSONL, CloudEvents 1.0</div></div>
      <div class="card"><div class="k">Scenes</div><div class="v">{len(scenes_final)}</div><div class="sub">narrative structure</div></div>
      <div class="card"><div class="k">Traits</div><div class="v">{len(traits_final)}</div><div class="sub">separate store</div></div>
      <div class="card"><div class="k">Snapshots</div><div class="v">{len(bundle.get("snapshots", []))}</div><div class="sub">+ manifest replay</div></div>
    </div>
    <div class="grid2">
      <div>
        <h3>By type</h3>
        <table><thead><tr><th>Type</th><th>Count</th></tr></thead><tbody>{type_rows}</tbody></table>
      </div>
      <div>
        <h3>By kind</h3>
        <table><thead><tr><th>Kind</th><th>Count</th></tr></thead><tbody>{kind_rows}</tbody></table>
      </div>
    </div>
    <div class="grid2">
      <div>
        <h3>By scene</h3>
        <table><thead><tr><th>Scene</th><th>Count</th></tr></thead><tbody>{scene_rows}</tbody></table>
      </div>
      <div>
        <h3>Bundle</h3>
        <div class="small muted">root <code>{bundle.get("bundle_root", "")}</code> · manifest <code>{"✓ present" if manifest else "—"}</code></div>
        <pre class="small json">{json.dumps(bundle_meta, indent=2)}</pre>
      </div>
    </div>
    <p class="small muted">Derived states precomputed at build time via <code>FusedState._apply_event</code> replay — no JS reimplementation. Timeline length {len(timeline)} (0 = before first event).</p>
  </section>

  <section id="state">
    <h2>State @ seq <span class="count" id="count-state">seq 0</span> <span class="pill" id="pill-active-scene">—</span></h2>
    <div class="state-grid">
      <div>
        <h3>Clocks</h3>
        <div id="state-clocks"><div class="empty small">Clocks render after JS loads — or at seq 0 no clocks yet.</div></div>
        <h3>Active scene</h3>
        <div id="state-scene" class="card small"><div class="muted">—</div></div>
        <h3>Stress</h3>
        <div id="state-stress" class="small muted">—</div>
      </div>
      <div>
        <h3>Characters</h3>
        <div id="state-chars"><div class="empty small">Players/monsters at current seq (from latest snapshot + replay).</div></div>
        <h3>Transcript tail</h3>
        <pre id="state-transcript" class="small" style="max-height:160px;overflow:auto">—</pre>
        <h3>Diff vs prev</h3>
        <pre id="state-diff" class="small json" style="max-height:220px;overflow:auto">—</pre>
      </div>
    </div>
    <details><summary>Raw state @ seq (json)</summary><pre id="state-raw" class="small json">—</pre></details>
  </section>

   <section id="scenes">
     <h2>Scenes <span class="count">{len(scenes_final)}</span></h2>
     <p class="small muted">Click any scenario card to <strong>filter the timeline</strong> to that scenario (or use the scenario filter in Timeline). Each card links to a detail anchor.</p>
     <div class="grid2" id="scenes-grid">{scenes_cards}</div>
     {scene_details_html}
   </section>

  <section id="traits">
    <h2>Traits <span class="count">{len(traits_final)}</span></h2>
    <table><thead><tr><th>Name</th><th>Archetype</th><th>Traits</th></tr></thead><tbody id="traits-body">{traits_rows}</tbody></table>
  </section>

  <section id="timeline">
    <h2>Timeline <span class="count" id="count-timeline">{len(events)}</span></h2>
     <div class="controls">
       <select id="filter-type"><option value="">All types</option>{"".join(f'<option value="{k}">{k}</option>' for k in sorted(by_type.keys()) if k)}</select>
       <select id="filter-kind"><option value="">All kinds</option>{"".join(f'<option value="{k}">{k}</option>' for k in sorted(by_kind.keys()) if k)}</select>
       <select id="filter-scene"><option value="">All scenarios</option>{scene_filter_options}</select>
       <input id="filter-text" placeholder="filter text (actor, summary, scene)">
       <button onclick="clearFilters()" class="ghost">Clear</button>
       <span class="small muted" id="filter-count"></span>
     </div>
    <div class="timeline" id="timeline-list">
      <div class="empty">Timeline will be rendered by JS from embedded events.</div>
    </div>
  </section>

  <section id="raw">
    <h2>Raw bundles</h2>
    <p class="small muted">Machine-readable copies are written alongside <code>index.html</code> for <code>jq</code>/<code>duckdb</code> use. Embedded JSON below is file://-safe (no extra fetch).</p>
    <details><summary>Embedded bundle meta</summary><pre class="small json" id="meta-pre">{json.dumps(bundle_meta, indent=2)}</pre></details>
    <details><summary>How to query (no LLM)</summary><pre class="small">jq -c 'select(.type=="fused.effect.recorded")' knowledge/fused-demo/events.jsonl
sqlite3 knowledge/fused-demo/projections/campaign.db "SELECT subject, kind, summary FROM events ORDER BY seq DESC LIMIT 5"
# State at seq 10 via static site or CLI:
#   open site/index.html#seq=10
#   uv run fused replay --log knowledge/fused-demo/events.jsonl --at-seq 10
</pre></details>
  </section>

  <footer>
    <div>Built via <code>fused build-site</code> · deterministic replay · file:// friendly · <span id="footer-seq"></span></div>
  </footer>

</div></main>

<script id="__FUSED_META__" type="application/json">{meta_json}</script>
<script id="__FUSED_EVENTS__" type="application/json">{events_json}</script>
<script id="__FUSED_TIMELINE__" type="application/json">{timeline_json}</script>
<script>
// --- Fused static site rewind/playthrough — no deps, file:// safe ---
(function(){{
  const events = JSON.parse(document.getElementById('__FUSED_EVENTS__').textContent || '[]');
  const timeline = JSON.parse(document.getElementById('__FUSED_TIMELINE__').textContent || '[]');
  const meta = JSON.parse(document.getElementById('__FUSED_META__').textContent || '{{}}');
  const N = events.length;
  let seq = 0; // 0..N, 0 = before any event
  let playing = false;
  let timer = null;

  const $ = (id) => document.getElementById(id);
  const scrub = $('scrub');
  const seqLabel = $('seq-label');
  const chipSeq = $('chip-seq');
  const chipClocks = $('chip-state-clocks');
  const timeLabel = $('time-label');
  const btnPlay = $('btn-play');
  const countPlayer = $('count-player');
  const countState = $('count-state');
  const countTimeline = $('count-timeline');
  const currentText = $('current-event-text');
  const filterType = $('filter-type');
  const filterKind = $('filter-kind');
  const filterScene = $('filter-scene');
  const filterText = $('filter-text');
  const speedSel = $('speed');
  const loopCb = $('autoplay-wrap');

  // click-through from Scenes → filter timeline to that scenario
  window.__fused_filter_scene = function(sid){{
    if(filterScene){{ filterScene.value = sid; }}
    renderTimeline();
    const tl = document.getElementById('timeline');
    if(tl) tl.scrollIntoView({{behavior:'smooth', block:'start'}});
    try{{ history.replaceState(null,'','#seq='+seq+'&scene='+encodeURIComponent(sid)); }}catch(e){{ location.hash='#seq='+seq+'&scene='+sid; }}
  }};
  window.__fused_clear_scene = function(){{ if(filterScene) filterScene.value=''; renderTimeline(); try{{ history.replaceState(null,'','#seq='+seq); }}catch(e){{}} }};

  function clampSeq(v){{ const n = parseInt(v,10); if(isNaN(n)) return 0; return Math.max(0, Math.min(N, n)); }}

  function fmtTime(iso){{ try{{ return iso ? iso.slice(11,19)+'Z' : '—'; }}catch(e){{ return '—'; }} }}

  function stateAt(s){{ return timeline[s] || timeline[0] || {{scenes:[],traits:[],clocks:{{}}}}; }}

  function renderState(s){{
    const st = stateAt(s);
    // clocks
    const clocksEl = $('state-clocks');
    const clocks = st.clocks || {{}};
    const names = Object.keys(clocks);
    chipClocks.textContent = names.length ? names.length+' clocks' : '0 clocks';
    if(!names.length) clocksEl.innerHTML = '<div class="muted small">No clocks at this seq.</div>';
    else {{
      clocksEl.innerHTML = names.map(function(k){{
        const c = clocks[k];
        const pct = c.segments ? Math.round(100*c.ticks/c.segments) : 0;
        return '<div class="kv"><b>'+k+'</b><div><div style="display:flex;gap:8px;align-items:center"><div class="clock-bar"><div class="clock-fill" style="width:'+pct+'%"></div></div><span class="pill">'+c.ticks+'/'+c.segments+' '+c.kind+(c.completed?' ✓':'')+'</span></div></div></div>';
      }}).join('');
    }}
    // active scene
    const active = st.active_scene_id || '(none)';
    $('pill-active-scene').textContent = active;
    const sc = (st.scenes||[]).find(function(x){{ return x.scene_id===st.active_scene_id; }}) || (st.scenes||[])[0];
    const sceneEl = $('state-scene');
    if(sc) sceneEl.innerHTML = '<div class="k">'+sc.scene_id+'</div><div style="font-weight:700">'+(sc.title||sc.scene_id)+'</div><div class="small muted">'+(sc.objective||'')+'</div><div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap"><span class="pill">'+(sc.location||'')+'</span><span class="pill">'+(sc.threat||'')+'</span><span class="pill">'+(sc.status||'')+'</span></div>'+ (sc.beats&&sc.beats.length? '<div class="small" style="margin-top:6px"><b>beats:</b> '+(sc.beats.join(' → '))+'</div>':'');
    else sceneEl.innerHTML = '<div class="muted small">No scene at this seq.</div>';
    // stress
    const stress = st.stress || {{}};
    const sKeys = Object.keys(stress);
    $('state-stress').textContent = sKeys.length ? sKeys.map(function(k){{ return k+': '+stress[k]; }}).join(' · ') : '—';
    // chars
    const players = st.players || {{}};
    const monsters = st.monsters || {{}};
    const pNames = Object.keys(players);
    const mNames = Object.keys(monsters);
    let charsHtml = '';
    if(pNames.length) charsHtml += '<div class="small k" style="margin-top:4px">Players</div><table><thead><tr><th>Name</th><th>HP</th><th>Pos</th></tr></thead><tbody>'+ pNames.map(function(n){{ const p=players[n]; return '<tr><td>'+n+'</td><td>'+p.hp+'/'+p.max_hp+(p.alive?'':' dead')+'</td><td class="muted">'+(p.pos||[]).slice(0,3).join(',')+'</td></tr>'; }}).join('') +'</tbody></table>';
    if(mNames.length) charsHtml += '<div class="small k" style="margin-top:6px">Threats</div><table><thead><tr><th>Name</th><th>HP</th><th>Pos</th></tr></thead><tbody>'+ mNames.map(function(n){{ const p=monsters[n]; return '<tr><td>'+n+'</td><td>'+p.hp+'/'+p.max_hp+(p.alive?'':' dead')+'</td><td class="muted">'+(p.pos||[]).slice(0,3).join(',')+'</td></tr>'; }}).join('') +'</tbody></table>';
    if(!charsHtml) charsHtml = '<div class="muted small">No combatants at this seq (before encounter setup).</div>';
    charsHtml += '<div class="small muted" style="margin-top:6px">round '+ (st.round||1) + (st.turn? ' · turn '+st.turn:'') + ' · effects '+ (st.effects_count||0) +'</div>';
    $('state-chars').innerHTML = charsHtml;
    // transcript
    const tail = st.transcript_tail || [];
    $('state-transcript').textContent = tail.length ? tail.join("\\n") : '(no transcript at this seq)';
    // raw
    $('state-raw').textContent = JSON.stringify(st, null, 2);
    // diff vs prev (simple: which clocks changed, which scene added, traits added)
    const prev = s>0 ? stateAt(s-1) : null;
    let diff = '';
    if(!prev) diff = 'Initial state (before any event).';
    else {{
      const lines = [];
      // clocks diff
      const allClocks = new Set([].concat(Object.keys(prev.clocks||{{}}), Object.keys(st.clocks||{{}})));
      allClocks.forEach(function(k){{
        const a = (prev.clocks||{{}})[k]; const b=(st.clocks||{{}})[k];
        if(!a && b) lines.push('+ clock '+k+': '+b.ticks+'/'+b.segments);
        else if(a && b && a.ticks!==b.ticks) lines.push('~ clock '+k+': '+a.ticks+'→'+b.ticks+'/'+b.segments+(b.completed?' completed':''));
      }});
      if((st.scenes||[]).length !== (prev.scenes||[]).length) lines.push('+ scenes '+(prev.scenes||[]).length+'→'+(st.scenes||[]).length);
      if((st.traits||[]).length !== (prev.traits||[]).length) lines.push('+ traits '+(prev.traits||[]).length+'→'+(st.traits||[]).length + ': ' + (st.traits||[]).filter(function(x){{ return !(prev.traits||[]).includes(x); }}).join(', '));
      if((st.effects_count||0) !== (prev.effects_count||0)) lines.push('effects '+(prev.effects_count||0)+'→'+(st.effects_count||0));
      diff = lines.length ? lines.join("\\n") : '(no clock/trait/scene change — check event payload)';
      if(s>0 && events[s-1]) {{
        const ev = events[s-1];
        diff = 'Event '+ (s-1) + ' ('+ ev.type + ' · '+ (ev.fused&&ev.fused.kind||'') + ') — '+ ((ev.data&&ev.data.summary)||'') + "\\n---\\n" + diff;
      }}
    }}
    $('state-diff').textContent = diff;
  }}

  function escHtml(s){{ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }}

  function choiceBlock(evt){{
    const payload = (evt.data && evt.data.payload) || {{}};
    const choice = payload.choice || {{}};
    const prop = payload.proposal || {{}};
    const obvious = choice.obvious || prop.obvious || payload.obvious || '';
    const option = choice.option || prop.option || payload.option || '';
    const odd = choice.odd || prop.odd || payload.odd || '';
    const situation = choice.situation || payload.situation || '';
    const position = choice.position || payload.position || '';
    const effect = choice.effect || payload.effect || '';
    const category = choice.category != null ? choice.category : (payload.category != null ? payload.category : null);
    const roll = choice.roll != null ? choice.roll : (payload.roll != null ? payload.roll : null);
    const rolls = choice.rolls && choice.rolls.length ? choice.rolls : (payload.rolls || []);
    const choiceText = choice.choice_text || payload.choice_text || '';
    const via = choice.resolved_via || payload.resolved_via || '';
    const ticks = choice.ticks != null ? choice.ticks : (payload.ticks != null ? payload.ticks : null);
    const trivial = choice.trivial || payload.trivial;
    const isResolved = evt.type === 'fused.choice.resolved' || category != null || roll != null;
    if(!obvious && !option && !odd && !situation) return '';
    let html = '';
    if(situation) html += '<div class="small" style="margin-top:6px"><b>Situation:</b> '+escHtml(situation)+'</div>';
    else if(evt.data && evt.data.summary && evt.type.indexOf('choice')!==-1) html += '<div class="small" style="margin-top:6px"><b>Situation:</b> '+escHtml(evt.data.summary.slice(0,260))+'</div>';
    html += '<div class="choice-grid">';
    [['obvious', obvious], ['option', option], ['odd', odd]].forEach(function(pair){{
      const cat = pair[0]; const txt = pair[1];
      if(!txt) return;
      const isChosen = isResolved && category === cat;
      const cls = 'choice-card'+(isChosen ? ' chosen' : '');
      html += '<div class="'+cls+'"><div class="label">'+cat+(isChosen ? ' ✓ chosen' : '')+'</div><div>'+escHtml(txt)+'</div></div>';
    }});
    html += '</div>';
    const meta = [];
    if(position || effect) meta.push('<span class="pill">'+escHtml(position||'')+(effect ? '/'+escHtml(effect) : '')+'</span>');
    if(isResolved){{
      if(roll != null) meta.push('<span class="pill '+(via==='rolled' ? 'rolled' : '')+'">rolled '+escHtml(roll)+(rolls && rolls.length ? ' ['+rolls.join(',')+']' : '')+'</span>');
      if(via) meta.push('<span class="pill">'+escHtml(via)+'</span>');
      if(category) meta.push('<span class="pill '+escHtml(category)+'">'+escHtml(category)+'</span>');
      if(ticks != null) meta.push('<span class="pill">ticks '+escHtml(ticks)+'</span>');
    }} else {{
      meta.push('<span class="pill muted">awaiting roll → '+(via||'rolled')+'</span>');
    }}
    if(trivial) meta.push('<span class="pill say_yes">say yes / trivial</span>');
    if(meta.length) html += '<div class="choice-meta">'+meta.join(' ')+'</div>';
    if(isResolved && choiceText) html += '<div class="small" style="margin-top:6px"><b>Chosen:</b> <em>'+escHtml(choiceText)+'</em></div>';
    return html;
  }}

  function renderTimeline(){{
    const list = $('timeline-list');
    const ft = (filterType.value||'').trim();
    const fk = (filterKind.value||'').trim();
    const fs = (filterScene && filterScene.value||'').trim();
    const ftxt = (filterText.value||'').toLowerCase().trim();
    let visible = 0;
    const rows = events.map(function(evt, idx){{
      const type = evt.type||''; const kind = (evt.fused&&evt.fused.kind)||''; const subject = evt.subject||''; const scene = (evt.fused&&evt.fused.scene_id)||''; const summary = (evt.data&&evt.data.summary)||''; const time = evt.time||'';
      const hay = (type+' '+kind+' '+subject+' '+scene+' '+summary).toLowerCase();
      const okType = !ft || type===ft;
      const okKind = !fk || kind===fk;
      const okScene = !fs || scene===fs;
      const okTxt = !ftxt || hay.indexOf(ftxt)!==-1;
      const pass = okType && okKind && okScene && okTxt;
      if(!pass) return '';
      visible++;
      const isCurrent = idx+1===seq; // seq is count of applied events, so event idx current when seq==idx+1
      const isFuture = idx+1 > seq;
      const cls = 'tl-item'+(pass&&kind==='choice'?' choice':'')+(isCurrent?' current':'')+(isFuture?' future':'');
      const badge = type.replace('fused.','');
      const isChoice = kind==='choice' || type.indexOf('fused.choice')===0;
      const chHtml = isChoice ? choiceBlock(evt) : '';
      return '<div class="'+cls+'" data-type="'+type+'" data-kind="'+kind+'" data-subject="'+subject+'" data-scene="'+scene+'" data-idx="'+idx+'" onclick="window.__fused_set_seq('+(idx+1)+')" style="cursor:pointer" title="Jump to seq '+(idx+1)+'">'
        + '<div class="tl-meta"><span class="pill">'+badge+'</span><span class="pill">'+kind+'</span><span>seq '+(idx)+'→'+(idx+1)+'</span><span>'+scene+'</span><span>'+fmtTime(time)+'</span><span class="pill" style="margin-left:auto">#'+idx+'</span></div>'
        + '<div class="hl">'+subject+' — '+(summary.slice(0,140))+'</div>'
        + chHtml
        + '<div class="small muted">id <code>'+(evt.id||'')+'</code></div>'
        + '<details><summary>payload</summary><pre class="json">'+JSON.stringify(evt,null,2)+'</pre></details>'
        + '</div>';
    }}).join('');
    if(!visible && events.length) list.innerHTML = '<div class="empty">No events match filter (try Clear).</div>';
    else if(!events.length) list.innerHTML = '<div class="empty">No events in bundle — run <code>fused demo</code> to populate.</div>';
    else list.innerHTML = rows;
    $('filter-count').textContent = visible+' / '+events.length+' visible · seq '+seq+' · '+ (events[seq-1]? (events[seq-1].subject+' — '+((events[seq-1].data&&events[seq-1].data.summary)||'').slice(0,60) ) : 'start');
    // scroll current into view if playing
    if(playing) {{
      const cur = list.querySelector('.tl-item.current');
      if(cur) cur.scrollIntoView({{block:'nearest',behavior:'smooth'}});
    }}
  }}

  function setSeq(v, opts){{ 
    opts = opts || {{}};
    const n = clampSeq(v);
    if(n===seq && !opts.force) return;
    seq = n;
    scrub.value = String(seq);
    seqLabel.textContent = 'seq '+seq+' / '+N;
    if(chipSeq) chipSeq.textContent = 'seq '+seq+' / '+N;
    if(countPlayer) countPlayer.textContent = N+' events · seq '+seq+'→'+N;
    if(countState) countState.textContent = 'seq '+seq;
    if($('footer-seq')) $('footer-seq').textContent = 'seq '+seq+' / '+N+(playing?' · playing':'');
    // hash deep link — preserve scene filter if active
    if(!opts.noHash) {{
      try{{
        const scenePart = (filterScene && filterScene.value) ? '&scene='+encodeURIComponent(filterScene.value) : '';
        // keep existing scene hash if we are not changing seq via scene filter
        let hash = '#seq='+seq + scenePart;
        // if there was a scene hash without seq, preserve it
        const existing = location.hash||'';
        if(scenePart==='' && existing.indexOf('scene=')!==-1) {{
          const mm = existing.match(/scene=([^&]+)/);
          if(mm) hash = '#seq='+seq + '&scene='+mm[1];
        }}
        history.replaceState(null,'',hash);
      }}catch(e){{ location.hash='#seq='+seq; }}
    }}
    // current event summary
    if(seq===0) currentText.textContent = '— start (before any event) —';
    else {{
      const ev = events[seq-1];
      if(ev) currentText.textContent = '#'+(seq-1)+' '+ev.type+' · '+(ev.subject||'')+' — '+((ev.data&&ev.data.summary)||'');
      else currentText.textContent = 'seq '+seq;
      timeLabel.textContent = ev && ev.time ? fmtTime(ev.time) : '—';
    }}
    renderState(seq);
    renderTimeline();
  }}
  window.__fused_set_seq = setSeq;

  function step(d){{ setSeq(seq+d); }}
  function play(){{ if(playing) return; playing=true; btnPlay.textContent='⏸'; btnPlay.classList.add('active'); tick(); }}
  function pause(){{ playing=false; btnPlay.textContent='▶'; btnPlay.classList.remove('active'); if(timer) clearTimeout(timer); timer=null; renderTimeline(); }}
  function tick(){{
    if(!playing) return;
    const spd = parseFloat(speedSel.value||'1');
    const delay = Math.max(120, 900 / spd);
    timer = setTimeout(function(){{
      let nxt = seq+1;
      if(nxt > N) {{
        if(loopCb.checked) nxt = 0;
        else {{ pause(); return; }}
      }}
      setSeq(nxt);
      tick();
    }}, delay);
  }}

  // bind controls
  scrub.addEventListener('input', function(e){{ pause(); setSeq(e.target.value); }});
  scrub.addEventListener('change', function(e){{ setSeq(e.target.value); }});
  $('btn-start').addEventListener('click', function(){{ pause(); setSeq(0); }});
  $('btn-prev').addEventListener('click', function(){{ pause(); step(-1); }});
  $('btn-play').addEventListener('click', function(){{ if(playing) pause(); else play(); }});
  $('btn-next').addEventListener('click', function(){{ pause(); step(1); }});
  $('btn-end').addEventListener('click', function(){{ pause(); setSeq(N); }});
  speedSel.addEventListener('change', function(){{ if(playing){{ pause(); play(); }} }});
  filterType.addEventListener('change', renderTimeline);
  filterKind.addEventListener('change', renderTimeline);
  if(filterScene) filterScene.addEventListener('change', renderTimeline);
  filterText.addEventListener('input', renderTimeline);
  window.clearFilters = function(){{
    filterType.value=''; filterKind.value=''; filterText.value='';
    if(filterScene) filterScene.value='';
    // clear scene hash
    try{{ history.replaceState(null,'', location.pathname+location.search); }}catch(e){{ location.hash=''; }}
    renderTimeline();
  }};
  document.addEventListener('keydown', function(e){{
    if(e.target && (e.target.tagName==='INPUT' || e.target.tagName==='SELECT' || e.target.tagName==='TEXTAREA')) return;
    if(e.key===' '){{ e.preventDefault(); if(playing) pause(); else play(); }}
    else if(e.key==='ArrowRight'){{ e.preventDefault(); pause(); step(1); }}
    else if(e.key==='ArrowLeft'){{ e.preventDefault(); pause(); step(-1); }}
    else if(e.key==='Home'){{ e.preventDefault(); pause(); setSeq(0); }}
    else if(e.key==='End'){{ e.preventDefault(); pause(); setSeq(N); }}
  }});
  // hash init — supports #seq=10, #scene=xxx, #seq=10&scene=xxx, #scene-xxx
  (function(){{
    let h = location.hash||'';
    const mSeq = h.match(/seq=(\\d+)/);
    const mScene = h.match(/scene=([^&#]+)/);
    const mSceneDash = !mScene ? h.match(/#scene-([a-zA-Z0-9\\-_]+)/) : null;
    const sceneFromHash = mScene ? decodeURIComponent(mScene[1]) : (mSceneDash ? mSceneDash[1] : null);
    // support legacy #scene-xxx anchor (e.g. #scene-scene-01-goblin-ambush)
    let legacyScene = null;
    if(!sceneFromHash && h.indexOf('#scene-')===0) {{
      legacyScene = h.slice(7).split('&')[0].split('#')[0];
      if(legacyScene) legacyScene = decodeURIComponent(legacyScene);
    }}
    const sceneVal = sceneFromHash || legacyScene;
    if(sceneVal && filterScene) {{
      // verify it exists as option, else keep
      let found = false;
      for(let i=0;i<filterScene.options.length;i++) if(filterScene.options[i].value===sceneVal){{ found=true; break; }}
      if(found) filterScene.value = sceneVal;
      else if(sceneVal) filterScene.value = sceneVal; // allow even if not in dropdown (e.g. scene_id with dash)
    }}
    if(mSeq) setSeq(parseInt(mSeq[1],10), {{noHash:true}});
    else setSeq(0, {{noHash:true, force:true}});
    if(filterScene && filterScene.value) renderTimeline();
  }})();
  renderState(seq);
  renderTimeline();
  // expose for tests
  window.__FUSED_N = N;
  window.__FUSED_EVENTS = events;
  window.__FUSED_TIMELINE = timeline;
}})();
</script>
</body>
</html>
"""
    return html


def build_site(
    bundle_root: str | _pl.Path,
    out_dir: str | _pl.Path | None = None,
    title: str | None = None,
) -> _pl.Path:
    """Build a static site from a knowledge bundle.

    Args:
        bundle_root: path to knowledge bundle directory (contains events.jsonl)
                     or directly to events.jsonl
        out_dir: output directory (default ``<bundle_root>/site`` if bundle_root is dir,
                 else ``<events.jsonl parent>/site``). Created if missing.
        title: optional page title; falls back to bundle-derived.
    Returns:
        Path to out_dir (contains index.html + data.json + events.jsonl copy)
    Raises:
        FileNotFoundError if no events found and no bundle root exists
        RuntimeError on write failure
    """
    bundle = collect_bundle(bundle_root)
    # allow empty bundle (still generates skeleton)
    timeline = build_timeline(bundle_root, events=bundle["events"])
    root = _pl.Path(bundle["bundle_root"])
    if out_dir is None:
        out_dir_p = root / "site"
        # if bundle_root was a file, root is parent, site is parent/site
        if _pl.Path(bundle_root).is_file():
            out_dir_p = _pl.Path(bundle_root).parent / "site"
    else:
        out_dir_p = _pl.Path(out_dir)
    out_dir_p.mkdir(parents=True, exist_ok=True)

    html = _render_html(bundle, timeline, title=title)
    index_path = out_dir_p / "index.html"
    index_path.write_text(html, encoding="utf-8")

    # data.json (machine-readable)
    data = {
        "meta": {
            "title": title or f"Fused Campaign — {bundle.get('seed', 0)}",
            "bundle_root": bundle.get("bundle_root"),
            "seed": bundle.get("seed", 0),
            "events_count": len(bundle["events"]),
            "generated_at": bundle.get("generated_at"),
            "snapshots": bundle.get("snapshots", []),
            "manifest": bundle.get("manifest"),
        },
        "events": bundle["events"],
        "timeline": timeline,
    }
    try:
        (_pl.Path(out_dir_p) / "data.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass
    # events.json + events.jsonl copies for jq friendliness
    try:
        ep_raw = bundle.get("events_path")
        events_path = _pl.Path(ep_raw) if isinstance(ep_raw, (str, _pl.Path)) and ep_raw else None
        if events_path is not None and events_path.exists():
            # copy jsonl verbatim
            import shutil as _sh

            _sh.copy2(events_path, out_dir_p / "events.jsonl")
            # also pretty json
            (_pl.Path(out_dir_p) / "events.json").write_text(
                json.dumps(bundle["events"], indent=2, default=str), encoding="utf-8"
            )
        else:
            (_pl.Path(out_dir_p) / "events.json").write_text(
                json.dumps(bundle["events"], indent=2, default=str), encoding="utf-8"
            )
    except Exception:
        pass
    # copy manifest if present
    try:
        m = _pl.Path(root) / "manifest.json"
        if m.exists():
            import shutil as _sh

            _sh.copy2(m, out_dir_p / "manifest.json")
    except Exception:
        pass
    return out_dir_p
