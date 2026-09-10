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
# static site with rewind/playthrough (file:// friendly, no server required)
uv run fused build-site --bundle knowledge/fused-demo --out knowledge/fused-demo/site
open knowledge/fused-demo/site/index.html#seq=5  # slider + Play/Pause + ←→/Space + hash deep-link
python -m http.server --directory knowledge/fused-demo/site 8000
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

## Static site (rewind / playthrough)

`fused build-site` turns the canonical `events.jsonl` + derived `timeline` states into a fully static, `file://`-friendly site — no server, no build step.

```bash
uv run fused build-site --bundle knowledge/fused-demo --out knowledge/fused-demo/site --title "Fused Campaign"
# outputs: site/index.html (embedded events+timeline) + site/data.json + site/events.jsonl
```

Features (all client-side, after precomputing states at build time via `FusedState._apply_event`):

- **Scrubbable timeline**: range slider `0..N` (0 = before any event), click any event to jump, hash `#seq=10` deep-links.
- **Rewind / playthrough**: `⏮ ◀ ▶/⏸ ▶▶ ⏭`, autoplay with speed `0.5×/1×/2×/4×`, loop toggle, `Space`/`←`/`→`/`Home`/`End` keys.
- **State @ seq panel**: clocks (filled bar + `ticks/segments`), active scene, stress, characters (HP/pos), transcript tail, diff vs previous (`+clock`, `~tick`, `+traits`), and raw JSON.
- **File:// safe**: all data embedded via `<script type="application/json">` — no `fetch`, works by double-clicking `index.html`.

See `packages/fused/src/fused/site.py:1` (`build_site`, `build_timeline`, `collect_bundle`).

## Tools (LLM-visible)

All paper tools plus campaign/Triple-O plus fused:

- `register_traits` / `get_traits` / `list_traits`
- `create_scene` / `get_scene` / `list_scenes` / `advance_scene_beat`
- `record_effect` / `traverse_history` / `get_context` / `summarize_fused`

## Determinism & Idempotence

- All dice via `dnd_tools.dice` seeded RNG. Same seed → identical rolls, scenes, and event log.
- **Projection is idempotent**: `build_projection(log, db)` drops/recreates tables; delete `projections/campaign.db` and rerun → identical DB. DB is `.gitignored`; log + snapshots are the source of truth and can recreate it.
- `FusedState.from_log(events.jsonl, at_seq=N)` = `restore(latest_snapshot_before_N) + replay(events where seq > snapshot)`.

## Tests

```bash
uv run pytest packages/fused
```
