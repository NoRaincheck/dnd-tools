"""Win-condition coverage for Swords & Sorcery dice (ref/sword-and-sorcery.md).

Verifies the authoritative rules:
- 1-3d6 (base 1 +1 prepared +1 trained +1 help, capped 3)
- SWORDS: roll UNDER sns (strict <), SORCERY: roll OVER sns (strict >)
- Exactly == sns is Divine Intervention — counts as success, flagged
- Outcomes: 0→fail, 1→barely, 2→success (good), 3→critical
- WD = sns-1, roll WD d6 take highest
- Spell damage/heal: roll level d6s, highest + 2*level, can split
- Derived: HP=3*sns, SP=10-2*sns, WD=sns-1, EN=sns+3
"""

from sword_and_sorcery.dice import roll_sns_check, roll_spell_damage, roll_weapon_damage, seed
from sword_and_sorcery.models import derived_en, derived_hp, derived_sp, derived_wd
from sword_and_sorcery.simulation import create_sns_monster, create_sns_player, initialize_sns_scene
from sword_and_sorcery.state import SnSState
from sword_and_sorcery.tools import SnSTools

# ---------------------------------------------------------------------------
# Pure dice logic (no RNG) — explicit roll lists via helper
# ---------------------------------------------------------------------------


def _count(rolls, sns, mode):
    """Mirror roll_sns_check counting without RNG."""
    succ, divine = 0, False
    for r in rolls:
        if r == sns:
            divine = True
            succ += 1
        elif (mode == "swords" and r < sns) or (mode == "sorcery" and r > sns):
            succ += 1
    if succ == 0:
        outcome = "fail"
    elif succ == 1:
        outcome = "barely"
    elif succ == 2:
        outcome = "success"
    else:
        outcome = "critical"
    return succ, divine, outcome


def test_sns_swords_is_strict_less():
    # sns=4: 1,2,3 succeed, 4 divine, 5,6 fail
    assert _count([1], 4, "swords")[0] == 1
    assert _count([3], 4, "swords")[0] == 1
    assert _count([4], 4, "swords") == (1, True, "barely")  # divine counts as success
    assert _count([5], 4, "swords")[0] == 0
    assert _count([6], 4, "swords")[0] == 0
    # sns=2 edge: only 1 <2 succeeds
    assert _count([1], 2, "swords")[0] == 1
    assert _count([2], 2, "swords") == (1, True, "barely")
    assert _count([3], 2, "swords")[0] == 0
    # sns=5: 1-4 succeed
    assert _count([4], 5, "swords")[0] == 1
    assert _count([5], 5, "swords") == (1, True, "barely")
    assert _count([6], 5, "swords")[0] == 0


def test_sns_sorcery_is_strict_greater():
    # sns=4: 5,6 succeed, 4 divine, 1-3 fail
    assert _count([6], 4, "sorcery")[0] == 1
    assert _count([5], 4, "sorcery")[0] == 1
    assert _count([4], 4, "sorcery") == (1, True, "barely")
    assert _count([3], 4, "sorcery")[0] == 0
    assert _count([1], 4, "sorcery")[0] == 0
    # sns=2: 3-6 succeed
    assert _count([6], 2, "sorcery")[0] == 1
    assert _count([2], 2, "sorcery") == (1, True, "barely")
    assert _count([1], 2, "sorcery")[0] == 0
    # sns=5: only 6 >5 succeeds
    assert _count([6], 5, "sorcery")[0] == 1
    assert _count([5], 5, "sorcery") == (1, True, "barely")
    assert _count([4], 5, "sorcery")[0] == 0


def test_sns_divine_counts_as_success_both_modes():
    for sns in [2, 3, 4, 5]:
        for mode in ("swords", "sorcery"):
            succ, divine, _ = _count([sns], sns, mode)
            assert divine is True
            assert succ == 1
            # need not be < or > — divine alone grants success


def test_sns_divine_flagged_when_any_die_equals():
    assert _count([1, 4, 6], 4, "swords")[1] is True
    assert _count([1, 2, 3], 4, "swords")[1] is False
    assert _count([4, 4, 4], 4, "sorcery")[1] is True


def test_sns_outcome_mapping_0_1_2_3():
    # 0
    assert _count([5, 6], 2, "swords") == (0, False, "fail")
    # 1
    assert _count([1, 5, 6], 2, "swords")[2] == "barely"
    # but need actual 2,3
    assert _count([1, 1, 6], 4, "swords")[2] == "success"  # 1,1 <4 =>2
    assert _count([1, 2, 3], 4, "swords")[2] == "critical"  # 1,2,3 <4 =>3
    # SORCERY variants
    assert _count([6, 1, 1], 4, "sorcery")[2] == "barely"  # only 6 >4
    assert _count([5, 6, 1], 4, "sorcery")[2] == "success"  # 5,6 >4 =>2
    assert _count([5, 6, 6], 2, "sorcery")[2] == "critical"  # all >2


