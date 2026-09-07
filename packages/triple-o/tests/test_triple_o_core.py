from triple_o.core import TripleO, _category_for_roll


def test_category_mapping():
    assert _category_for_roll(4) == "obvious"
    assert _category_for_roll(5) == "obvious"
    assert _category_for_roll(6) == "obvious"
    assert _category_for_roll(2) == "option"
    assert _category_for_roll(3) == "option"
    assert _category_for_roll(1) == "odd"


def test_roll_deterministic():
    e1 = TripleO(seed=42)
    e2 = TripleO(seed=42)
    r1 = [e1.roll().roll for _ in range(10)]
    e2.reseed(42)
    r2 = [e2.roll().roll for _ in range(10)]
    assert r1 == r2


def test_double_down_advantage_favours_obvious():
    # advantage picks max, so should be at least as high as single?
    # deterministic check: with seed, roll with advantage distribution differs
    e = TripleO(seed=0)
    # just verify it uses 2 dice and category matches max
    r = e.roll(advantage="advantage")
    assert len(r.rolls) == 2
    assert r.roll == max(r.rolls)
    assert r.category == _category_for_roll(r.roll)

    e2 = TripleO(seed=0)
    r2 = e2.roll(advantage="disadvantage")
    assert len(r2.rolls) == 2
    assert r2.roll == min(r2.rolls)


def test_propose_and_resolve():
    e = TripleO(seed=10)
    p = e.propose("Lyra", "gate", obvious="snipe", option="flank", odd="charge")
    assert p.character == "Lyra"
    res = e.resolve(p)
    assert res["category"] in ("obvious", "option", "odd")
    assert res["choice"] in ("snipe", "flank", "charge")
    assert res["choice"] == p.choice_for(res["category"])


def test_propose_validation():
    e = TripleO(seed=1)
    try:
        e.propose("A", "s", obvious="", option="b", odd="c")
        assert False, "should raise"
    except ValueError:
        pass


def test_question():
    e = TripleO(seed=0)
    q = e.question("Do they search for traps?", yes_is_obvious=True)
    assert q["category"] in ("obvious", "option", "odd")
    assert "answer" in q
    # odd should map to No / rush in when yes_is_obvious
    e2 = TripleO(seed=0)
    # force check: just ensure structure
    q2 = e2.question("Are they suspicious?", yes_is_obvious=False)
    assert q2["yes_is_obvious"] is False


def test_group_resolve():
    e = TripleO(seed=42)
    res = e.group_resolve(["brave", "cautious", "reckless"], ["hold", "negotiate", "flee"])
    assert res["choice"] in ["hold", "negotiate", "flee"]
    assert res["category"] in ("obvious", "option", "odd")
    # explicit assignment
    res2 = e.group_resolve([], [], assignment="given", obvious_plan="A", option_plan="B", odd_plan="C")
    assert res2["plans"]["obvious"] == "A"
