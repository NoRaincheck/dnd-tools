from dnd_tools.simulation import create_player

from dnd_campaign.session import CampaignSession
from dnd_campaign.state import CampaignState
from dnd_campaign.tools import CampaignTools


def test_add_encounter_and_run():
    cs = CampaignState(seed_val=1)
    for p in [create_player("P1", "fighter"), create_player("P2", "wizard")]:
        cs.inner.add_player(p, (0, 0, 0))
    ct = CampaignTools(cs)
    sess = CampaignSession(cs, ct)
    sess.add_encounter(monster_specs=["goblin", "goblin"], map_kind="outdoor")
    assert len(cs.inner.monsters) == 2
    res = sess.run_encounter(max_turns=4)
    assert "transcript" in res
    assert "tool_trace" in res


def test_run_campaign_two_encounters():
    cs = CampaignState(seed_val=2)
    for p in [create_player("A", "fighter"), create_player("B", "cleric")]:
        cs.inner.add_player(p, (0, 0, 0))
    ct = CampaignTools(cs)
    sess = CampaignSession(cs, ct)
    encounters = [
        {"monsters": ["goblin"], "map": "outdoor"},
        {"monsters": ["wolf"], "map": "indoor"},
    ]
    results = sess.run_campaign(encounters, max_turns_per_encounter=3)
    assert len(results) == 2
    # after campaign, history should have at least 2 checkpoints + rests
    assert len(cs.history) >= 2


def test_isolation_from_paper_state():
    # campaign and paper states are independent
    from dnd_tools.state import GameState

    paper_gs = GameState(seed_val=0)
    paper_gs.add_player(create_player("PaperHero", "fighter"), (0, 0, 0))
    cs = CampaignState(seed_val=99)
    cs.inner.add_player(create_player("CampHero", "fighter"), (0, 0, 0))
    # mutating campaign should not affect paper
    cs.inner.update_hp("CampHero", -5)
    p1 = paper_gs.get_character("PaperHero")
    p2 = cs.inner.get_character("CampHero")
    assert p1 is not None and p2 is not None
    assert p1.hp == p1.max_hp
    assert p2.hp != p1.hp


def test_session_respects_max_history():
    cs = CampaignState(seed_val=0, max_history=2)
    for p in [create_player("P1", "fighter")]:
        cs.inner.add_player(p, (0, 0, 0))
    ct = CampaignTools(cs)
    sess = CampaignSession(cs, ct)
    for _ in range(5):
        sess.add_encounter(monster_specs=["goblin"], map_kind="outdoor")
    assert len(cs.history) == 2