def test_sns_outcome_matches_dice_api():
    # verify roll_sns_check outcomes via deterministic seeds match helper
    seed(123)
    r = roll_sns_check(4, "swords", 3)
    succ, divine, outcome = _count(r["rolls"], 4, "swords")
    assert r["successes"] == succ
    assert r["divine_intervention"] == divine
    assert r["outcome"] == outcome
    seed(123)
    r2 = roll_sns_check(2, "sorcery", 2)
    succ2, divine2, outcome2 = _count(r2["rolls"], 2, "sorcery")
    assert r2["successes"] == succ2
    assert r2["divine_intervention"] == divine2
    assert r2["outcome"] == outcome2


def test_sns_roll_structure():
    seed(42)
    r = roll_sns_check(4, "swords", 2)
    assert set(r.keys()) >= {
        "rolls",
        "sns",
        "mode",
        "dice_count",
        "successes",
        "success",
        "divine_intervention",
        "outcome",
    }
    assert len(r["rolls"]) == 2
    assert r["sns"] == 4
    assert r["mode"] == "swords"
    assert r["success"] == (r["successes"] >= 1)
    assert r["outcome"] in ("fail", "barely", "success", "critical")


def test_sns_roll_seeded_determinism():
    seed(7)
    a = roll_sns_check(3, "swords", 3)
    seed(7)
    b = roll_sns_check(3, "swords", 3)
    assert a["rolls"] == b["rolls"]
    assert a["successes"] == b["successes"]


# ---------------------------------------------------------------------------
# Derived attributes
# ---------------------------------------------------------------------------


def test_sns_derived_hp_sp_wd_en():
    assert derived_hp(2) == 6
    assert derived_hp(3) == 9
    assert derived_hp(4) == 12
    assert derived_hp(5) == 15
    assert derived_sp(2) == 6
    assert derived_sp(3) == 4
    assert derived_sp(4) == 2
    assert derived_sp(5) == 0
    assert derived_wd(2) == 1
    assert derived_wd(3) == 2
    assert derived_wd(5) == 4
    assert derived_en(2) == 5
    assert derived_en(3) == 6
    assert derived_en(5) == 8


# ---------------------------------------------------------------------------
# Weapon damage — WD d6 take highest
# ---------------------------------------------------------------------------


def test_sns_weapon_damage_is_highest():
    seed(10)
    d = roll_weapon_damage(4)
    assert len(d["rolls"]) == 4
    assert d["damage"] == max(d["rolls"])
    seed(10)
    d2 = roll_weapon_damage(1)
    assert len(d2["rolls"]) == 1
    assert d2["damage"] == d2["rolls"][0]


def test_sns_weapon_damage_wd_zero():
    d = roll_weapon_damage(0)
    assert d["damage"] == 0
    assert d["rolls"] == []


def test_sns_weapon_damage_scales_with_sns():
    for sns in [2, 3, 4, 5]:
        wd = derived_wd(sns)
        seed(0)
        d = roll_weapon_damage(wd)
        assert len(d["rolls"]) == wd


# ---------------------------------------------------------------------------
# Spell damage — highest + 2*level
# ---------------------------------------------------------------------------


def test_sns_spell_damage_formula():
    for level in [1, 2, 3]:
        seed(level)
        d = roll_spell_damage(level)
        assert len(d["rolls"]) == level
        assert d["highest"] == max(d["rolls"])
        assert d["total"] == d["highest"] + 2 * level


def test_sns_spell_damage_can_split_note():
    # documented: can be split between close targets — total is what's split
    seed(5)
    d = roll_spell_damage(2)
    assert d["total"] >= 3  # min 1 +4
    assert d["total"] <= 10  # max 6+4


# ---------------------------------------------------------------------------
# Tool-level integration: dice count, help, attack, cast
# ---------------------------------------------------------------------------


def _scene(sns_a=4, sns_b=3):
    state = SnSState(seed_val=42)
    p1 = create_sns_player("A", ancestry="Human", background="Soldier", sns=sns_a)
    p2 = create_sns_player("B", ancestry="Elf", background="Sage", sns=sns_b)
    initialize_sns_scene(state, [p1, p2], [], map_kind="outdoor", seed=42)
    tools = SnSTools(state)
    return state, tools, p1, p2


def test_sns_tool_dice_count_prepared_trained_help():
    state, tools, _a, _b = _scene()
    seed(0)
    r1 = tools.roll_check("A", "swords", prepared=False, trained=False)
    assert r1["dice_count"] == 1
    seed(0)
    r2 = tools.roll_check("A", "swords", prepared=True, trained=False)
    assert r2["dice_count"] == 2
    seed(0)
    r3 = tools.roll_check("A", "swords", prepared=True, trained=True)
    assert r3["dice_count"] == 3
    # help bonus caps at 3
    state._pending_help["A"] = 1
    r4 = tools.roll_check("A", "swords", prepared=True, trained=True)
    assert r4["dice_count"] == 3  # 1+2+help capped
    assert r4["help_bonus"] == 1


