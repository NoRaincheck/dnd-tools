from pathlib import Path

from tricube.session import TricubeSession
from tricube.simulation import TricubeSimulation, create_tricube_player, initialize_tricube_scene
from tricube.state import TricubeCampaignState, TricubeState
from tricube.tools import TricubeCampaignTools, TricubeTools


def test_single_scene_heuristic():
    s = TricubeState(seed_val=1)
    players = [
        create_tricube_player("A", trait="brawny", concept="knight"),
        create_tricube_player("B", trait="crafty", concept="mage"),
    ]
    from tricube.simulation import create_tricube_monster

    monsters = [create_tricube_monster("Gob", trait="agile", concept="goblin", rank=1)]
    initialize_tricube_scene(s, players, monsters, map_kind="outdoor", seed=1)
    tools = TricubeTools(s)
    sim = TricubeSimulation(s, tools, use_heuristic=True, max_turns=8)
    res = sim.run()
    assert "transcript" in res
    assert "tool_trace" in res
    assert len(res["transcript"]) > 0


def test_campaign_two_scenes_with_context(tmp_path: Path):
    cs = TricubeCampaignState(seed_val=42)
    # seed players
    for name, trait, concept in [("Lyra", "agile", "ranger"), ("Borin", "brawny", "knight")]:
        cs.inner.add_player(create_tricube_player(name, trait=trait, concept=concept), (0, 0, 0))
    ctools = TricubeCampaignTools(cs)
    sess = TricubeSession(cs, ctools)
    scenes = [
        {"monsters": [("Gob1", "agile", 1, False), ("Gob2", "agile", 1, False)], "map": "outdoor"},
        {"monsters": [("Ogre", "brawny", 2, False)], "map": "indoor"},
    ]
    results = sess.run_campaign(scenes, max_turns_per_scene=10)
    assert len(results) == 2
    # history should have at least 2 checkpoints + scenes
    assert len(cs.history) >= 2
    # summary via tool
    summary = ctools.get_summary()
    assert "players" in summary
    # persistence
    path = tmp_path / "camp.json"
    cs.save(path)
    cs2 = TricubeCampaignState.load(path)
    assert cs2.campaign_meta["scenes"] == cs.campaign_meta["scenes"]


def test_campaign_long_rest_between_scenes():
    cs = TricubeCampaignState(seed_val=0)
    p = create_tricube_player("Mira", trait="crafty", concept="mage")
    cs.inner.add_player(p, (0, 0, 0))
    # give affliction
    cs.inner.update_resolve("Mira", -3)
    before = len(p.afflictions)
    assert before == 1
    sess = TricubeSession(cs)
    # run campaign with long rest between
    scenes = [
        {"monsters": [("Gob", "agile", 1, False)], "map": "outdoor"},
        {"monsters": [("Wolf", "brawny", 1, False)], "map": "outdoor"},
    ]
    sess.run_campaign(scenes, max_turns_per_scene=5)
    # after campaign, afflictions from first scene should be cleared via long_rest (scene recovery)
    assert len(p.afflictions) == 0 or p.afflictions[0].recovery != "scene"
