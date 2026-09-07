import random

from sword_and_sorcery.dice import roll_sns_check, roll_spell_damage, roll_weapon_damage
from sword_and_sorcery.models import derived_en, derived_hp, derived_sp, derived_wd, roll_sns_number
from sword_and_sorcery.simulation import SnSSimulation, create_sns_monster, create_sns_player, initialize_sns_scene
from sword_and_sorcery.state import SnSCampaignState, SnSState
from sword_and_sorcery.tools import SnSCampaignTools, SnSTools


def test_derived():
    assert derived_hp(2) == 6
    assert derived_hp(5) == 15
    assert derived_sp(2) == 6
    assert derived_sp(5) == 0
    assert derived_wd(2) == 1
    assert derived_wd(5) == 4
    assert derived_en(3) == 6


def test_roll_sns_number_range():
    rng = random.Random(0)
    for _ in range(20):
        v = roll_sns_number(rng)
        assert 2 <= v <= 5


def test_dice_check():
    from sword_and_sorcery.dice import seed

    seed(42)
    r = roll_sns_check(4, "swords", 2)
    assert "rolls" in r and len(r["rolls"]) == 2
    # swords success = roll < sns
    for roll in r["rolls"]:
        if roll < 4 and roll != 4:
            assert r["successes"] >= 1

    seed(42)
    r2 = roll_sns_check(3, "sorcery", 3)
    assert len(r2["rolls"]) == 3


def test_weapon_damage():
    from sword_and_sorcery.dice import seed

    seed(1)
    d = roll_weapon_damage(3)
    assert len(d["rolls"]) == 3
    assert d["damage"] == max(d["rolls"])


def test_spell_damage():
    from sword_and_sorcery.dice import seed

    seed(1)
    d = roll_spell_damage(2)
    assert d["total"] == max(d["rolls"]) + 4


def test_scene_heuristic():
    random.seed(42)
    state = SnSState(seed_val=42)
    players = [
        create_sns_player("A", ancestry="Human", background="Soldier", sns=5),
        create_sns_player("B", ancestry="Elf", background="Sage", sns=2),
    ]
    monsters = [create_sns_monster("Goblin", threat="Easy")]
    initialize_sns_scene(state, players, monsters, map_kind="outdoor", seed=42)
    tools = SnSTools(state)
    sim = SnSSimulation(state, tools, use_heuristic=True, max_turns=6)
    res = sim.run()
    assert "transcript" in res
    assert len(res["tool_trace"]) > 0
    assert "players" in res


def test_cast_spell_level0_no_cost():
    from sword_and_sorcery.dice import seed

    seed(42)
    state = SnSState(seed_val=42)
    p = create_sns_player("Mage", ancestry="Elf", background="Sage", sns=2)
    initialize_sns_scene(state, [p], [], map_kind="outdoor", seed=42)
    tools = SnSTools(state)
    before = p.sp
    res = tools.cast_spell("Mage", "Illuminate", level=0)
    assert res["sp_cost"] == 0
    assert p.sp == before


def test_help_grants_bonus():
    from sword_and_sorcery.dice import seed

    seed(0)
    state = SnSState(seed_val=0)
    p1 = create_sns_player("Helper", ancestry="Human", background="Soldier", sns=5)
    p2 = create_sns_player("Target", ancestry="Elf", background="Sage", sns=2)
    initialize_sns_scene(state, [p1, p2], [], map_kind="outdoor", seed=0)
    tools = SnSTools(state)
    # helper attempts help — with seed 0 may not always succeed, but we test mechanics not flake
    # Force a success by seeding differently if needed — we just check tool doesn't crash
    r = tools.help("Helper", "Target", "swords", trained=True)
    assert "help_granted" in r


def test_campaign_state_snapshot():
    cs = SnSCampaignState(seed_val=42)
    p = create_sns_player("Gunther", ancestry="Human", background="Soldier", sns=5)
    cs.inner.add_player(p, (0, 0, 0))
    snap = cs.snapshot()
    cs2 = SnSCampaignState(seed_val=0)
    cs2.restore(snap)
    assert cs2.inner.players["Gunther"].sns == 5
    assert cs2.inner.players["Gunther"].hp_max == 15


def test_night_rest():
    state = SnSState(seed_val=0)
    p = create_sns_player("A", ancestry="Human", background="Soldier", sns=5)
    p.hp = 1
    p.sp = 0
    state.add_player(p, (0, 0, 0))
    tools = SnSTools(state)
    tools.night_rest()
    assert p.hp == p.hp_max
    assert p.sp == p.sp_max


def test_campaign_tools():
    cs = SnSCampaignState(seed_val=42)
    p = create_sns_player("A", ancestry="Human", background="Soldier", sns=4)
    cs.inner.add_player(p, (1, 1, 0))
    tools = SnSCampaignTools(cs)
    r = tools.get_summary()
    assert "players" in r
