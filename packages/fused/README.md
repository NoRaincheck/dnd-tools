# fused — Fused TTRPG (Scenes + Triple-O + Event Log)

Implements [GH #4](https://github.com/NoRaincheck/dnd-tools/issues/4) + [GH #8](https://github.com/NoRaincheck/dnd-tools/issues/8) — a **fused ruleset** that keeps narrative structure while forcing LLM creativity, and records campaign history as a **canonical JSONL event log** (CloudEvents-compatible) with snapshots and an idempotent projection.

## What this solves

| Issue | `fused` answer |
|---|---|
| *Fused ruleset that helps with creativity (e.g. Triple-O) and yet maintains narrative structure + scenes setup* | Campaign = ordered **scenes** (objective, patron, threat, beats, cast). Inside each scene, player dilemmas go through **Triple-O middleware** (Obvious/Option/Odd, seeded 1d6) — constrained option space + randomness. |
| *Record campaign history so an Agent can traverse it before acting* | Every trait/scene/effect is an **append-only JSONL event** (`events.jsonl`, one object per line, `specversion: 1.0`, `type: fused.*`). `jq`/`duckdb`/`sqlite`-queryable; `snapshots/<seq>.json` + `manifest.json` make replay `O(events since snapshot)`. |
| *Cheap thread queries + CLI builder* | `jq 'select(.type=="fused.effect.recorded")' events.jsonl` or `sqlite3 projections/campaign.db "SELECT * FROM wounds WHERE actor='Elaria'"` — no LLM needed. DB projection is **derived, idempotent, never committed** (`build_projection` drops/recreates). |
| *Character traits should be maintained separate to the event state* | `traits_registry: dict[name -> CharacterTraits]` (stable, `fused.trait.registered`) is **separate** from `effects: list[Effect]` (transient event state). |

Simplification vs OKF bundle (#8): the former `OKFBundle` (dozens of markdown files with YAML frontmatter + payload in body) was human-traversable via `cat`/`rg` but functionally not reconstructable and expensive (`O(files)` I/O + regex over body). The log replaces it as the **single source of truth** — `FusedState.restore(snapshot)+replay(events)` is deterministic via seeded dice.

## Architecture

```
FusedState
  ├── CampaignState (dnd_campaign) → GameState (dnd_tools)  # authoritative mechanics
  ├── traits_registry: CharacterTraits  [separate store]
  ├── scenes: Scene[]                   [narrative structure]
  ├── effects: Effect[]                 [append-only, in-memory]
  └── knowledge/fused-demo/             # on-disk canonical log
        ├── events.jsonl                ← CANONICAL, append-only, CloudEvents + fused.*
        ├── snapshots/00000.json        ← periodic full snapshot (state.py snapshot())
        ├── manifest.json               ← head_seq + snapshot_ref + events sha256
        └── projections/campaign.db     ← DERIVED SQLite (idempotent, .gitignored)
```

Paper code in `dnd_tools`/`dnd_campaign` is never edited.

## Quickstart

```bash
uv sync
uv run fused demo --seed 42 --turns 12
cat knowledge/fused-demo/events.jsonl | jq -c 'select(.type=="fused.effect.recorded") | {id, subject, fused}'
uv run fused validate --log knowledge/fused-demo/events.jsonl
uv run fused build-projection --log knowledge/fused-demo/events.jsonl --db knowledge/fused-demo/projections/campaign.db
sqlite3 knowledge/fused-demo/projections/campaign.db "SELECT subject, kind, summary FROM events ORDER BY seq DESC LIMIT 5"
uv run fused replay --log knowledge/fused-demo/events.jsonl --at-seq 10
```

LLM (optional):
```bash
uv run fused demo --seed 42 --use-llm --model qwen3.6-35b-a3b-mtp
```

## Cheap query examples (no LLM)

```bash
# goal of scene 01 + was it achieved?
jq -c 'select(.type=="fused.scene.created" and .fused.scene_id=="scene-01-goblin-ambush") | {objective: .data.payload.scene.objective}' knowledge/fused-demo/events.jsonl

# what wounds did characters endure?
jq -c 'select(.data.payload.wound != null) | {actor: .subject, wound: .data.payload.wound, summary}' knowledge/fused-demo/events.jsonl

# HP timeline for Elaria (DuckDB, columnar)
duckdb -c "SELECT subject, count(*) AS wounds FROM read_json('knowledge/fused-demo/events.jsonl') WHERE type='fused.effect.recorded' GROUP BY subject"
```

## Campaign via choices (LLM-derived, Burning Wheel Say Yes)

A campaign unfolds as a sequence of **Choices**. The LLM authors each Choice via **Triple-O** (`obvious`/`option`/`odd`), then the engine resolves it:

- **Trivial / low-risk** (`position=controlled` + `effect=limited`, or `trivial`/`low risk` tag, or `threat=none`) → **Say Yes** auto-selects Obvious with visible `trivial_reason`, **no dice consumed**.
- **Risky/Desperate** → **rolled** `1d6` (4-6 obvious, 2-3 option, 1 odd, or `2d6` with advantage) + Blades `Position/Effect` gate → `action_roll`.

Both paths are **logged as `fused.choice.*` events** (jq/sqlite-queryable) and as `Effect(kind=choice)` for `traverse_history`.

```python
from fused.state import FusedState
from fused.session import FusedSession
from fused.models import CharacterTraits

fs = FusedState(seed_val=42, bundle_root="knowledge/fused-demo")
sess = FusedSession(fs)
sess.register_party_traits([
    CharacterTraits(name="Elaria", archetype="ranger", traits=["brave","keen eye"]),
    CharacterTraits(name="Borin", archetype="fighter", traits=["stubborn","cautious"]),
])
specs = [
    {"actor":"Elaria","situation":"trivial: arrange camp, refill waterskins at well — low risk","obvious":"Refill at well methodically","option":"Barter with locals","odd":"Sing loudly while refilling","position":"controlled","effect":"limited"},
    {"actor":"Elaria","situation":"Goblin horde blocks gate; party must breach","obvious":"Charge straight into fray","option":"Scan perimeter for weak point","odd":"Feign surrender to get close","position":"risky","effect":"standard"},
    {"actor":"Borin","situation":"A trapped corridor hisses — do they search for traps?","obvious":"Search carefully for traps","option":"Throw rock to trigger mechanisms","odd":"Kick wall and yell at corridor","position":"risky","effect":"standard"},
    {"actor":"Elaria","situation":"Group dilemma: hold position, negotiate, or flee","obvious":"Hold position","option":"Negotiate","odd":"Flee","position":"desperate","effect":"great"},
    {"actor":"Borin","situation":"trivial: mend torn cloak at campfire — easy","obvious":"Stitch with needle","option":"Use mage hand","odd":"Wear as cape","position":"controlled","effect":"limited"},
]
sess.run_campaign_via_choices(specs, scene_id="scene-demo", scene_title="Demo Choices")

# also via tools: propose_choice → resolve_choice → decide_via_triple_o → list_choices
```

### Verified output — `seed 42` (deterministic)

<details open>
<summary><strong>Heuristic + Triple-O choice unfolding (no LLM)</strong></summary>

```
- trivial: arrange camp, refill waterskins a | SAY YES (trivial — auto) | -> Refill at well methodically
  reason: Say Yes — trivial stakes: position=controlled, effect=limited
  proposal: {'obvious': 'Refill at well methodically', 'option': 'Barter with locals for skins', 'odd': 'Sing loudly while refilling'}
- Goblin horde blocks gate; party must breac | ROLL obvious (rolled)  | -> Charge straight into fray
  roll category=obvious via rolled | proposal={'obvious': 'Charge straight into fray', 'option': 'Scan perimeter for weak point', 'odd': 'Feign surrender to get close'}
- A trapped corridor hisses — do they search | ROLL odd (rolled)      | -> Kick wall and yell at corridor
  roll category=odd via rolled | proposal={'obvious': 'Search carefully for traps', 'option': 'Throw rock to trigger mechanisms', 'odd': 'Kick wall and yell at corridor'}
- Group dilemma: hold position, negotiate, o | ROLL odd (rolled)      | -> Flee
  roll category=odd via rolled | proposal={'obvious': 'Hold position', 'option': 'Negotiate', 'odd': 'Flee'}
- trivial: mend torn cloak at campfire — eas | SAY YES (trivial — auto) | -> Stitch with needle
  reason: Say Yes — trivial stakes: position=controlled, effect=limited
  proposal: {'obvious': 'Stitch with needle', 'option': 'Use mage hand', 'odd': 'Wear as cape'}

Total choices: 5 (trivial=2 rolled=3)
Log: knowledge/fused-demo/events.jsonl (13 events)
```

*Trivial `controlled/limited` choices auto-resolve to Obvious with a visible reason (Burning Wheel Say Yes), consuming no RNG — the next risky `1d6` for Elaria at the gate is still `roll 6 → obvious`, then Borin `roll 1 → odd`, Elaria group `roll 1 → odd` (seed 42 deterministic). Both paths appear as logged Choices.*

</details>

<details>
<summary><strong>Canonical JSONL (jq)</strong></summary>

```bash
cat events.jsonl | jq -c 'select(.type=="fused.choice.say_yes") | {actor:.subject, via:.data.payload.resolved_via, choice:.data.payload.choice_text, reason:.data.payload.trivial_reason}'
# {"actor":"Elaria","via":"say_yes","choice":"Refill at well methodically","reason":"Say Yes — trivial stakes: position=controlled, effect=limited"}
# {"actor":"Borin","via":"say_yes","choice":"Stitch with needle","reason":"Say Yes — trivial stakes: position=controlled, effect=limited"}

cat events.jsonl | jq -c 'select(.type=="fused.choice.resolved") | {actor:.subject, category:.data.payload.category, roll:.data.payload.roll, choice:.data.payload.choice_text}'
# {"actor":"Elaria","category":"obvious","roll":6,"choice":"Charge straight into fray"}
# {"actor":"Borin","category":"odd","roll":1,"choice":"Kick wall and yell at corridor"}
# {"actor":"Elaria","category":"odd","roll":1,"choice":"Flee"}

cat events.jsonl | jq -c 'select(.type|startswith("fused.choice.")) | {type, actor:.subject, summary:.data.summary}' | head
# {"type":"fused.choice.proposed","actor":"Elaria","summary":"Choice proposed: trivial: arrange camp, refill waterskins at well — low risk | O:Refill at well methodically / Opt:Barter with locals for skins / Odd:Sing loudly while refilling"}
# {"type":"fused.choice.say_yes","actor":"Elaria","summary":"Choice obvious (say_yes): Refill at well methodically — Say Yes trivial: Say Yes — trivial stakes: position=controlled, effect=limited"}
# {"type":"fused.choice.proposed","actor":"Elaria","summary":"Choice proposed: Goblin horde blocks gate; party must breach | O:Charge straight into fray / Opt:Scan perimeter for weak point / Odd:Feign surrender to get close"}
# {"type":"fused.choice.resolved","actor":"Elaria","summary":"Choice obvious (rolled): Charge straight into fray"}
```

`fused demo --seed 42` also logs Choices before combat (now via `FusedSession.run_scene`); query that log the same way:

```bash
uv run fused demo --seed 42 --turns 4
cat knowledge/fused-demo/events.jsonl | jq -c 'select(.type|startswith("fused.choice.")) | {type, actor:.subject, summary:.data.summary}'
```

</details>

### Tools (LLM-visible)

All paper tools plus campaign/Triple-O plus fused:

- `register_traits` / `get_traits` / `list_traits`
- `create_scene` / `get_scene` / `list_scenes` / `advance_scene_beat`
- `record_effect` / `traverse_history` / `get_context` / `summarize_fused`
- `propose_choice` / `resolve_choice` / `decide_via_triple_o` / `list_choices` — **choice unfolding**
- `set_position_and_effect` / `action_roll` / `resistance_roll` / `mark_stress` / `set_clock` / `tick_clock` / `visualize_clocks` — **Blades gate** (must precede `action_roll`)

## Determinism & Idempotence

- All dice via `dnd_tools.dice` seeded RNG. Same seed → identical rolls, scenes, and event log.
- **Projection is idempotent**: `build_projection(log, db)` drops/recreates tables; delete `projections/campaign.db` and rerun → identical DB. DB is `.gitignored`; log + snapshots are the source of truth and can recreate it.
- `FusedState.from_log(events.jsonl, at_seq=N)` = `restore(latest_snapshot_before_N) + replay(events where seq > snapshot)`.

## Tests

```bash
uv run pytest packages/fused
```
