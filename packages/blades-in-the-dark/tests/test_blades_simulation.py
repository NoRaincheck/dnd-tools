from blades_in_the_dark.simulation import BladesSimulation, create_blades_player, initialize_blades_score
from blades_in_the_dark.state import BladesCampaignState, BladesState
from blades_in_the_dark.tools import BladesTools


def test_blades_simulation_heuristic_completes():
    s = BladesState(seed_val=42)
    players = [
        create_blades_player("Silas", playbook="Lurk", actions={"Prowl": 2}),
        create_blades_player("Locke", playbook="Spider", actions={"Consort": 2}),
    ]
    initialize_blades_score(s, players, clocks=[("Score Clock", 6, "obstacle")])
    tools = BladesTools(s)
    sim = BladesSimulation(s, tools, use_heuristic=True, max_turns=8)
    result = sim.run()
    assert "transcript" in result
    assert "clocks" in result
    assert len(result["tool_trace"]) > 5
    # at least some ticks should have occurred
    assert result["clocks"]["Score Clock"]["ticks"] >= 0


def test_blades_campaign_session():
    from blades_in_the_dark.session import BladesSession
    from blades_in_the_dark.tools import BladesCampaignTools

    cstate = BladesCampaignState(seed_val=42)
    for name, pb in [("Silas", "Lurk"), ("Locke", "Spider")]:
        cstate.inner.add_player(create_blades_player(name, playbook=pb, actions={"Prowl": 2}), (0, 0, 0))
    ctools = BladesCampaignTools(cstate)
    sess = BladesSession(cstate, ctools)
    scores = [
        {"plan": "infiltration", "detail": "canal", "clocks": [("Infiltrate", 4, "obstacle")]},
        {"plan": "deception", "detail": "disguise", "clocks": [("Ledger", 4, "obstacle")]},
    ]
    results = sess.run_campaign(scores, max_turns_per_score=6, use_heuristic=True)
    assert len(results) == 2
    assert cstate.campaign_meta["scores"] == 2
    # summary via tool
    summary = ctools.get_summary()
    assert "players" in summary
    assert "clocks" in summary
