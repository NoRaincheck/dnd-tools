import tempfile
from pathlib import Path

from fused.models import CharacterTraits, Scene
from fused.okf import OKFBundle
from fused.state import FusedState


def test_okf_bundle_conformance():
    with tempfile.TemporaryDirectory() as tmp:
        fs = FusedState(seed_val=42, bundle_root=tmp)
        fs.register_traits(CharacterTraits(name="Elaria", archetype="ranger", traits=["Suspicious of authority"]))
        sc = Scene(
            scene_id="scene-01",
            title="Ambush",
            objective="Survive road",
            location="wilderlands",
            patron="Guild",
            threat="goblin",
            beats=["beat1"],
            cast=["Elaria"],
            seed=42,
        )
        fs.add_scene(sc)
        fs.record_effect("encounter-start", "GM", "Scene starts", scene_id="scene-01")
        root = fs.export_okf()
        # every non-reserved md must have type
        errs = OKFBundle.validate_bundle(root)
        assert errs == [], f"validation failed: {errs}"
        # bundle has expected structure
        assert (Path(root) / "traits" / "elaria.md").exists()
        assert (Path(root) / "scenes" / "scene-01.md").exists()
        assert (Path(root) / "events").exists()
        assert (Path(root) / "index.md").exists()
        assert (Path(root) / "log.md").exists()
        # trait file frontmatter contains type
        text = (Path(root) / "traits" / "elaria.md").read_text()
        assert "type: Trait" in text
        # characters are written only if CampaignState has them; we have none, so traits check is enough
        # but scenes must exist
        assert "type: Scene" in (Path(root) / "scenes" / "scene-01.md").read_text()
        # event
        ev_files = list((Path(root) / "events").glob("*.md"))
        # filter index.md
        concepts = [p for p in ev_files if p.name != "index.md"]
        assert len(concepts) >= 1
        assert "type: Effect" in concepts[0].read_text()


def test_okf_traversable_history():
    fs = FusedState(seed_val=7)
    fs.add_scene(Scene(scene_id="s1", title="T1", objective="O1"))
    fs.add_scene(Scene(scene_id="s2", title="T2", objective="O2"))
    fs.record_effect("move", "A", "moved", scene_id="s1")
    fs.record_effect("attack", "A", "attacks", scene_id="s2")
    fs.record_effect("move", "B", "moved", scene_id="s2")
    # traverse filters
    assert len(fs.traverse_history(scene_id="s1")) == 1
    assert len(fs.traverse_history(actor="A")) == 2
    assert len(fs.traverse_history(kind="move")) == 2
    assert len(fs.traverse_history(last_n=1)) == 1
