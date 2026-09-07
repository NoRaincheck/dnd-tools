from triple_o.core import TripleO
from triple_o.spark import ACTION_TABLE, DISPOSITION_TABLE, roll_action, roll_disposition, roll_spark


def test_tables_complete():
    assert len(DISPOSITION_TABLE) == 6
    assert len(ACTION_TABLE) == 6
    for i in range(1, 7):
        assert "disposition" in DISPOSITION_TABLE[i]
        assert "motivation" in DISPOSITION_TABLE[i]
        assert "action" in ACTION_TABLE[i]
        assert "method" in ACTION_TABLE[i]


def test_spark_deterministic():
    TripleO(seed=42)
    _first = roll_spark()
    TripleO(seed=42)
    # need reseed because spark uses global RNG
    from dnd_tools import dice

    dice.seed(42)
    r2 = roll_spark()
    # Actually earlier _first consumed RNG, so reseed to compare first spark after reseed
    dice.seed(42)
    r1_again = roll_spark()
    assert r1_again == r2
    assert _first == r2  # first spark after reseed should match


def test_rolls_in_range():
    from dnd_tools import dice

    dice.seed(0)
    for _ in range(20):
        d = roll_disposition()
        assert 1 <= d["roll"] <= 6
        a = roll_action()
        assert 1 <= a["roll"] <= 6
        s = roll_spark()
        assert 1 <= s["disposition_roll"] <= 6
        assert 1 <= s["action_roll"] <= 6
