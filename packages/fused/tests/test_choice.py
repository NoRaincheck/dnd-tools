import tempfile
from pathlib import Path

from fused.choice import ChoiceResolver, assess_trivial
from fused.models import Scene
from fused.state import FusedState


def test_assess_trivial_gate_boundaries():
    # controlled+limited always trivial (even with threat, even with high-stakes keyword unless limited exempt)
    trivial, reason = assess_trivial("controlled", "limited", "arrange camp", scene_threat="goblin")
    assert trivial is True and "position=controlled" in reason
    # limited stays trivial even with high-stakes keyword (ambush) because eff==limited exempt from override
    trivial, _ = assess_trivial("controlled", "limited", "ambush at camp trivial", scene_threat="goblin")
    assert trivial is True

    # controlled+standard+none threat => trivial
    trivial, reason = assess_trivial("controlled", "standard", "mend cloak", scene_threat="none")
    assert trivial is True and "no threat" in reason

    # controlled+standard+goblin threat without explicit tag => not trivial
    trivial, _ = assess_trivial("controlled", "standard", "mend cloak", scene_threat="goblin")
    assert trivial is False

    # controlled+standard+explicit trivial tag overrides threat => trivial (but high-stakes overrides)
    trivial, reason = assess_trivial("controlled", "standard", "trivial: mend cloak", scene_threat="goblin")
    assert trivial is True and "explicit trivial tag" in reason

    # controlled+standard+explicit trivial + high-stakes keyword => not trivial (high-stakes overrides for non-limited)
    trivial, reason = assess_trivial("controlled", "standard", "trivial ambush cloak", scene_threat="none")
    assert trivial is False

    # risky+limited => not trivial (position not controlled)
    trivial, _ = assess_trivial("risky", "limited", "trivial: arrange camp", scene_threat="none")
    assert trivial is False

    # controlled+great never trivial via primary gate (great not in TRIVIAL_EFFECTS)
    trivial, _ = assess_trivial("controlled", "great", "do great thing", scene_threat="none")
    assert trivial is False
    # but explicit tag + controlled via fallback makes great trivial (fallback path)
    trivial, _ = assess_trivial("controlled", "great", "trivial great feat", scene_threat="goblin")
    assert trivial is True

    # zero effect with controlled+none => trivial
    trivial, _ = assess_trivial("controlled", "zero", "trivial zero", scene_threat="none")
    assert trivial is True

    # fallback explicit trivial even if not in TRIVIAL_EFFECTS via fallback is covered above; without controlled fails
    trivial, _ = assess_trivial("risky", "great", "trivial great", scene_threat="none")
    assert trivial is False


def test_choice_resolver_say_yes_vs_rolled_and_ticks():
    # say_yes path: controlled+limited trivial
    r = ChoiceResolver(seed=42)
    c = r.propose(
        "s1-choice-0000",
        "s1",
        "A",
        "trivial: arrange camp low risk",
        "Refill",
        "Opt",
        "Odd",
        position="controlled",
        effect="limited",
    )
    r.resolve(c, scene_threat="none")
    assert c.trivial is True
    assert c.resolved_via == "say_yes"
    assert c.category == "obvious"
    assert c.choice_text == "Refill"
    assert c.ticks == 1
    assert c.roll is None
    assert c.rolls == []

    # rolled path: risky+standard with seed 42 should be deterministic
    r2 = ChoiceResolver(seed=42)
    c2 = r2.propose(
        "s1-choice-0001",
        "s1",
        "A",
        "Goblin horde blocks gate",
        "Charge",
        "Sneak",
        "Kick wall",
        position="risky",
        effect="standard",
    )
    r2.resolve(c2, scene_threat="goblin")
    assert c2.trivial is False
    assert c2.resolved_via == "rolled"
    assert c2.category in ("obvious", "option", "odd")
    assert c2.roll is not None
    assert c2.choice_text in ("Charge", "Sneak", "Kick wall")
    # ticks via EFFECT_TICKS: standard -> 2, odd+great would be +1 but we use standard
    assert c2.ticks == 2

    # odd category should still have ticks but live should not tick clock (tested in integration below)
    # force odd by manipulating resolver or using seed search: seed 1 gives odd for first roll?
    # Instead test that odd ticks are still computed but choice.ticks remains 2 (not 0)
    # We verify the rule that state skips tick on odd, not resolver
    # Here we just check resolver still assigns ticks for odd
    # find a seed that yields odd on first roll by brute
    from triple_o.core import TripleO

    found = None
    for s in range(100):
        t = TripleO(seed=s)
        rr = t.roll()
        if rr.category == "odd":
            found = s
            break
    assert found is not None
    r_odd = ChoiceResolver(seed=found)
    c_odd = r_odd.propose(
        "s1-choice-odd", "s1", "A", "risky odd test", "Obv", "Opt", "OddText", position="risky", effect="great"
    )
    r_odd.resolve(c_odd, scene_threat="goblin")
    if c_odd.category == "odd":
        # odd+great => base 3 +1 =4
        assert c_odd.ticks == 4
    # force_roll overrides trivial
    r4 = ChoiceResolver(seed=42)
    c4 = r4.propose(
        "s1-choice-force",
        "s1",
        "A",
        "trivial: arrange camp",
        "Refill",
        "Opt",
        "Odd",
        position="controlled",
        effect="limited",
    )
    r4.resolve(c4, scene_threat="none", force_roll=True)
    assert c4.trivial is False
    assert c4.resolved_via == "rolled"
    assert c4.roll is not None

    # advantage path
    r5 = ChoiceResolver(seed=42)
    c5 = r5.propose(
        "s1-choice-adv", "s1", "A", "risky combat", "Obv", "Opt", "Odd", position="risky", effect="standard"
    )
    r5.resolve(c5, scene_threat="goblin", advantage="advantage")
    assert c5.payload.get("advantage") == "advantage"
    assert len(c5.rolls) == 2


