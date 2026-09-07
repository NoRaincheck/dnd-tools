from triple_o.core import TripleO
from triple_o.tools import TripleOTools


def _tools(seed=0):
    return TripleOTools(TripleO(seed=seed))


def test_propose_then_roll():
    t = _tools(seed=42)
    prop = t.propose_triple_o("Lyra", "ambush", obvious="snipe", option="flank", odd="charge", traits=["reckless"])
    assert "pending" in prop
    # roll reuses pending
    res = t.roll_triple_o(character="Lyra")
    assert res["category"] in ("obvious", "option", "odd")
    assert res["choice"] in ("snipe", "flank", "charge")
    assert t.tool_trace[-1]["tool"] == "roll_triple_o"


def test_inline_roll():
    t = _tools(seed=10)
    res = t.roll_triple_o(obvious="A", option="B", odd="C", situation="test", character="Bob")
    assert res["choice"] in ("A", "B", "C")


def test_double_down_via_tools():
    t = _tools(seed=0)
    t.propose_triple_o("A", "s", obvious="obv", option="opt", odd="od")
    res = t.roll_triple_o(advantage="advantage")
    assert len(res["rolls"]) == 2
    assert res["advantage"] == "advantage"
    # disadvantage
    t2 = _tools(seed=0)
    t2.propose_triple_o("A", "s", obvious="obv", option="opt", odd="od")
    res2 = t2.roll_triple_o(advantage="disadvantage")
    assert res2["advantage"] == "disadvantage"


def test_group_and_ask():
    t = _tools(seed=42)
    g = t.group_triple_o(["brave", "cautious", "reckless"], ["hold", "talk", "flee"])
    assert g["choice"] in ["hold", "talk", "flee"]
    q = t.ask_triple_o("Do they search for traps?")
    assert "answer" in q
    assert q["category"] in ("obvious", "option", "odd")


def test_spark():
    t = _tools(seed=1)
    s = t.spark_roll()
    assert "disposition" in s and "action" in s
    d = t.spark_disposition()
    assert "disposition" in d
    a = t.spark_action()
    assert "action" in a


def test_tool_schemas():
    t = _tools()
    schemas = t.tool_schemas()
    names = {s["function"]["name"] for s in schemas}
    assert "propose_triple_o" in names
    assert "roll_triple_o" in names
    assert "spark_roll" in names
    assert "group_triple_o" in names
    assert "ask_triple_o" in names
    assert len(schemas) >= 6


def test_dispatch_error():
    t = _tools()
    try:
        t.dispatch("unknown", {})
        assert False
    except ValueError:
        pass
