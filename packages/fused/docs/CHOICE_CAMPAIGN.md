# Campaign via Choices — Fused Choice Engine (Triple-O + Blades Gate + BW Say Yes)

**Status:** implemented in `packages/fused` (extends Joint SRD GH #11)  
**Principles:** Choices are LLM-derived via Triple-O; trivial choices auto-resolve via Burning Wheel *Say Yes* but remain visible; risky choices go through Blades Position/Effect hard gate.

## Why this design (decisioning vs issues/PRs)

| Prior decision | This design respects it |
|---|---|
| **PR #10 removed tricube** — trait bonus inference sycophancy-prone (always 3d6) | Choice engine uses **seeded 1d6 Triple-O** (`packages/triple-o/src/triple_o/core.py:82`) via `dnd_tools.dice`, not trait-count bonus inference. LLM only authors 3 branches; die is authoritative. |
| **Joint SRD #11** — Blades Position/Effect is the only proven LLM-hard gate (“cannot soften the blow”) and journalistic loop is `get_traits+get_context → propose→roll → set_position_and_effect → action_roll → record → tick_clock` (`packages/fused/docs/JOINT_SRD.md:27`) | Choice engine keeps **Position/Effect as required gate** before any roll (`FusedState.set_position_and_effect`). New `assess_trivial` respects it: only `controlled` + `limited` (or explicit `trivial` tag / `none` threat) qualifies for Say Yes. Risky/Desperate always roll. |
| **GH #4 traits separate from event state, GH #8 canonical JSONL log, PR #9 snapshots+manifest+idempotent projection** | `Choice` is **append-only, event-sourced**: `choices: list[Choice]` in `FusedState` (`state.py:58`), persisted via `events.jsonl` (`fused.choice.proposed / resolved / say_yes`) + snapshots (`snapshot()` includes `choices`/`choice_counter`). `FusedState.from_log` hydrates choices (with update on resolve). Projection remains idempotent; choices are in `events` table. Traits stay separate (`FusedState.traits_registry`). |
| **dnd-tools frozen, paper metrics untouched** | `packages/dnd-tools/*` not edited. `FusedState` wraps `CampaignState` → `GameState`. `ChoiceResolver` consumes `triple_o.TripleO` seeded via same `dnd_tools.dice`. |
| **Burning Wheel SRD `ref/burning-wheel.md:32 Say Yes or Roll + Let It Ride`** | Implements **Say Yes**: if `position=controlled` + `effect=limited` (or explicit `trivial/low risk/easy` in situation, or `threat in {none,unknown}` + `standard`) → auto-select Obvious, `resolved_via=say_yes`, no dice consumed, but **still logged as visible choice** with `trivial_reason`. Else → `rolled` via Triple-O 1d6 (or 2d6 advantage). Let It Ride not re-added; choice log prevents reroll spam. |
| **GUMSHOE core-clue automaticity** (`ref/gumshoe-srd.md:8`) | Say Yes mirrors GUMSHOE core: if you have the ability + are in right place + stakes are nil → automatic, no roll. Here: if traits competent + trivial stakes → Say Yes. |

## Core constructs

```python
@dataclass Choice
  choice_id, scene_id, actor, situation,
  obvious, option, odd, traits[],
  position: controlled|risky|desperate,
  effect: limited|standard|great|zero|extreme,
  trivial: bool, trivial_reason: str,
  roll, rolls, category: obvious|option|odd,
  choice_text, resolved_via: rolled|say_yes, ticks, payload

ChoiceResolver(seed) — propose() validates 3 branches, resolve() applies assess_trivial()
  → if trivial: category=obvious, ticks=1 (or 0 for zero), say_yes, no RNG
  → else: TripleO.roll(advantage) → category/choice_text/ticks=EFFECT_TICKS[effect]
```

## Canonical loop (extends Joint SRD loop with choice branching)

```
for each Scene in campaign order:
  1. setup       create_scene(objective, patron, threat, beats→clocks, cast)
  2. for each dilemma:
       a) load    get_traits(actor) + get_context(actor,last_n=20)
       b) dilemma propose_choice(actor,situation,obvious,option,odd,traits,position,effect)  // LLM authors 3
       c) stake   assess_trivial(position,effect,situation,scene_threat) → Say Yes or gate
       d) choose  resolve_choice(choice_id)  // trivial→Obvious say_yes (no dice); else roll_triple_o 1d6
       e) gate    if not trivial: set_position_and_effect → action_roll → resistance → record → tick_clock
                if trivial: record_choice + tick 1 for momentum
       f) record  choice + effect in events.jsonl (fused.choice.*) + effect trail
  3. close       scene resolved; snapshot every 50 effects + on choice; long_rest between scenes
```

**Valid sequence:** `propose_choice → resolve_choice → (if rolled) set_position_and_effect → action_roll`. Skipping gate returns `valid:false`. Trivial path skips dice but still ticks.

## Tool surface (LLM-facing, extends Joint SRD minimal set)

```
traits:  register_traits, get_traits, list_traits
scenes:  create_scene, get_scene, list_scenes, advance_scene_beat, set_clock, tick_clock, visualize_clocks
choice:  propose_choice, resolve_choice, decide_via_triple_o (one-shot), list_choices
         // propose_choice args: actor,situation,obvious,option,odd,traits,position,effect,scene_id
         // resolve_choice args: choice_id, advantage, force_roll
risk:    set_position_and_effect  [GATE]
resolve: action_roll, resistance_roll, mark_stress, apply_harm, use_armor
memory:  record_effect, traverse_history, get_context, summarize_fused, list_choices
sense:   visualize_map, get_names_of_all_players, get_names_of_all_monsters, roll_initiative
```

`FusedTools.dispatch` delegates to `base/campaign/triple` plus choice handlers. `tool_schemas()` exposes only the minimal set above (hides raw 5e roll_attack etc.).

## Persistence & queryability

```
knowledge/<campaign>/
  events.jsonl                canonical, CloudEvents 1.0, jq-queryable
    fused.choice.proposed   {choice, proposal, position, effect}
    fused.choice.say_yes    {choice, trivial, trivial_reason, resolved_via=say_yes, category=obvious}
    fused.choice.resolved   {choice, category, roll, choice_text, resolved_via=rolled}
  snapshots/<seq>.json        {choices, choice_counter, ...} + hash
  manifest.json               {head_seq, snapshot_ref, events_sha256}
  projections/campaign.db     DERIVED SQLite (events view), idempotent
```

Cheap queries (no LLM):

```bash
# all choices proposed
jq -c 'select(.type=="fused.choice.proposed") | {id:.id, actor:.subject, situation:.data.payload.choice.situation}' knowledge/fused-demo/events.jsonl

# trivial Say Yes choices (auto-resolved but visible)
jq -c 'select(.type=="fused.choice.say_yes") | {actor:.subject, choice:.data.payload.choice_text, reason:.data.payload.trivial_reason}' events.jsonl

# rolled choices by category
jq -c 'select(.type=="fused.choice.resolved") | {actor:.subject, category:.data.payload.category, roll:.data.payload.roll, choice:.data.payload.choice_text}' events.jsonl

# full campaign branching timeline
jq -c 'select(.type | startswith("fused.choice.")) | {seq:.id, type, category:.data.payload.category, via:.data.payload.resolved_via}' events.jsonl

# SQLite (projection)
sqlite3 projections/campaign.db "SELECT type, subject, json_extract(data,'$.summary') FROM events WHERE type LIKE 'fused.choice%' ORDER BY seq"
```

Determinism: all rolls via `dnd_tools.dice` seeded RNG; Say Yes consumes **no RNG**, so seeded sequence for risky choices remains identical across runs.

## LLM derivation & trivial visibility

Prompt fragment the harness enforces (see `choice.py:assess_trivial`):

```
You are Guild Manager (GM) — transactional controller.
- Before acting: get_traits + get_context. Never conflate.
- For each dilemma: call propose_choice with 3 LLM-authored branches:
  obvious = most predictable given Traits,
  option = reasonable alternative,
  odd    = left-field / impulsive.
  Include position/effect (controlled/risky/desperate × limited/standard/great).
- Call resolve_choice — if trivial (controlled+limited, or explicit trivial tag, or none threat) the engine auto Say Yes to obvious
  but still logs all 3 proposals + reason "Say Yes — trivial stakes: ..." as visible choice.
  Else engine rolls 1d6 (4-6 obvious, 2-3 option, 1 odd) and returns chosen branch — narrate it.
- Then if rolled: set_position_and_effect → action_roll (pool derived from Traits, zero-dice 2d6kL) → resistance if needed → tick_clock.
  If say_yes: just record and tick 1 for momentum.
Map: grid 5ft adjacency (for sense).
```

Heuristic fallback (no LLM) mirrors the same propose→resolve loop via `TripleOMiddleware.run_heuristic` without LLM.

## Running

```bash
# choice-driven pure campaign (no combat) — demonstrates Say Yes vs roll
uv run python -c "
from fused.state import FusedState
from fused.session import FusedSession
fs = FusedState(seed_val=42, bundle_root='knowledge/fused-demo')
sess = FusedSession(fs)
# ... register traits, then:
specs = [
  {'actor':'Elaria','situation':'trivial: arrange camp, refill waterskins — low risk','obvious':'Refill at well','option':'Barter','odd':'Sing while refilling','position':'controlled','effect':'limited'},
  {'actor':'Elaria','situation':'Goblin horde blocks gate; party must breach','obvious':'Charge straight','option':'Scan perimeter','odd':'Feign surrender','position':'risky','effect':'standard'},
]
sess.run_campaign_via_choices(specs)
"

# existing scene+combat demo now also logs choices before combat
uv run fused demo --seed 42 --turns 12
cat knowledge/fused-demo/events.jsonl | jq -c 'select(.type|startswith("fused.choice."))'
uv run fused validate --log knowledge/fused-demo/events.jsonl
uv run fused build-projection --log knowledge/fused-demo/events.jsonl --db /tmp/campaign.db
```

## Files touched

- `packages/fused/src/fused/models.py` — adds `Choice` dataclass
- `packages/fused/src/fused/choice.py` — new: `assess_trivial`, `ChoiceResolver` (Triple-O + Say Yes)
- `packages/fused/src/fused/state.py` — adds `choices`, `choice_resolver`, `propose_choice/resolve_choice/decide_via_triple_o`, snapshot/restore, from_log hydration
- `packages/fused/src/fused/tools.py` — exposes `propose_choice/resolve_choice/decide_via_triple_o/list_choices` + schemas
- `packages/fused/src/fused/session.py` — `run_scene` logs Choice before combat; new `run_campaign_via_choices` for pure choice unfolding
- `packages/fused/src/fused/events.py` — adds `fused.choice.*` to VALID_TYPES
- `packages/fused/src/fused/__init__.py` — re-exports `Choice`, `ChoiceResolver`, `assess_trivial`
```

