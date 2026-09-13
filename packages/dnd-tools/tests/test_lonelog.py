"""Lonelog notation tests — emit/parse/render + hard-switch assertions."""

from dnd_tools.lonelog import (
    aftermath,
    attack_sequence,
    consequence,
    encounter_snapshot,
    parse,
    render_html,
    round_marker,
    scene_header,
    to_markdown,
)
from dnd_tools.metrics import evaluate_all
from dnd_tools.simulation import Simulation, create_monster, create_player, initialize_encounter
from dnd_tools.state import GameState
from dnd_tools.tools import Tools

LEGACY_TOKENS = ("<End Turn/>", "<DM/>", "<Call/>", "--- Monster Turn", "--- Player Turn")


def test_attack_sequence_uses_core_symbols():
    lines = attack_sequence(
        "Goblin 1",
        "Mira",
        "club",
        roll=13,
        ac=12,
        hit=True,
        damage=5,
        damage_type="slashing",
        target_hp=3,
        target_max=8,
        target_is_pc=True,
    )
    assert lines[0].startswith("@(Goblin 1)")
    assert lines[1].startswith("d:")
    assert "-> Hit" in lines[1]
    assert lines[2].startswith("=>")
    assert "[PC:Mira|HP 3/8]" in lines[2]


def test_scene_and_round_markers():
    assert scene_header(1, "Encounter opens").startswith("S1 ")
    assert "[COMBAT]" in scene_header(1, "x")
    assert round_marker(2) == "Rd2"
    assert "Init:" in round_marker(1, [{"name": "A", "initiative": 18}])
    snap = encounter_snapshot({"Mira": {"hp": 3, "max_hp": 8, "ac": 12}}, {"Gob": {"hp": 7, "max_hp": 7}})
    assert "[PC:Mira|HP 3/8|AC 12]" in snap
    assert "[F:Gob|HP 7/7|Close]" in snap


def test_parse_roundtrip():
    lines = [
        "S1 *Encounter opens* [COMBAT]",
        "Rd1 (Init: A 18, B 12)",
        "@(Gob) Attack Mira with club",
        "d: d20+1=13 vs AC 12 -> Hit",
        "=> 5 dmg (slashing) to Mira. [PC:Mira|HP 3/8]",
        "[/COMBAT]",
        "=> Combat ends. [Thread:Gob|Closed]",
    ]
    kinds = [e.kind for e in parse(lines)]
    assert kinds == ["scene", "round", "action", "roll", "consequence", "combat_close", "consequence"]
    assert parse(lines)[2].actor == "Gob"
    assert parse(lines)[1].round == 1


def test_render_html_self_contained():
    html = render_html(["S1 *x* [COMBAT]", "Rd1", "@(A) Attack B", "=> done. [F:B|dead]"], title="T")
    assert "<style>" in html and "<script>" in html
    assert 'src="http' not in html  # file:// friendly, no external fetches
    assert "lonelog-data" in html
    assert "[F:B|dead]" in html


def test_to_markdown_fences():
    md = to_markdown(["@(A) hi"], title="Demo")
    assert md.startswith("# Demo") and "```lonelog" in md


def test_simulation_transcript_is_lonelog():
    gs = GameState(seed_val=42)
    initialize_encounter(gs, [create_player("Hero", "fighter")], [create_monster("Gob", "goblin")], seed=42)
    res = Simulation(gs, Tools(gs), use_heuristic=True, max_turns=5).run()
    text = "\n".join(res["transcript"])
    for tok in LEGACY_TOKENS:
        assert tok not in text, tok
    assert res["transcript"][0].startswith("S1 ")
    assert any(l.startswith("Rd1") for l in res["transcript"])
    assert any(l.startswith("@(") for l in res["transcript"])
    assert any(l.startswith("d:") for l in res["transcript"])
    assert any(l.startswith("=>") for l in res["transcript"])
    assert res["transcript"][-2] == "[/COMBAT]"
    for entry in res["death"]["log"]:
        assert entry.startswith("=>")


def test_metrics_accept_lonelog():
    gs = GameState(seed_val=1)
    initialize_encounter(gs, [create_player("P", "fighter")], [create_monster("G", "goblin")], seed=1)
    res = Simulation(gs, Tools(gs), use_heuristic=True, max_turns=4).run()
    m = evaluate_all(res["transcript"], res["tool_trace"])
    assert 0 <= m["tactical_optimality"]["O"] <= 1
    assert 0 <= m["acting_quality"]["A"] <= 1


def test_aftermath_block():
    lines = aftermath("Combat ends. Party 1 up.", "[PC:A|HP 1/8]")
    assert lines[0] == "[/COMBAT]"
    assert lines[1].startswith("=>")
    assert consequence("x").startswith("=>")
