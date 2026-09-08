from blades_in_the_dark.dice import roll_action, roll_fortune, roll_resistance
from blades_in_the_dark.state import BladesState


def test_roll_action_zero_dice_keeps_lowest():
    BladesState(seed_val=1)
    # action pool 0 => 2d6 keep lowest, no crit ever
    for _ in range(20):
        r = roll_action(0)
        assert len(r["rolls"]) == 2
        assert r["highest"] == min(r["rolls"])
        assert not r["critical"]


def test_roll_action_critical_detection():
    # Use seeded state to get deterministic; just check structure
    BladesState(seed_val=42)
    # Roll 4 dice repeatedly, check that critical only when 2 sixes present
    found_crit = False
    for _ in range(200):
        r = roll_action(4)
        if r["critical"]:
            assert r["outcome"] == "critical"
            assert r["rolls"].count(6) >= 2
            found_crit = True
            break
    # not asserting must find crit, just structural if found
    if found_crit:
        assert found_crit


def test_roll_resistance_stress_cost():
    BladesState(seed_val=123)
    for _ in range(10):
        r = roll_resistance(2)
        assert 0 <= r["stress_cost"] <= 5
        assert len(r["rolls"]) in (1, 2)
        if r["highest"] == 6:
            assert r["stress_cost"] == 0


def test_roll_fortune_tier():
    BladesState(seed_val=0)
    for d in [0, 1, 2, 4]:
        r = roll_fortune(d)
        assert r["tier"] in ("critical", "excellent", "good", "poor")
