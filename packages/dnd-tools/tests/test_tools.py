from dnd_tools.models import Character
from dnd_tools.state import GameState
from dnd_tools.tools import Tools


def _setup() -> tuple[GameState, Tools]:
    gs = GameState(seed_val=0, map_w=10, map_h=10)
    p = Character(name="Hero", max_hp=10, hp=10, ac=12, strength=14, dexterity=14)
    p.equipped_mainhand = "longsword"
    m = Character(name="Gob", max_hp=7, hp=7, ac=13, strength=10, dexterity=14)
    m.equipped_mainhand = "club"
    gs.add_player(p, (1, 1, 0))
    gs.add_monster(m, (2, 1, 0))
    return gs, Tools(gs)


def test_check_hp_logs_tool_trace():
    gs, tools = _setup()
    hp = tools.check_hp("Hero")
    assert hp == 10
    assert gs.tool_trace[-1]["tool"] == "check_hp"


def test_move_valid_and_speed():
    gs, tools = _setup()
    res = tools.move_player("Hero", 2, 1)
    assert res["valid"] is True
    assert gs.get_pos("Hero") == (2, 1, 0)
    # speed decreases (diagonal simplified to Chebyshev)
    ch = gs.get_character("Hero")
    assert ch is not None
    assert ch.speed_remaining < 30


def test_move_out_of_bounds():
    _gs, tools = _setup()
    res = tools.move_player("Hero", 99, 99)
    assert res["valid"] is False
    assert "bounds" in res["reason"]


def test_move_impassable():
    gs, tools = _setup()
    gs.map[3][3].valid = False
    res = tools.move_player("Hero", 3, 3)
    assert res["valid"] is False


def test_roll_attack_out_of_range_melee():
    gs, tools = _setup()
    # move hero far away
    gs.set_pos("Hero", (0, 0, 0))
    gs.set_pos("Gob", (9, 9, 0))
    res = tools.roll_attack("Hero", "Gob", weapon_name="longsword", action_cost=1)
    assert res["out_of_range"] is True
    assert res["valid"] is True


def test_roll_attack_economy_insufficient():
    _gs, tools = _setup()
    hero = tools.state.get_character("Hero")
    assert hero is not None
    hero.num_of_action = 0
    res = tools.roll_attack("Hero", "Gob", weapon_name="longsword", action_cost=1)
    assert res["valid"] is False
    assert "economy" in res["reason"]


def test_check_resources():
    _gs, tools = _setup()
    r = tools.check_resources("Hero")
    assert r["action"] == 1
    assert r["speed_remaining"] == 30


def test_tool_schemas_count():
    _gs, tools = _setup()
    schemas = tools.tool_schemas()
    assert len(schemas) >= 30
    names = {s["function"]["name"] for s in schemas}
    assert "roll_attack" in names
    assert "visualize_map" in names


def test_dash_consumes_action():
    _gs, tools = _setup()
    hero = tools.state.get_character("Hero")
    assert hero is not None
    before = hero.speed_remaining
    res = tools.dash("Hero")
    assert res["valid"] is True
    assert hero.speed_remaining == before + hero.speed
    assert hero.num_of_action == 0