def test_choice_counter_and_id_uniqueness():
    fs = FusedState(seed_val=1)
    fs.add_scene(Scene(scene_id="s1", title="T", objective="O", beats=["b1"]))
    c1 = fs.propose_choice(
        actor="A", situation="s1", obvious="O1", option="O2", odd="O3", position="risky", effect="standard"
    )
    c2 = fs.propose_choice(
        actor="A", situation="s2", obvious="O1", option="O2", odd="O3", position="risky", effect="standard"
    )
    assert c1.choice_id != c2.choice_id
    assert fs._choice_counter == 2
    assert len(fs.choices) == 2


def test_choice_snapshot_and_from_log_hydration_with_clock_ticks():
    """Integration: trivial Say-Yes and rolled choice both hydrate via from_log with correct ticks."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "campaign"
        fs = FusedState(seed_val=42, bundle_root=root, snapshot_every=50)
        sc = Scene(scene_id="s1", title="T", objective="O", threat="goblin", beats=["b1", "b2"])
        fs.add_scene(sc)
        # ensure clock exists
        assert "s1-progress" in fs.clocks
        before = fs.clocks["s1-progress"].ticks
        assert before == 0

        # trivial say_yes (controlled+limited, threat none => trivial despite scene threat goblin? limited always trivial)
        # Use situation that triggers controlled+limited trivial regardless of scene threat
        c_triv = fs.propose_choice(
            actor="A",
            situation="trivial: arrange camp low risk",
            obvious="Refill at well methodically",
            option="Opt",
            odd="Odd",
            position="controlled",
            effect="limited",
        )
        fs.resolve_choice(c_triv.choice_id)
        assert c_triv.trivial is True
        assert c_triv.category == "obvious"
        assert c_triv.ticks == 1
        # clock should have ticked 1
        assert fs.clocks["s1-progress"].ticks == 1

        # rolled choice (risky+standard, not trivial)
        c_roll = fs.propose_choice(
            actor="A",
            situation="Goblin horde blocks gate risky combat",
            obvious="Charge straight into fray",
            option="Sneak around",
            odd="Kick wall and yell at corridor",
            position="risky",
            effect="standard",
        )
        fs.resolve_choice(c_roll.choice_id)
        assert c_roll.trivial is False
        assert c_roll.category in ("obvious", "option", "odd")
        # live clock after both choices: if rolled was odd, no tick; else +2
        live_ticks = fs.clocks["s1-progress"].ticks
        expected = 1 + (0 if c_roll.category == "odd" else 2)
        assert live_ticks == expected

        # snapshot roundtrip
        snap = fs.snapshot()
        fs_snap = FusedState(seed_val=0)
        fs_snap.restore(snap)
        assert len(fs_snap.choices) == 2
        assert fs_snap.choices[0].choice_id == c_triv.choice_id
        assert fs_snap.choices[0].trivial is True
        assert fs_snap.clocks["s1-progress"].ticks == live_ticks

        # from_log hydration (idempotent projection)
        fs_log = FusedState.from_log(root / "events.jsonl")
        assert len(fs_log.choices) == 2
        # choices must match in-memory (trivial flag, ticks, category)
        for orig, hydrated in zip(fs.choices, fs_log.choices):
            assert hydrated.choice_id == orig.choice_id
            assert hydrated.trivial == orig.trivial
            assert hydrated.category == orig.category
            assert hydrated.ticks == orig.ticks
            assert hydrated.choice_text == orig.choice_text
            assert hydrated.resolved_via == orig.resolved_via
        assert fs_log.clocks["s1-progress"].ticks == live_ticks
        # also check that from_log after snapshot still matches (latest snapshot + replay)
        # Ensure no drift when choice ticks are replayed via choice branch + idempotent clock-tick
        assert fs_log.clocks["s1-progress"].ticks == fs.clocks["s1-progress"].ticks


def test_odd_category_no_tick_rule():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "c"
        fs = FusedState(seed_val=0, bundle_root=root)
        sc = Scene(scene_id="s1", title="T", objective="O", threat="goblin", beats=["b1"])
        fs.add_scene(sc)
        # brute force seed that yields odd
        from triple_o.core import TripleO

        odd_seed = None
        for s in range(200):
            t = TripleO(seed=s)
            if t.roll().category == "odd":
                odd_seed = s
                break
        assert odd_seed is not None
        fs2 = FusedState(seed_val=odd_seed, bundle_root=Path(tmp) / "c2")
        sc2 = Scene(scene_id="s1", title="T", objective="O", threat="goblin", beats=["b1"])
        fs2.add_scene(sc2)
        c = fs2.propose_choice(
            actor="A",
            situation="risky odd test",
            obvious="O1",
            option="O2",
            odd="O3",
            position="risky",
            effect="standard",
        )
        fs2.resolve_choice(c.choice_id)
        # if odd, clock should not have ticked even though ticks>0
        if c.category == "odd":
            assert c.ticks == 2
            assert fs2.clocks["s1-progress"].ticks == 0
            # replay should also have 0
            fs2_log = FusedState.from_log(Path(tmp) / "c2" / "events.jsonl")
            assert fs2_log.clocks["s1-progress"].ticks == 0
