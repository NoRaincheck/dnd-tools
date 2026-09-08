import json
import tempfile
from pathlib import Path

from fused.events import iter_events, validate_log
from fused.models import CharacterTraits, Scene
from fused.projection import build_projection, query_events
from fused.state import FusedState


def test_event_log_is_canonical_and_valid():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "campaign"
        fs = FusedState(seed_val=42, bundle_root=root)
        fs.register_traits(CharacterTraits(name="Elaria", archetype="ranger", traits=["Suspicious"]))
        sc = Scene(scene_id="scene-01", title="Ambush", objective="Survive road", seed=42)
        fs.add_scene(sc)
        fs.record_effect("attack", "Elaria", "hits goblin", payload={"damage": 7}, scene_id="scene-01")
        # log exists and is valid
        log = root / "events.jsonl"
        assert log.exists()
        lines = log.read_text().strip().splitlines()
        assert len(lines) >= 3  # trait + scene + effect
        for line in lines:
            evt = json.loads(line)
            assert evt["specversion"] == "1.0"
            assert "id" in evt and "type" in evt
        assert validate_log(log) == []


def test_snapshot_and_replay_is_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "campaign"
        fs = FusedState(seed_val=7, bundle_root=root, snapshot_every=2)
        fs.register_traits(CharacterTraits(name="Lyra", archetype="wizard"))
        fs.add_scene(Scene(scene_id="s1", title="T1", objective="O1"))
        fs.record_effect("move", "Lyra", "moved", scene_id="s1")
        fs.record_effect("attack", "Lyra", "attacks", scene_id="s1")
        # snapshot taken every 2 effects
        snaps = list((root / "snapshots").glob("*.json"))
        assert len(snaps) >= 1
        # replay from log should match in-memory state
        fs2 = FusedState.from_log(root / "events.jsonl")
        assert len(fs2.effects) == len(fs.effects)
        assert fs2.effects[0].summary == fs.effects[0].summary
        assert "Lyra" in fs2.traits_registry


def test_projection_is_idempotent_and_rebuildable():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "campaign"
        fs = FusedState(seed_val=42, bundle_root=root)
        fs.register_traits(CharacterTraits(name="Elaria", archetype="ranger", traits=["Brave"]))
        fs.add_scene(Scene(scene_id="scene-01", title="T", objective="O"))
        fs.record_effect(
            "attack", "Elaria", "hits", payload={"damage": 5, "wound": {"type": "slashing"}}, scene_id="scene-01"
        )
        db = root / "projections" / "campaign.db"
        p1 = build_projection(root / "events.jsonl", db)
        assert p1.exists()
        rows1 = query_events(db, actor="Elaria")
        assert len(rows1) >= 1
        # second build is idempotent — same row count
        build_projection(root / "events.jsonl", db)
        rows2 = query_events(db, actor="Elaria")
        assert len(rows2) == len(rows1)
        # delete and rebuild yields same
        db.unlink()
        assert not db.exists()
        build_projection(root / "events.jsonl", db)
        rows3 = query_events(db, actor="Elaria")
        assert len(rows3) == len(rows1)


def test_traversable_history_filters():
    fs = FusedState(seed_val=7)
    fs.add_scene(Scene(scene_id="s1", title="T1", objective="O1"))
    fs.add_scene(Scene(scene_id="s2", title="T2", objective="O2"))
    fs.record_effect("move", "A", "moved", scene_id="s1")
    fs.record_effect("attack", "A", "attacks", scene_id="s2")
    fs.record_effect("move", "B", "moved", scene_id="s2")
    # s1 has scene-create + move = 2; s2 has scene-create + attack + move = 3
    assert len(fs.traverse_history(scene_id="s1")) == 2
    assert len(fs.traverse_history(scene_id="s2")) == 3
    assert len(fs.traverse_history(actor="A")) == 2
    assert len(fs.traverse_history(kind="move")) == 2
    assert len(fs.traverse_history(last_n=1)) == 1


def test_jq_query_examples_work_on_log():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "c"
        fs = FusedState(seed_val=99, bundle_root=root)
        fs.register_traits(CharacterTraits(name="Elaria", archetype="ranger"))
        fs.add_scene(Scene(scene_id="scene-01", title="T", objective="Reach tower"))
        fs.record_effect(
            "attack", "Elaria", "wounds goblin", payload={"wound": {"severity": "moderate"}}, scene_id="scene-01"
        )
        # simulate jq: select wound != null
        wounds = [
            e
            for e in iter_events(root / "events.jsonl")
            if e.get("data", {}).get("payload", {}).get("wound") is not None
        ]
        assert len(wounds) == 1
        assert wounds[0]["subject"] == "Elaria"
