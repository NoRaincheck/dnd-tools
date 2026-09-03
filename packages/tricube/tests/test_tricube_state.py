from pathlib import Path

from tricube.models import TricubeCharacter
from tricube.state import TricubeCampaignState, TricubeState


def _char(name="Hero"):
    return TricubeCharacter(name=name, trait="brawny", concept="knight", perks=["brave"], quirks=["stubborn"])


def test_add_and_get():
    s = TricubeState(seed_val=0, map_w=10, map_h=10)
    c = _char("Aria")
    s.add_player(c, (1, 1, 0))
    assert s.get_character("Aria") is c
    assert s.get_pos("Aria") == (1, 1, 0)


def test_update_resolve_and_affliction():
    s = TricubeState(seed_val=0)
    c = _char("Bob")
    s.add_player(c, (0, 0, 0))
    s.update_resolve("Bob", -3)
    # should have gained affliction and recovered to max
    assert c.resolve == c.resolve_max
    assert len(c.afflictions) == 1
    assert s.affliction_log


def test_retirement():
    s = TricubeState(seed_val=0)
    c = _char("Doomed")
    s.add_player(c, (0, 0, 0))
    for _ in range(4):
        s.update_resolve("Doomed", -3)
    assert c.retired
    assert not c.alive


def test_distance_and_los():
    s = TricubeState(seed_val=0, map_w=5, map_h=5)
    s.add_player(_char("A"), (0, 0, 0))
    s.add_player(_char("B"), (4, 0, 0))
    assert s.line_of_sight("A", "B") is True
    s.map[0][2].z = 2
    assert s.line_of_sight("A", "B") is False
    s2 = TricubeState(seed_val=0, map_w=20, map_h=20)
    s2.add_player(_char("A"), (0, 0, 0))
    s2.add_player(_char("B"), (3, 4, 0))
    assert s2.distance_feet("A", "B") == 25.0


def test_initiative_deterministic():
    s1 = TricubeState(seed_val=42)
    s1.add_player(_char("P1"), (0, 0, 0))
    s1.add_monster(_char("M1"), (1, 0, 0))
    r1 = s1.roll_initiative()
    order1 = list(s1.initiative_order)
    s2 = TricubeState(seed_val=42)
    s2.add_player(_char("P1"), (0, 0, 0))
    s2.add_monster(_char("M1"), (1, 0, 0))
    r2 = s2.roll_initiative()
    order2 = list(s2.initiative_order)
    assert r1 == r2
    assert order1 == order2


def test_campaign_snapshot_restore():
    cs = TricubeCampaignState(seed_val=10, map_w=10, map_h=10)
    p = _char("Aria")
    cs.inner.add_player(p, (2, 2, 0))
    snap = cs.snapshot()
    cs.inner.update_resolve("Aria", -3)
    assert len(p.afflictions) == 1
    cs.restore(snap)
    ch2 = cs.inner.get_character("Aria")
    assert ch2 is not None
    assert len(ch2.afflictions) == 0
    assert ch2.resolve == 3


def test_campaign_save_load(tmp_path: Path):
    cs = TricubeCampaignState(seed_val=5)
    p = _char("Boris")
    cs.inner.add_player(p, (1, 1, 0))
    cs.inner.update_resolve("Boris", -3)
    path = tmp_path / "save.json"
    cs.save(path)
    assert path.exists()
    cs2 = TricubeCampaignState.load(path)
    ch1 = cs.inner.get_character("Boris")
    ch2 = cs2.inner.get_character("Boris")
    assert ch1 is not None and ch2 is not None
    assert len(ch2.afflictions) == len(ch1.afflictions)


def test_long_rest_clears_scene_afflictions():
    cs = TricubeCampaignState(seed_val=0)
    p = _char("Cleric")
    cs.inner.add_player(p, (0, 0, 0))
    cs.inner.update_resolve("Cleric", -3)
    # add non-scene permanent manually
    from tricube.models import Affliction

    p.afflictions.append(Affliction(name="curse", permanent=True, recovery="permanent"))
    cs.long_rest()
    # scene one cleared, permanent remains
    assert any(a.permanent for a in p.afflictions)
    assert not any(a.recovery == "scene" for a in p.afflictions)
