from dnd_tools.dice import roll_dice, seed


def test_seed_deterministic():
    seed(42)
    a = roll_dice("1d20")
    seed(42)
    b = roll_dice("1d20")
    assert a == b


def test_roll_dice_basic_range():
    seed(1)
    v = roll_dice("1d20")
    assert 1 <= v <= 20
    v2 = roll_dice("2d6")
    assert 2 <= v2 <= 12


def test_advantage_keep_highest():
    seed(123)
    # 2d20kh1 should be max of two 1d20 rolls
    seed(123)
    rolls = [roll_dice("1d20"), roll_dice("1d20")]
    expected = max(rolls)
    seed(123)
    adv = roll_dice("2d20kh1")
    assert adv == expected


def test_disadvantage_keep_lowest():
    seed(99)
    seed(99)
    rolls = [roll_dice("1d20"), roll_dice("1d20")]
    expected = min(rolls)
    seed(99)
    dis = roll_dice("2d20kl1")
    assert dis == expected


def test_modifier():
    seed(7)
    v = roll_dice("1d20+5")
    assert 6 <= v <= 25
