from dnd_tools.simulation import create_player

from dnd_campaign.state import CampaignState
from dnd_campaign.tools import CampaignTools


def _cs_with_player() -> tuple[CampaignState, CampaignTools]:
    cs = CampaignState(seed_val=0, map_w=10, map_h=10)
    p = create_player("Hero", "fighter")
    cs.inner.add_player(p, (1, 1, 0))
    ct = CampaignTools(cs)
    return cs, ct


def test_delegation_check_hp():
    cs, ct = _cs_with_player()
    hp = ct.check_hp("Hero")
    ch = cs.inner.get_character("Hero")
    assert ch is not None
    assert hp == ch.hp
    assert cs.inner.tool_trace[-1]["tool"] == "check_hp"


def test_delegation_move_player():
    cs, ct = _cs_with_player()
    res = ct.move_player("Hero", 2, 2)
    assert res["valid"] is True
    assert cs.inner.get_pos("Hero") == (2, 2, 0)


def test_long_rest_via_tools():
    cs, ct = _cs_with_player()
    cs.inner.update_hp("Hero", -5)
    res = ct.long_rest(name="Hero")
    ch = cs.inner.get_character("Hero")
    assert ch is not None
    assert res["Hero"]["hp"] == ch.max_hp
    assert any(t["tool"] == "long_rest" for t in cs.inner.tool_trace)


def test_tool_schemas_includes_campaign():
    _cs, ct = _cs_with_player()
    schemas = ct.tool_schemas()
    names = {s["function"]["name"] for s in schemas}
    assert "long_rest" in names
    assert "short_rest" in names
    assert "get_summary" in names
    assert "roll_attack" in names  # from base Tools
    assert len(schemas) >= 36  # 30 base + 6 campaign


def test_dispatch_campaign_and_base():
    cs, ct = _cs_with_player()
    # base tool via dispatch
    hp = ct.dispatch("check_hp", {"name": "Hero"})
    ch = cs.inner.get_character("Hero")
    assert ch is not None
    assert hp == ch.hp
    # campaign tool via dispatch
    s = ct.dispatch("get_summary", {})
    assert "players" in s
    assert "round" in s


def test_checkpoint_and_save(tmp_path):
    _cs, ct = _cs_with_player()
    res = ct.checkpoint()
    assert res["history_len"] == 1
    p = tmp_path / "chk.json"
    res2 = ct.save_checkpoint(path=str(p))
    assert p.exists()
    assert "path" in res2


def test_prune_traces_via_tools():
    cs, ct = _cs_with_player()
    for i in range(5):
        cs.inner.log_tool(f"t{i}", {}, i)
    res = ct.prune_traces(keep_last=2)
    assert res["tool_trace_len"] == 2 or res["tool_trace_len"] == 3  # includes prune log
