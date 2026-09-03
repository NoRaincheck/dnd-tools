from dnd_tools.simulation import create_player

from dnd_campaign.memory import compact_transcript, summarize_state
from dnd_campaign.state import CampaignState


def test_summarize_state():
    cs = CampaignState(seed_val=0)
    p = create_player("Hero", "fighter")
    cs.inner.add_player(p, (1, 2, 0))
    s = summarize_state(cs)
    assert s["round"] == 1
    assert "Hero" in s["players"]
    assert s["players"]["Hero"]["hp"] == p.hp
    assert "meta" in s


def test_compact_transcript_short():
    cs = CampaignState(seed_val=0)
    for i in range(5):
        cs.inner.add_transcript(f"line {i}")
    out = compact_transcript(cs, keep_last=10)
    assert "line 0" in out
    assert "line 4" in out
    assert "omitted" not in out


def test_compact_transcript_long():
    cs = CampaignState(seed_val=0)
    for i in range(100):
        cs.inner.add_transcript(f"line {i}")
    out = compact_transcript(cs, keep_last=10)
    assert "omitted" in out
    assert "line 99" in out
    assert "line 0" in out
