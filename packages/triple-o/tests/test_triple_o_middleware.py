from triple_o.core import TripleO
from triple_o.middleware import TripleOMiddleware
from triple_o.tools import TripleOTools


def test_middleware_heuristic():
    engine = TripleO(seed=42)
    mw = TripleOMiddleware(engine, TripleOTools(engine))
    out = mw.run_heuristic(
        player_name="Lyra",
        traits=["reckless", "keen"],
        situation="gate ambush",
        obvious="snipe from roof",
        option="flank",
        odd="charge shouting",
    )
    assert out["roll"]["category"] in ("obvious", "option", "odd")
    assert out["roll"]["choice"] in ("snipe from roof", "flank", "charge shouting")
    assert "text" in out and len(out["text"]) > 10
    assert "spark" in out


def test_middleware_heuristic_deterministic():
    e1 = TripleO(seed=123)
    mw1 = TripleOMiddleware(e1, TripleOTools(e1))
    o1 = mw1.run_heuristic(player_name="A", traits="brave", situation="s", obvious="obv", option="opt", odd="odd")
    e2 = TripleO(seed=123)
    mw2 = TripleOMiddleware(e2, TripleOTools(e2))
    o2 = mw2.run_heuristic(player_name="A", traits="brave", situation="s", obvious="obv", option="opt", odd="odd")
    assert o1["roll"]["roll"] == o2["roll"]["roll"]
    assert o1["roll"]["choice"] == o2["roll"]["choice"]


def test_middleware_system_prompt():
    assert "Triple-O" in TripleOMiddleware.SYSTEM_PROMPT
