from fused.models import CharacterTraits, Scene
from fused.state import FusedState


def test_traits_separate_from_event_state():
    fs = FusedState(seed_val=42)
    ct = CharacterTraits(name="Lyra", archetype="ranger", traits=["Suspicious of authority"])
    fs.register_traits(ct)
    # register_traits is event-sourced (canonical log), so effects == 1
    assert len(fs.effects) == 1
    assert "Lyra" in fs.traits_registry
    # recording effects does not mutate traits
    eff = fs.record_effect("move", "Lyra", "Lyra moves to cover", payload={"x": 2, "y": 3})
    assert eff.actor == "Lyra"
    assert len(fs.effects) == 2
    assert fs.traits_registry["Lyra"].traits == ["Suspicious of authority"]
    # traits query via context is separate
    ctx = fs.context_for_actor("Lyra")
    assert ctx["traits"] is not None
    assert any("Suspicious" in t for t in ctx["traits_detail"]["traits"])


def test_scene_narrative_structure():
    fs = FusedState(seed_val=1)
    sc = Scene(scene_id="s01", title="Ambush", objective="Survive", location="wilderlands")
    fs.add_scene(sc)
    cur = fs.current_scene()
    assert cur is not None and cur.scene_id == "s01"
    assert fs.campaign.campaign_meta["active_scene"] == "s01"
    # add_scene is event-sourced, so one effect already
    assert len(fs.effects) == 1
    # effects attach to scene
    fs.record_effect("attack", "Elaria", "hits goblin", scene_id="s01")
    assert len(fs.effects) == 2
    assert sc.effect_ids[0].startswith("s01")


def test_snapshot_restore_roundtrips():
    fs = FusedState(seed_val=99)
    fs.register_traits(CharacterTraits(name="Borin", archetype="fighter", traits=["Brave"]))
    fs.add_scene(Scene(scene_id="s01", title="Test", objective="Obj"))
    fs.record_effect("test", "Borin", "does thing")
    # trait + scene + test = 3 events
    assert len(fs.effects) == 3
    snap = fs.snapshot()
    fs2 = FusedState(seed_val=0)
    fs2.restore(snap)
    assert "Borin" in fs2.traits_registry
    assert len(fs2.effects) == 3
    assert fs2.scenes[0].title == "Test"