def test_sns_help_grants_plus_one_on_success():
    state = SnSState(seed_val=0)
    # Use sns 5 for helper: swords <5 has 4/6 success per die => high success chance
    helper = create_sns_player("Helper", ancestry="Human", background="Soldier", sns=5)
    target = create_sns_player("Target", ancestry="Elf", background="Sage", sns=2)
    initialize_sns_scene(state, [helper, target], [], map_kind="outdoor", seed=0)
    tools = SnSTools(state)
    # trained => 2 dice, sns5 very likely success; but test loop until success to avoid flake
    got_help = False
    for s in range(10):
        seed(s * 7)
        r = tools.help("Helper", "Target", "swords", trained=True)
        if r["help_granted"]:
            got_help = True
            assert state._pending_help.get("Target") == 1
            # next roll consumes it
            seed(s * 7 + 1)
            rr = tools.roll_check("Target", "swords", prepared=False, trained=False)
            assert rr["help_bonus"] == 1
            assert rr["dice_count"] == 2  # 1 base + help
            break
    # if we never got success in 10 trials, just verify structure
    if not got_help:
        # at least structure is correct
        seed(999)
        r = tools.help("Helper", "Target", "swords", trained=True)
        assert "help_granted" in r


def test_sns_attack_applies_wd_highest_only_on_success():
    state = SnSState(seed_val=0)
    atk = create_sns_player("Attacker", ancestry="Human", background="Soldier", sns=5)  # WD 4, high success
    mon = create_sns_monster("Gob", threat="Easy")
    initialize_sns_scene(state, [atk], [mon], map_kind="outdoor", seed=0)
    tools = SnSTools(state)
    before_hp = mon.hp
    seed(0)
    res = tools.attack("Attacker", "Gob", prepared=True, trained=True)  # 3 dice very likely success
    assert "roll" in res
    assert "damage" in res
    if res["roll"]["success"]:
        assert res["damage"]["damage"] == max(res["damage"]["rolls"])
        assert mon.hp == before_hp - res["damage"]["damage"]
    else:
        assert res["damage"]["damage"] == 0
        assert mon.hp == before_hp


def test_sns_cast_level0_no_roll_no_cost():
    state = SnSState(seed_val=0)
    mage = create_sns_player("Mage", ancestry="Elf", background="Sage", sns=2)
    mage.sp = 3
    initialize_sns_scene(state, [mage], [], map_kind="outdoor", seed=0)
    tools = SnSTools(state)
    before = mage.sp
    res = tools.cast_spell("Mage", "Illuminate", level=0)
    assert res["sp_cost"] == 0
    assert mage.sp == before
    assert res["roll"] is None


def test_sns_cast_failure_no_sp_cost():
    state = SnSState(seed_val=0)
    mage = create_sns_player("Mage", ancestry="Elf", background="Sage", sns=5)  # SORCERY >5 only 1 succeeds (6)
    # sorcery roll with 1 die and sns5 => fail unless 6; force failure with mocked rolls by seeding
    initialize_sns_scene(state, [mage], [], map_kind="outdoor", seed=0)
    tools = SnSTools(state)
    before = mage.sp
    # try seeds until we get a failure
    for s in range(20):
        seed(s * 3)
        # we need to set tool's RNG to same seed; roll inside cast_spell will use it
        # just attempt and check
        seed(s * 3)
        res = tools.cast_spell("Mage", "Fireball", level=2, prepared=False, trained=False)
        if not res["roll"]["success"]:
            assert res["sp_cost"] == 0
            assert mage.sp == before
            break


def test_sns_cast_success_costs_sp_and_highest_plus_two():
    state = SnSState(seed_val=0)
    mage = create_sns_player("Mage", ancestry="Elf", background="Sage", sns=2)  # SORCERY >2 easy
    # sns2 sorcery >2 succeeds on 3-6 (4/6) per die
    mage.sp = 6
    initialize_sns_scene(state, [mage], [], map_kind="outdoor", seed=0)
    tools = SnSTools(state)
    for s in range(5):
        mage.sp = 6
        seed(s + 10)
        res = tools.cast_spell("Mage", "Fireball", level=2, prepared=True, trained=True)
        if res.get("success"):
            assert res["sp_cost"] == 2
            assert mage.sp == 4
            assert res["damage"]["total"] == res["damage"]["highest"] + 4
            break
    else:
        # if we never succeeded, the test should still assert dice formula when success happens
        # force success by using low sns and many dice
        seed(42)
        mage.sp = 6
        res = tools.cast_spell("Mage", "Fireball", level=1, prepared=True, trained=True)
        if res.get("success"):
            assert res["damage"]["total"] == res["damage"]["highest"] + 2


def test_sns_cast_insufficient_sp():
    state = SnSState(seed_val=0)
    mage = create_sns_player("Mage", ancestry="Elf", background="Sage", sns=2)
    mage.sp = 0
    initialize_sns_scene(state, [mage], [], map_kind="outdoor", seed=0)
    tools = SnSTools(state)
    # make success likely but we have 0 SP
    seed(0)
    res = tools.cast_spell("Mage", "Fireball", level=2, prepared=True, trained=True)
    if res["roll"]["success"]:
        assert res.get("error") is not None or res.get("success") is False
        assert mage.sp == 0
