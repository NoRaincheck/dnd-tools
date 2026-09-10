from adventure_webapp.engine import AdventureEngine


def test_templates_exist():
    eng = AdventureEngine()
    tpls = eng.list_templates()
    assert len(tpls) >= 3
    assert any(t["template_id"] == "veiled-archive" for t in tpls)


def test_create_game_has_pending():
    eng = AdventureEngine()
    g = eng.create_game(template_id="veiled-archive", actor="Elaria", seed=42)
    assert g.game_id
    assert g.scene.title
    assert g.clock()["segments"] == 6
    assert len(g.turns) == 1
    assert g.turns[0].picked is None


def test_pick_obvious_still_can_fail_or_partial():
    # Even the "safe" obvious pick goes through action_roll where 1-3 is failure.
    # Over many seeds we must see non-success outcomes for obvious.
    outcomes: set[str] = set()
    for seed in range(30):
        eng = AdventureEngine()
        g = eng.create_game(template_id="veiled-archive", actor="Elaria", seed=seed)
        res = eng.resolve_pick(g.game_id, "obvious", auto=False)
        turn = res["turn"]
        outcomes.add(turn["roll"]["outcome"])
    # deterministic seeded dice gives mixed outcomes, not always success
    assert "failure" in outcomes or "partial" in outcomes
    assert len(outcomes) >= 2


def test_auto_picks_via_triple_o():
    eng = AdventureEngine()
    g = eng.create_game(template_id="goblin-ambush", actor="Borin", seed=123)
    # auto internally rolls triple-o; outcome category must be one of three
    res = eng.resolve_pick(g.game_id, "obvious", auto=True)
    cat = res["turn"]["picked"]
    assert cat in ("obvious", "option", "odd")


def test_loop_until_clock_complete():
    eng = AdventureEngine()
    g = eng.create_game(template_id="starlit-heist", actor="Mira", seed=7, segments=4)
    steps = 0
    while not g.completed and steps < 10:
        eng.resolve_pick(g.game_id, "obvious", auto=False)
        steps += 1
    assert g.completed
    assert g.clock()["completed"] is True
    assert g.story_text() != "(story not yet started)"


def test_invalid_pick_raises():
    eng = AdventureEngine()
    g = eng.create_game(seed=1)
    try:
        eng.resolve_pick(g.game_id, "banana", auto=False)
        assert False, "should raise"
    except ValueError as e:
        assert "pick must be" in str(e)
