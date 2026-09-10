import json
from pathlib import Path

from fused.models import CharacterTraits, Scene
from fused.site import build_site, build_timeline, collect_bundle
from fused.state import FusedState


def test_collect_bundle_and_timeline(tmp_path: Path):
    fs = FusedState(seed_val=7, bundle_root=tmp_path / "bundle")
    fs.register_traits(CharacterTraits(name="A", archetype="fighter", traits=["brave"]))
    sc = Scene(scene_id="s01", title="Test", objective="Obj", beats=["a", "b"])
    fs.add_scene(sc)
    fs.record_effect("move", "A", "A moves", payload={"x": 1})
    fs.tick_clock("s01-progress", 2)
    # no need to flush: events are on disk via bundle_root
    bundle = collect_bundle(tmp_path / "bundle")
    assert len(bundle["events"]) >= 3
    assert bundle["seed"] == 7
    timeline = build_timeline(tmp_path / "bundle")
    assert len(timeline) == len(bundle["events"]) + 1
    # seq 0 initial
    assert timeline[0]["traits"] == []
    # final after all events includes trait
    assert "A" in timeline[-1]["traits"]
    # clocks at final should have ticks 2
    assert "s01-progress" in timeline[-1]["clocks"]
    assert timeline[-1]["clocks"]["s01-progress"]["ticks"] == 2


def test_build_site_generates_rewind_player(tmp_path: Path):
    bundle_root = tmp_path / "bundle2"
    fs = FusedState(seed_val=42, bundle_root=bundle_root)
    fs.register_traits(CharacterTraits(name="Lyra", archetype="ranger", traits=["keen"]))
    sc = Scene(scene_id="scene-01", title="Ambush", objective="Survive", beats=["start", "fight"])
    fs.add_scene(sc)
    fs.record_effect("encounter-start", "GM", "start encounter", scene_id="scene-01")
    fs.tick_clock("scene-01-progress", 1)
    fs.record_effect("scene-end", "GM", "end", scene_id="scene-01")

    out = build_site(bundle_root, out_dir=tmp_path / "site", title="Test Site")
    assert (out / "index.html").exists()
    html = (out / "index.html").read_text(encoding="utf-8")
    # rewind/playthrough controls
    for needle in [
        'id="scrub"',
        'id="btn-play"',
        'id="btn-prev"',
        'id="btn-next"',
        "window.__fused_set_seq",
        "__FUSED_TIMELINE__",
        "playbar",
        "Rewind / Playthrough",
    ]:
        assert needle in html, f"missing {needle}"
    # deep-link hash handling
    assert "#seq=" in html
    # keyboard hints
    assert "Space" in html or "space" in html.lower()
    # data.json
    data = json.loads((out / "data.json").read_text())
    assert data["meta"]["seed"] == 42
    assert len(data["events"]) >= 5
    assert len(data["timeline"]) == len(data["events"]) + 1
    # timeline states are ordered and monotonic in effects_count (non-decreasing)
    counts = [t["effects_count"] for t in data["timeline"]]
    assert counts == sorted(counts)
    # events.json copy exists
    assert (out / "events.jsonl").exists()


def test_build_site_empty_bundle(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    out = build_site(empty, out_dir=tmp_path / "site-empty")
    html = (out / "index.html").read_text()
    assert "0 events" in html
    # still has player chrome
    assert 'id="scrub"' in html


def test_build_site_direct_events_path(tmp_path: Path):
    # allow passing events.jsonl directly
    bundle_root = tmp_path / "direct"
    fs = FusedState(seed_val=9, bundle_root=bundle_root)
    fs.register_traits(CharacterTraits(name="B", archetype="wizard"))
    fs.record_effect("test", "B", "hello")
    events_path = bundle_root / "events.jsonl"
    out = build_site(events_path, out_dir=tmp_path / "site-direct")
    assert (out / "index.html").exists()
    html = (out / "index.html").read_text()
    assert "B" in html


def test_build_site_choice_timeline_shows_available_and_chosen(tmp_path: Path):
    from fused.events import append_event, make_event

    bundle_root = tmp_path / "bundle-choice"
    bundle_root.mkdir()
    log = bundle_root / "events.jsonl"
    # proposed — all three branches available
    proposed = make_event(
        effect_id="scene-01-0000-aaa",
        type="fused.choice.proposed",
        actor="Elaria",
        scene_id="scene-01",
        kind="choice",
        summary="Choice proposed: what does Elaria do?",
        payload={
            "choice": {
                "choice_id": "c-001",
                "actor": "Elaria",
                "situation": "Survive the ambush — what does Elaria do?",
                "obvious": "Elaria holds position and attacks the nearest foe",
                "option": "Elaria repositions for flanking",
                "odd": "Elaria tries an impulsive stunt",
                "position": "risky",
                "effect": "standard",
                "trivial": False,
                "roll": None,
                "rolls": [],
                "category": None,
            },
            "proposal": {
                "obvious": "Elaria holds position and attacks the nearest foe",
                "option": "Elaria repositions for flanking",
                "odd": "Elaria tries an impulsive stunt",
            },
        },
        seed=42,
        round=1,
        scene_title="Goblin Ambush",
    )
    append_event(log, proposed)
    # resolved — obvious chosen via roll 6, ticks 2
    resolved = make_event(
        effect_id="scene-01-0001-bbb",
        type="fused.choice.resolved",
        actor="Elaria",
        scene_id="scene-01",
        kind="choice",
        summary="Choice obvious (rolled): Elaria holds position and attacks the nearest foe",
        payload={
            "choice": {
                "choice_id": "c-001",
                "actor": "Elaria",
                "situation": "Survive the ambush — what does Elaria do?",
                "obvious": "Elaria holds position and attacks the nearest foe",
                "option": "Elaria repositions for flanking",
                "odd": "Elaria tries an impulsive stunt",
                "position": "risky",
                "effect": "standard",
                "trivial": False,
                "roll": 6,
                "rolls": [6],
                "category": "obvious",
                "choice_text": "Elaria holds position and attacks the nearest foe",
                "resolved_via": "rolled",
                "ticks": 2,
            },
            "choice_id": "c-001",
            "category": "obvious",
            "roll": 6,
            "rolls": [6],
            "choice_text": "Elaria holds position and attacks the nearest foe",
            "resolved_via": "rolled",
        },
        seed=42,
        round=1,
        scene_title="Goblin Ambush",
    )
    append_event(log, resolved)

    out = build_site(bundle_root, out_dir=tmp_path / "site-choice")
    html = (out / "index.html").read_text()
    # timeline JS must render choices: look for choice-specific chrome
    assert "choiceBlock" in html
    assert "choice-grid" in html
    assert "choice-card" in html
    # embedded events JSON retains all three branches
    data = json.loads((out / "data.json").read_text())
    assert len(data["events"]) == 2
    assert "Elaria holds position" in json.dumps(data["events"])
    assert "Elaria tries an impulsive stunt" in json.dumps(data["events"])
    # resolved has roll/category
    resolved_evt = data["events"][1]
    p = resolved_evt["data"]["payload"]["choice"]
    assert p["category"] == "obvious"
    assert p["roll"] == 6
    # HTML should contain helpers for showing available vs chosen
    assert "obvious" in html.lower()
    assert "Available" not in html or "Situation" in html  # situation header
