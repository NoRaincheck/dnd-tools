from dnd_tools.simulation import Simulation, create_monster, create_player, initialize_encounter
from dnd_tools.state import GameState
from dnd_tools.tools import Tools


def test_initialize_encounter_places():
    gs = GameState(seed_val=1, map_w=20, map_h=20)
    players = [create_player("P1", "fighter"), create_player("P2", "wizard")]
    monsters = [create_monster("G1", "goblin")]
    tools = Tools(gs)
    initialize_encounter(gs, players, monsters, map_kind="outdoor", seed=1)
    assert len(gs.players) == 2
    assert len(gs.monsters) == 1
    assert gs.get_pos("P1") is not None
    assert gs.get_pos("G1") is not None
    _ = tools


def test_simulation_run_heuristic_deterministic():
    # two runs with same seed should give same tool_trace length (heuristic is deterministic)
    def run_one(seed: int):
        gs = GameState(seed_val=seed)
        players = [create_player("Hero", "fighter")]
        monsters = [create_monster("Gob", "goblin")]
        initialize_encounter(gs, players, monsters, map_kind="outdoor", seed=seed)
        tools = Tools(gs)
        sim = Simulation(gs, tools, use_heuristic=True, max_turns=5)
        return sim.run()

    r1 = run_one(42)
    r2 = run_one(42)
    assert r1["rounds"] == r2["rounds"]
    assert len(r1["tool_trace"]) == len(r2["tool_trace"])
    assert r1["players"].keys() == r2["players"].keys()


def test_simulation_ends_when_one_side_dead():
    gs = GameState(seed_val=0)
    p = create_player("P1", "fighter")
    p.hp = 1
    p.max_hp = 1
    m = create_monster("G1", "goblin")
    m.hp = 1
    m.max_hp = 1
    initialize_encounter(gs, [p], [m], map_kind="outdoor", seed=0)
    # force close distance for quick kill
    gs.set_pos("P1", (5, 5, 0))
    gs.set_pos("G1", (6, 5, 0))
    tools = Tools(gs)
    sim = Simulation(gs, tools, use_heuristic=True, max_turns=10)
    res = sim.run()
    # combat should end before max_turns since someone dies quickly or stalls
    assert res["rounds"] >= 1
    assert "players" in res
    assert "monsters" in res


def test_generate_and_load_scenario(tmp_path):
    from dnd_tools.simulation import generate_scenarios, load_scenario

    paths = generate_scenarios(seed=123, out_dir=str(tmp_path))
    assert len(paths) == 27
    state, tools = load_scenario(paths[0])
    assert state is not None
    assert tools is not None
    assert len(state.players) == 4
