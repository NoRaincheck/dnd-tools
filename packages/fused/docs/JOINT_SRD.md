# Fused Joint SRD — Journalistic Campaign for LLM Play

**Status:** canonical for `packages/fused` (issue #11)  
**Principles:** Scenes + Triple-O + Position/Effect + Clocks + Event Log + Traits Separate  
**Engine:** `dnd-tools` (seeded dice/map) behind the curtain, `triple-o` as middleware, `blades-in-the-dark` gate logic ported, paper package frozen.

## 1. Why this SRD

Human 1-pagers (Tricube, Lasers&Feelings/Sword-and-Sorcery) fail for small LLMs (<35B): abstract bonus inference (`tricube/tools.py:169 dice_count/out_of_scope`) is sycophancy-prone — always 3d6, ignores `out_of_scope -1`. PR #10 deleted `tricube` for this reason. Heavy 5e (`dnd_tools` 30+ tools `packages/dnd-tools/src/dnd_tools/tools.py:25`) causes decision paralysis and long `tool_trace` pruning (`packages/fused/src/fused/session.py:158`). **Blades Position/Effect** (`ref/blades-in-the-dark.md §3.1/§7` `set_position_and_effect` + `CONSEQUENCE_TABLE`, now folded into `fused`) is the only proven LLM-hard gate (“cannot soften the blow”). Triple-O (`packages/triple-o/src/triple_o/core.py:82` `1d6 4-6 Obvious/2-3 Option/1 Odd`) constrains option space + injects seeded randomness.

**Journalistic thesis:** LLMs are best at *observe → constrain → roll → narrate → record*, not tactical optimisation. Hence this SRD is journalistic, not tactical sim.

## 2. Core constructs

| Concept | Shape | Store |
|---|---|---|
| **Traits** | `CharacterTraits(name, ancestry, background, archetype, alignment, traits[], flaws[], fears[], bonds[], ideals[], perk, quirk)` `models.py:23` | `FusedState.traits_registry: dict[name->CharacterTraits]` — stable, `fused.trait.registered` event, separate from HP/pos |
| **Scene** | `scene_id, title, objective, location, patron, threat, beats[], clocks[], cast[], status(planned/active/resolved), seed` `models.py:74` | `FusedState.scenes: list[Scene]` + `active_scene_id`; `fused.scene.created` |
| **Clock** | `name, segments(4/6/8), ticks, kind(obstacle/danger/project/healing/turf), completed=ticks>=segments` | `FusedState.clocks: dict[name->Clock]` (per-campaign) + per-scene `Scene.clocks`; scope = `FusedState` for cross-scene heat |
| **Effect** | `effect_id, scene_id, actor, kind, summary, round, turn_actor, payload{}` `models.py:111` | `FusedState.effects: list[Effect]` append-only; canonical JSONL `events.jsonl` CloudEvents `specversion/id/source/type/time/subject + fused{seed,round,scene_id,kind,position,effect} + data{summary,payload}` `events.py:40 make_event` |
| **Position/Effect** | `Position=controlled/risky/desperate`, `Effect=zero/limited/standard/great/extreme`, `EFFECT_TICKS={limited1/standard2/great3/extreme5}` | Pending gate per actor `FusedState._pending` — must be set before `action_roll` |
| **Triple-O** | `Obvious(4-6)/Option(2-3)/Odd(1)`, `advantage=2d6 keep higher favours Obvious` `triple_o/core.py:109` | `TripleO(seed)` seeded via `dnd_tools.dice` |

## 3. Canonical loop (GM transactional controller)

```
for each Scene in campaign order:
  1. setup       create_scene(objective, patron, threat, beats → clocks, cast, seed)
  2. for each turn:
       a) load    get_traits(actor) + get_context(actor,last_n=20)   // separate stores, never conflate
       b) dilemma propose_triple_o(actor,situation,obvious,option,odd,traits)  // constrained 3 branches
       c) choose  roll_triple_o(actor)  // seeded 1d6 authoritative; advantage=2d6
       d) stake   set_position_and_effect(actor,action,position,effect) // REQUIRED GATE — no roll without it
       e) resolve action_roll(actor, clock?) // pool=rpb+bonus(assist/push/devil), zero-dice 2d6kL, highest → critical/success(6)/partial(4-5)/failure(1-3); payload.consequence=CONSEQUENCE_TABLE[position][outcome]; ticks=EFFECT_TICKS[effect] (+1 crit, -1 partial reduced)
       f) pay     if requires_resistance → resistance_roll(actor,attribute) (6−high stress, crit clears 1) OR use_armor/mark_stress/apply_harm  // must pay
       g) record  record_effect(kind,actor,summary,payload{triple_o,position,effect,outcome,ticks,consequence})
       h) tick    tick_clock(name, ticks); if completed → advance_scene_beat or resolve
  3. close       scene status resolved; snapshot every 50 effects + on rest/beat; long_rest between scenes
```

**Valid sequence enforced:** `propose→roll→set_position_and_effect→action_roll→(resistance)→record→tick`. Skipping gate returns `valid:false`.

## 4. Persistence (from PR #9)

```
knowledge/<campaign>/
  events.jsonl                canonical, append-only CloudEvents 1.0, git-diffable, jq/duckdb queryable
  snapshots/<seq>.json        {seq, hash, snapshot: FusedState.snapshot()}  snapshot_hash sha256, every 50 effects
  manifest.json               {head_seq,head_id,snapshot_ref,events_sha256,generated_at}  write_manifest
  projections/campaign.db     DERIVED SQLite (events + wounds view), idempotent build_projection drop/recreate, never committed (.gitignored)
```

Replay = `restore(latest_snapshot_before_N) + replay(non-snapshot events where count in (snapshot.seq, N])` (`state.py:293 from_log` counter fix for 3+ snapshots). `validate_log` checks `specversion 1.0` + required top-level.

Cheap queries (no LLM):
```bash
jq -c 'select(.type=="fused.scene.created" and .fused.scene_id=="scene-01") | {objective: .data.payload.scene.objective}' events.jsonl
jq -c 'select(.data.payload.wound!=null) | {actor:.subject,wound:.data.payload.wound}' events.jsonl
sqlite3 projections/campaign.db "SELECT subject,kind,summary FROM events WHERE scene_id='scene-01' ORDER BY seq"
```

## 5. Tool surface (LLM-facing, ≤16)

Hides raw 5e `roll_attack/roll_dmg/check_valid_attack_line` etc. (kept internally for `Simulation` but not in `tool_schemas`):

```
traits:  register_traits, get_traits, list_traits
scenes:  create_scene, get_scene, list_scenes, advance_scene_beat, set_clock, tick_clock, visualize_clocks
choice:  propose_triple_o, roll_triple_o, propose_group_triple_o, spark_roll
risk:    set_position_and_effect  [GATE]
resolve: action_roll, resistance_roll, mark_stress, apply_harm, use_armor
memory:  record_effect, traverse_history, get_context, summarize_fused
sense:   visualize_map, get_names_of_all_players, get_names_of_all_monsters, roll_initiative
```

`FusedTools.dispatch` still delegates to `base_tools`/`campaign_tools`/`triple_tools` for compat, but `tool_schemas()` exposes only the minimal set above.

## 6. Prompt (rigid, Blades + Triple-O)

```
You are the Guild Manager (GM) — transactional controller.
- Traits SEPARATE from event state. Before acting: get_traits + get_context/traverse_history. Never conflate.
- Scenes have objective/patron/threat/beats→clocks/cast. Track via get_scene/list_scenes, advance via advance_scene_beat/tick_clock.
- Dilemmas: propose_triple_o(Obvious=most predictable given Traits, Option=alternative, Odd=left-field) → roll_triple_o (die authoritative, 1d6 4-6 Obvious/2-3 Option/1 Odd). Optionally spark_roll for flavour.
- Risk gate: set_position_and_effect(controlled/risky/desperate × limited/standard/great) — REQUIRED before action_roll. Do not re-negotiate mid-roll.
- Resolve: action_roll (pool=rating+bonus; zero-dice 2d6kL; 6 clean /4-5 partial+consequence /1-3 fail+consequence; severity=position; ticks per effect; Devil Bargain ticks anyway) → resistance_roll(Insight/Prowess/Resolve, 6−high stress) or use_armor/mark_stress → record_effect → tick_clock. Say <End Turn/> then <End Scene/> when objective complete.
- History is events.jsonl + snapshots (jq/sqlite-queryable). Use traverse_history/get_context before acting. Keep dnd-tools dice authoritative; snapshots auto every 50 effects; long_rest between scenes.
Map: grid 5ft.=adjacency.
```

## 7. Migration notes

- `tricube` deleted (PR #10), `sword-and-sorcery` + `blades-in-the-dark` archived to `ref/` (package logic folded into fused gate). `dnd_tools` frozen, `triple_o` kept as lib, `dnd_campaign` kept as internal snapshot helper but hidden from LLM schemas.
- Scene.beats retained as strings; clocks are canonical progress (beats→clocks via `set_clock`). Old `effect.kind=triple-o` now also carries `fused.position/effect` in event `fused` extension.
```

