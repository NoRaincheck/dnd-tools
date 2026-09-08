# fused — Fused TTRPG (Scenes + Triple-O + OKF)

Implements [GH #4](https://github.com/NoRaincheck/dnd-tools/issues/4) — a **fused ruleset** that keeps narrative structure while forcing LLM creativity, and records campaign history as a **traversable OKF bundle**.

## What this solves (issue #4)

The ref TTRPGs (`ref/tricube-tales.md`, `ref/sword-and-sorcery.md`, `ref/triple-o.md`) are not followed strictly elsewhere. `fused` provides:

| Issue text | `fused` answer |
|---|---|
| *Fused ruleset that helps with creativity (e.g. Triple-O) and yet maintains narrative structure + scenes setup* | Campaign = ordered **scenes** (objective, patron, threat, beats, cast). Inside each scene, player dilemmas go through **Triple-O middleware** (Obvious/Option/Odd, seeded 1d6) — constrained option space + randomness. |
| *Overall goal is to run a campaign, recording effects via https://okf.md/spec* | Every effect/event is an append-only OKF concept (`type: Effect` in `events/*.md`). Full bundle is markdown + YAML frontmatter per OKF spec; `index.md` + `log.md` provide progressive disclosure. Validated via `OKFBundle.validate_bundle`. |
| *So that an Agent can traverse through history of the campaign to gain context before acting* | Tools `traverse_history`, `get_context`, `summarize_fused` + `build_agent_context` provide bounded history traversal. Agents traverse the bundle (`events/`, `scenes/`, `traits/`) rather than a flat trace. |
| *Character traits should be maintained separate to the event state* | `traits_registry: dict[name -> CharacterTraits]` (stable, OKF `type: Trait`) is **separate** from `effects: list[Effect]` (transient event state). Characters in `CampaignState` hold HP/pos; traits hold background/flaws/traits/bonds — never conflated. |

## Architecture

```
FusedState
  ├── CampaignState (dnd_campaign) → GameState (dnd_tools)  # authoritative mechanics
  ├── traits_registry: CharacterTraits  [separate store]
  ├── scenes: Scene[]                   [narrative structure]
  ├── effects: Effect[]                 [append-only event log]
  └── OKFBundle → knowledge/fused-demo/
        ├── traits/<name>.md      (type: Trait)
        ├── characters/<name>.md   (type: Character)
        ├── scenes/<id>.md         (type: Scene)
        ├── events/<id>.md         (type: Effect)
        ├── references/attesters/fused_run.md (type: Attested Computation)
        ├── index.md / <dir>/index.md
        └── log.md
```

Paper code in `dnd_tools`/`dnd_campaign` is never edited.

## Quickstart

```bash
uv sync
uv run fused demo --seed 42 --turns 12
cat knowledge/fused-demo/index.md
cat knowledge/fused-demo/log.md
cat knowledge/fused-demo/traits/elaria.md
uv run fused demo --seed 42 --bundle /tmp/my-bundle --save /tmp/run.json
```

LLM (optional):
```bash
# requires LMStudio at :1234
uv run fused demo --seed 42 --use-llm --model qwen3.6-35b-a3b-mtp
```

## Tools (LLM-visible)

All paper tools (`check_valid_attack_line`, `roll_attack`, `move`, `dash`, `roll_initiative`, …) plus campaign tools (`long_rest`, `checkpoint`, …) plus Triple-O tools (`propose_triple_o`, `roll_triple_o`, `ask_triple_o`, `spark_roll`) plus fused tools:

- `register_traits` / `get_traits` / `list_traits`
- `create_scene` / `get_scene` / `list_scenes` / `advance_scene_beat`
- `record_effect` / `traverse_history` / `get_context` / `export_okf` / `summarize_fused`

## Determinism

All dice via `dnd_tools.dice` seeded RNG. Re-running with the same seed yields identical Triple-O rolls, scene seeds, and bundle hashes. Bundle concepts have stable frontmatter; `export_okf` validates OKF conformance (every non-reserved `.md` has `type`).

## Tests

```bash
uv run pytest packages/fused
```
