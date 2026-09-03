from pathlib import Path

from dnd_tools.models import Buff
from dnd_tools.simulation import create_player

from dnd_campaign.state import CampaignState


def test_snapshot_restore():
    cs = CampaignState(seed_val=10, map_w=10, map_h=10)
    p = create_player("Aria", "wizard")
    cs.inner.add_player(p, (2, 2, 0))
    snap = cs.snapshot()
    cs.inner.update_hp("Aria", -5)
    ch = cs.inner.get_character("Aria")
    assert ch is not None
    assert ch.hp == p.max_hp - 5
    cs.restore(snap)
    ch2 = cs.inner.get_character("Aria")
    assert ch2 is not None
    assert ch2.hp == p.max_hp


def test_save_load_roundtrip(tmp_path: Path):
    cs = CampaignState(seed_val=5)
    p = create_player("Boris", "fighter")
    cs.inner.add_player(p, (1, 1, 0))
    cs.inner.update_hp("Boris", -3)
    path = tmp_path / "save.json"
    cs.save(path)
    assert path.exists()
    cs2 = CampaignState.load(path)
    ch1 = cs.inner.get_character("Boris")
    ch2 = cs2.inner.get_character("Boris")
    assert ch1 is not None and ch2 is not None
    assert ch2.hp == ch1.hp
    assert cs2.round == cs.round


def test_long_rest_heals_and_restores_slots():
    cs = CampaignState(seed_val=0)
    p = create_player("Cleric", "cleric")
    # clerics get slots
    assert p.spell_slots
    cs.inner.add_player(p, (0, 0, 0))
    cs.inner.update_hp("Cleric", -5)
    p.spell_slots[1] = 0
    p.buffs.append(Buff(name="temp", remaining_turns=2, description="temp"))
    p.buffs.append(Buff(name="perm", remaining_turns=-1, description="perm"))
    cs.long_rest("Cleric")
    assert p.hp == p.max_hp
    assert p.spell_slots[1] == p.spell_slots_max[1]
    assert any(b.name == "perm" for b in p.buffs)
    assert not any(b.name == "temp" for b in p.buffs)


def test_long_rest_all_players():
    cs = CampaignState(seed_val=0)
    for name in ["P1", "P2"]:
        p = create_player(name, "fighter")
        cs.inner.add_player(p, (0, 0, 0))
        cs.inner.update_hp(name, -4)
    cs.long_rest()
    for name in ["P1", "P2"]:
        ch = cs.inner.get_character(name)
        assert ch is not None
        assert ch.hp == ch.max_hp


def test_short_rest_resets_speed():
    cs = CampaignState(seed_val=0)
    p = create_player("Ranger", "ranger")
    cs.inner.add_player(p, (0, 0, 0))
    p.speed_remaining = 5
    p.num_of_action = 0
    cs.short_rest("Ranger")
    assert p.speed_remaining == p.speed
    assert p.num_of_action == 1


def test_checkpoint_bounded_history():
    cs = CampaignState(seed_val=0, max_history=3)
    for _ in range(5):
        cs.checkpoint()
    assert len(cs.history) == 3


def test_prune_traces():
    cs = CampaignState(seed_val=0)
    p = create_player("P", "fighter")
    cs.inner.add_player(p, (0, 0, 0))
    for i in range(10):
        cs.inner.log_tool(f"tool{i}", {}, i)
        cs.inner.add_transcript(f"line {i}")
    cs.prune_traces(keep_last=3)
    assert len(cs.inner.tool_trace) == 3
    # transcript keeps head + tail (max 13 but >=3)
    assert len(cs.inner.transcript) <= 13


def test_snapshot_preserves_positions_and_map():
    cs = CampaignState(seed_val=42, map_w=8, map_h=8)
    p = create_player("PosTest", "rogue")
    cs.inner.add_player(p, (3, 4, 0))
    snap = cs.snapshot()
    cs.inner.set_pos("PosTest", (0, 0, 0))
    cs.restore(snap)
    assert cs.inner.get_pos("PosTest") == (3, 4, 0)
