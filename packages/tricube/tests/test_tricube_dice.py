from dnd_tools.dice import seed

from tricube.dice import opposed_result, reevaluate_with_difficulty, roll_tricube


def test_roll_tricube_deterministic():
    seed(42)
    r1 = roll_tricube(3, 5)
    seed(42)
    r2 = roll_tricube(3, 5)
    assert r1["rolls"] == r2["rolls"]
    assert r1["successes"] == r2["successes"]


def test_roll_tricube_counts():
    seed(1)
    r = roll_tricube(2, 6)
    # each die >=6 counts
    assert r["successes"] == sum(1 for v in r["rolls"] if v >= 6)
    assert r["success"] == (r["successes"] >= 1)
    assert r["exceptional"] == (r["successes"] >= 2)
    assert r["critical_failure"] == all(v == 1 for v in r["rolls"])


def test_reevaluate():
    rolls = [4, 5, 2]
    r = reevaluate_with_difficulty(rolls, 4)
    assert r["successes"] == 2
    r2 = reevaluate_with_difficulty(rolls, 6)
    assert r2["successes"] == 0


def test_opposed_both_crit():
    out = opposed_result([1, 1], [1, 1, 1])
    assert out["winner"] == "both_crit"


def test_opposed_highest_wins():
    out = opposed_result([6, 2, 1], [4, 3])
    # a_high 6 vs b_high 4 -> a needs >=4 (success with 6), b needs >=6 (fail)
    assert out["winner"] == "a"


def test_opposed_tie_most_matches():
    out = opposed_result([5, 5, 2], [5, 2, 1])
    # both succeed, a has 2 matches, b has 1
    assert out["winner"] == "a"
