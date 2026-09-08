import tempfile
from pathlib import Path

from fused.models import CharacterTraits
from fused.session import FusedSession
from fused.state import FusedState
from fused.tools import FusedTools


def test_fused_tools_traits_separate_and_history_traversal():
    fs = FusedState(seed_val=42)
    ft = FusedTools(fs)
    ft.register_traits(name="Lyra", ancestry="elf", traits=["Suspicious of authority"], flaws=["Vindictive"])
    assert ft.get_traits("Lyra")["found"] is True
    assert any("Suspicious" in t for t in ft.get_traits("Lyra")["traits"])
    # register_traits also records a trait-register effect (event state), filtered move history empty
    assert ft.traverse_history(kind="move") == []
    ft.record_effect(kind="move", actor="Lyra", summary="Lyra advances")
    # trait unchanged, event recorded (now 2 effects for Lyra: trait-register + move)
    assert ft.get_traits("Lyra")["traits"] == ["Suspicious of authority"]
    hist = ft.traverse_history(actor="Lyra", kind="move")
    assert len(hist) == 1 and hist[0]["kind"] == "move"
    # get_context combines both but keeps separate (includes trait-register + move)
    ctx = ft.get_context("Lyra")
    assert ctx["traits"] is not None
    assert len(ctx["recent_effects"]) == 2


def test_fused_tools_scene_structure():
    fs = FusedState(seed_val=10)
    ft = FusedTools(fs)
    ft.create_scene(
        scene_id="s01",
        title="Ambush",
        objective="Hold",
        location="wilderlands",
        threat="goblin",
        beats=["b1", "b2"],
        cast=["Lyra"],
    )
    scenes = ft.list_scenes()
    assert len(scenes) == 1
    assert scenes[0]["scene_id"] == "s01"
    sc = ft.get_scene("s01")
    assert sc["title"] == "Ambush"
    ft.advance_scene_beat(scene_id="s01", note="first beat done")
    # effect recorded
    hist = ft.traverse_history(kind="scene-beat")
    assert len(hist) == 1


def test_fused_session_projection_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "bundle"
        fs = FusedState(seed_val=42, bundle_root=bundle)
        fs.register_traits(CharacterTraits(name="Elaria", archetype="ranger", traits=["Suspicious of authority"]))
        sess = FusedSession(fs)
        from fused.models import Scene

        scene = Scene(scene_id="scene-01", title="Goblin Ambush", objective="Survive", location="wilderlands", seed=42)
        sess.add_scene_with_encounter(
            scene, player_specs=[("Elaria", "ranger", "medium")], monster_specs=["goblin"], map_kind="outdoor"
        )
        res = sess.run_scene(max_turns=4, use_heuristic=True, use_triple_o=True)
        assert "players" in res
        # log is canonical, validate it
        assert fs.validate_log() == []
        log = bundle / "events.jsonl"
        assert log.exists()
        # projection is idempotent — build twice gives same row count
        from fused.projection import build_projection, query_events

        db = bundle / "projections" / "campaign.db"
        build_projection(log, db)
        rows1 = query_events(db)
        build_projection(log, db)
        rows2 = query_events(db)
        assert len(rows2) == len(rows1)
        assert len(rows1) >= 4  # trait + scene + encounter-start + triple-o + scene-end
        # delete and rebuild still idempotent (can be recreated from events + snapshots)
        db.unlink()
        build_projection(log, db)
        rows3 = query_events(db)
        assert len(rows3) == len(rows1)
        # replay from log matches in-memory
        from fused.state import FusedState as FS2

        fs2 = FS2.from_log(log)
        assert len(fs2.effects) == len(fs.effects)
