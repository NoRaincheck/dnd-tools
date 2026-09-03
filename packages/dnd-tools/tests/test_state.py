from dnd_tools.models import Buff, Character
from dnd_tools.state import GameState


def _char(name: str = "Hero") -> Character:
    return Character(name=name, max_hp=10, hp=10, ac=12, strength=14, dexterity=12, constitution=12)


def test_add_player_and_get():
    gs = GameState(seed_val=0, map_w=10, map_h=10)
    c = _char("Aria")
    gs.add_player(c, (1, 1, 0))
    assert gs.get_character("Aria") is c
    assert gs.get_pos("Aria") == (1, 1, 0)


def test_update_hp_damage_and_heal():
    gs = GameState(seed_val=0)
    c = _char("Bob")
    gs.add_player(c, (0, 0, 0))
    gs.update_hp("Bob", -3)
    assert c.hp == 7
    gs.update_hp("Bob", 2)
    assert c.hp == 9
    # heal caps at max
    gs.update_hp("Bob", 10)
    assert c.hp == 10


def test_temp_hp_absorbs():
    gs = GameState(seed_val=0)
    c = _char("Temp")
    c.temp_hp = 5
    gs.add_player(c, (0, 0, 0))
    gs.update_hp("Temp", -7)
    # 5 absorbed, 2 to hp
    assert c.temp_hp == 0
    assert c.hp == 8
    assert c.alive is True


def test_death_log():
    gs = GameState(seed_val=0)
    c = _char("Doomed")
    c.hp = 1
    gs.add_player(c, (0, 0, 0))
    gs.update_hp("Doomed", -5)
    assert c.hp == 0
    assert c.alive is False
    assert any("Doomed" in s for s in gs.death_log)


def test_distance_feet():
    gs = GameState(seed_val=0, map_w=20, map_h=20)
    gs.add_player(_char("A"), (0, 0, 0))
    gs.add_player(_char("B"), (3, 4, 0))
    # 3-4-5 triangle *5 = 25 ft
    assert gs.distance_feet("A", "B") == 25.0


def test_line_of_sight_flat():
    gs = GameState(seed_val=0, map_w=5, map_h=5)
    gs.add_player(_char("A"), (0, 0, 0))
    gs.add_player(_char("B"), (4, 0, 0))
    assert gs.line_of_sight("A", "B") is True


def test_line_of_sight_blocked_by_height():
    gs = GameState(seed_val=0, map_w=5, map_h=5)
    gs.add_player(_char("A"), (0, 0, 0))
    gs.add_player(_char("B"), (4, 0, 0))
    gs.map[0][2].z = 2  # high wall in middle
    assert gs.line_of_sight("A", "B") is False


def test_initiative_deterministic():
    # GameState seeds a global RNG, so compare two independent seedings
    gs1 = GameState(seed_val=42)
    gs1.add_player(_char("P1"), (0, 0, 0))
    gs1.add_monster(_char("M1"), (1, 0, 0))
    r1 = gs1.roll_initiative()
    order1 = list(gs1.initiative_order)

    gs2 = GameState(seed_val=42)
    gs2.add_player(_char("P1"), (0, 0, 0))
    gs2.add_monster(_char("M1"), (1, 0, 0))
    r2 = gs2.roll_initiative()
    order2 = list(gs2.initiative_order)

    assert r1 == r2
    assert order1 == order2


def test_advance_turn_round():
    gs = GameState(seed_val=0)
    gs.add_player(_char("P1"), (0, 0, 0))
    gs.add_player(_char("P2"), (1, 0, 0))
    gs.roll_initiative()
    assert gs.round == 1
    gs.advance_turn()
    gs.advance_turn()
    # after 2 advances with 2 combatants, round should increment
    assert gs.round == 2


def test_buff_concentration_not_affected_by_state_directly():
    gs = GameState(seed_val=0)
    c = _char("C")
    c.buffs.append(Buff(name="blessed", remaining_turns=2, description="test"))
    gs.add_player(c, (0, 0, 0))
    assert len(c.buffs) == 1
