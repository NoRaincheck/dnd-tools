"""Triple-O lonelog rendering tests."""

from triple_o.core import TripleO, to_lonelog


def test_resolve_to_lonelog():
    e = TripleO(seed=42)
    p = e.propose("Lyra", "ambush at gate", "snipe", "flank", "charge", traits=["keen eye"])
    out = e.resolve(p)
    lines = to_lonelog(out)
    assert lines[0].startswith("? ambush at gate")
    assert any(l.startswith("d: d6=") and "->" in l for l in lines)
    assert lines[-1].startswith("=> @(")


def test_question_to_lonelog():
    e = TripleO(seed=7)
    q = e.question("Do they search for traps?", yes_is_obvious=True)
    lines = to_lonelog(q)
    assert lines[0] == "? Do they search for traps?"
    assert lines[1].startswith("d: d6=") and "->" in lines[1]
    assert lines[2].startswith("=>")


def test_group_to_lonelog():
    e = TripleO(seed=3)
    g = e.group_resolve(["brave"], ["hold", "negotiate", "flee"])
    lines = to_lonelog(g)
    assert lines[0].startswith("?")
    assert lines[1].startswith("d: d6=") and "->" in lines[1]
    assert lines[2].startswith("=>")
