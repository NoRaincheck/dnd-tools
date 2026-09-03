from tricube.models import TricubeCharacter
from tricube.state import TricubeState
from tricube.tools import TricubeTools


def _setup():
    s = TricubeState(seed_val=0, map_w=10, map_h=10)
    p = TricubeCharacter(
        name="Hero", trait="agile", concept="ranger", perks=["keen"], quirks=["reckless"], karma=2, resolve=3
    )
    m = TricubeCharacter(
        name="Gob", trait="brawny", concept="goblin", perks=[], quirks=[], rank=1, is_player=False, resolve=3
    )
    s.add_player(p, (1, 1, 0))
    s.add_monster(m, (2, 1, 0))
    s.effort_pools["Gob"] = 2
    return s, TricubeTools(s)


def test_check_karma_resolve_logs():
    s, t = _setup()
    r = t.check_karma_resolve("Hero")
    assert r["karma"] == 2
    assert s.tool_trace[-1]["tool"] == "check_karma_resolve"


def test_roll_challenge_out_of_scope():
    _s, t = _setup()
    # Hero agile, so brawny is -1 die, out_of_scope further -1
    r = t.roll_challenge("Hero", "brawny", difficulty=5, out_of_scope=True)
    assert r["dice_count"] == 1  # 2 base -1


def test_quirk_and_karma_flow():
    s, t = _setup()
    hero = s.get_character("Hero")
    assert hero is not None
    # ensure karma not max to see increase
    hero.karma = 1
    t.invoke_quirk("Hero", "reckless")
    assert hero._pending_quirk == "reckless"
    r = t.roll_challenge("Hero", "agile", difficulty=5)
    # pending should be auto-cleared and karma gained
    assert hero._pending_quirk is None
    assert hero.karma == 2  # +1 from quirk
    # now spend karma
    if not r["success"]:
        nr = t.spend_karma("Hero", r["rolls"], r["effective_difficulty"])
        assert "karma" in nr
    else:
        # force a failing roll to test spend
        # manually make fail
        hero.karma = 2
        fake_rolls = [2, 2]
        nr = t.spend_karma("Hero", fake_rolls, 5)
        assert nr["new_difficulty"] == 4


def test_effort_removal():
    _s, t = _setup()
    t.set_effort("Gob", 2)
    assert _s.effort_pools["Gob"] == 2
    # roll that will maybe succeed; do several until success
    # force success by using low difficulty
    r = t.roll_challenge("Hero", "agile", difficulty=2, effort_target="Gob")
    assert _s.effort_pools["Gob"] == 2 - r["effort_removed"]


def test_defense_and_affliction():
    s, t = _setup()
    hero = s.get_character("Hero")
    assert hero is not None
    hero.resolve = 1
    # failing defense should cause affliction
    # use very hard difficulty to ensure fail
    r = t.defense_roll("Hero", "agile", difficulty=6)
    # may fail or succeed depending on dice, but check log
    assert "resolve_cost" in r
    # if failed with 1 resolve, should have affliction after
    if r["resolve_cost"] > 0 and hero.resolve == 3:  # recovered after affliction
        assert len(hero.afflictions) >= 1


def test_fear_and_opposed():
    _s, t = _setup()
    r = t.fear_check("Hero", difficulty=5, inexperienced=False)
    assert "resolve_cost" in r
    out = t.opposed_challenge("Hero", "Gob", trait_a="crafty", trait_b="brawny")
    assert "winner" in out


def test_tool_schemas():
    _s, t = _setup()
    schemas = t.tool_schemas()
    assert len(schemas) >= 20
    names = {s["function"]["name"] for s in schemas}
    assert "roll_challenge" in names
    assert "visualize_map" in names
