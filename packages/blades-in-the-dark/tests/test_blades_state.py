from blades_in_the_dark.models import BladesCharacter
from blades_in_the_dark.simulation import create_blades_player
from blades_in_the_dark.state import BladesCampaignState, BladesState


def test_blades_state_snapshot_restore():
    s = BladesState(seed_val=42)
    p = create_blades_player("Silas", playbook="Lurk", actions={"Prowl": 2})
    s.add_player(p, (2, 2, 0))
    s.set_clock("Score Clock", 6, "obstacle")
    s.tick_clock("Score Clock", 2)
    # manually test BladesState via CampaignState snapshot pattern
    cstate = BladesCampaignState(seed_val=42)
    cstate.inner.add_player(create_blades_player("Locke", playbook="Spider", actions={"Consort": 2}), (1, 1, 0))
    cstate.inner.set_clock("Score", 6, "obstacle")
    cstate.inner.tick_clock("Score", 3)
    cstate.inner.crew.heat = 2
    cstate.inner.players["Locke"].stress = 4
    snap2 = cstate.snapshot()
    cstate2 = BladesCampaignState(seed_val=0)
    cstate2.restore(snap2)
    assert cstate2.inner.players["Locke"].stress == 4
    assert cstate2.inner.clocks["Score"].ticks == 3
    assert cstate2.inner.crew.heat == 2


def test_stress_trauma_flow():
    s = BladesState(seed_val=0)
    p = BladesCharacter(name="Vex", playbook="Cutter", actions={"Skirmish": 2}, stress=8)
    s.add_player(p, (0, 0, 0))
    # marking 2 more should overflow -> trauma
    from blades_in_the_dark.tools import BladesTools

    t = BladesTools(s)
    # push yourself will take 2 stress from 8 -> should trigger trauma
    res = t.push_yourself("Vex", bonus="dice")
    assert res["valid"]
    assert res.get("trauma_triggered") is True
    assert s.players["Vex"].stress == 0  # cleared
    assert len(s.players["Vex"].trauma) == 1
    # retirement at 4 traumas
    for tr in ["Haunted", "Obsessed", "Paranoid"]:
        s.add_trauma("Vex", tr)
    assert s.players["Vex"].retired is True
    assert not s.players["Vex"].alive


def test_harm_and_healing():
    s = BladesState(seed_val=0)
    p = create_blades_player("Thorn", playbook="Whisper", actions={"Attune": 2})
    s.add_player(p, (0, 0, 0))
    from blades_in_the_dark.tools import BladesTools

    t = BladesTools(s)
    r = t.apply_harm("Thorn", 2, "Cut to the Ribs")
    assert r["alive"] is True
    assert len(s.players["Thorn"].harm) == 1
    _ = t.apply_harm("Thorn", 4, "Fatal Stab")
    assert s.players["Thorn"].alive is False
    assert len(s.players["Thorn"].harm) == 2
    # heal
    _ = BladesTools(s)
    # but alive false still heals; we test heal on non-fatal
    s2 = BladesState(seed_val=0)
    p2 = create_blades_player("Thorn2", playbook="Whisper", actions={"Attune": 2})
    s2.add_player(p2, (0, 0, 0))
    t3 = BladesTools(s2)
    t3.apply_harm("Thorn2", 2, "Bruised")
    assert len(s2.players["Thorn2"].harm) == 1
    hr = t3.heal_harm("Thorn2", "Bruised")
    assert hr["valid"] is True
    assert len(s2.players["Thorn2"].harm) == 0


def test_campaign_save_load_roundtrip(tmp_path):
    cstate = BladesCampaignState(seed_val=7)
    cstate.inner.add_player(create_blades_player("Silas", playbook="Lurk", actions={"Prowl": 2}), (1, 1, 0))
    cstate.inner.set_clock("Score", 6, "obstacle")
    cstate.inner.tick_clock("Score", 2)
    cstate.checkpoint()
    p = tmp_path / "blades_campaign.json"
    cstate.save(p)
    loaded = BladesCampaignState.load(p)
    assert loaded.inner.clocks["Score"].ticks == 2
    assert loaded.inner.players["Silas"].playbook == "Lurk"
