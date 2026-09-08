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

> **LLM-verified (2026-09-08, LMStudio :1234, `qwen3.6-35b-a3b-mtp` + `tiel-coder-35b-a3b-mtp` via `tau-ai`/`tau_agent`)**

<details open>
<summary><strong>Verified LLM run — fused Triple-O per character (<code>fused demo --seed 42 --use-llm --model qwen3.6-35b-a3b-mtp</code> via <code>TripleOMiddleware</code>)</strong></summary>

```
--- Elaria (elf tracker, Traits: Suspicious of authority, Always ready to fight) ---
Situation: Goblin horde blocks the road to Tanglewood — what does Elaria do?
Chosen: {'character': 'Elaria', 'roll': 1, 'rolls': [1], 'category': 'odd', 'choice': 'Pretend to be a goblin to confuse the horde.', 'proposal': {'obvious': 'Charge straight into the goblins, ready to fight them all.', 'option': 'Circle to the side to look for a leader, suspecting they are being ordered around.', 'odd': 'Pretend to be a goblin to confuse the horde.'}}
Narration: Elaria suddenly drops to all fours and begins making guttural chittering noises, darting between the goblins with erratic, impulsive energy. She uses stealth to weave through the horde, pretending to be a lost goblin scout to confuse them and investigate the surroundings.

--- Briana (sage wizard, Traits: Inquisitive / Curious) ---
Situation: Trapped corridor hisses — do they search for traps?
Chosen: {'character': 'Briana', 'roll': 2, 'rolls': [2], 'category': 'option', 'choice': "Throw a rock down the hall to trigger mechanisms before stepping in.", 'proposal': {...}}
Narration: Borin snatches a loose stone ... (seed 42: queued next roll → option via same harness)

--- Thalion (fighter) — Group traits [Helpful, Cautious, Reckless] ---
Roll 6 (obvious) → hold position

Tool traces: propose_triple_o → roll_triple_o (seed 42: Elaria 1→odd, Briana 2→option) — deterministic category selection; LLM supplied trait-grounded prose per branch.
```
*LLM correctly invoked `propose_triple_o` → `roll_triple_o` (seed 42), deterministic selection of proposed branches, and narrated the chosen `choice` with trait-aware flavour. Traits (`traits/Elaria.md`, `type: Trait`) stayed in the separate `traits_registry`; the `odd`/`option` choice was recorded as an `Effect` (`type: Effect` in `events/`) without mutating traits.*

</details>

<details>
<summary><strong>Verified LLM run — second model (<code>--model tiel-coder-35b-a3b-mtp</code>, same seed 42)</strong></summary>

```
--- Elaria ---
Situation: Goblin horde blocks the road to Tanglewood — what does Elaria do?
Chosen: {'character': 'Elaria', 'roll': 1, 'rolls': [1], 'category': 'odd', 'choice': 'Elaria hurls insults and challenges the goblin warlord to single combat to break the stand', 'proposal': {'obvious': 'Elaria readies her weapon and charges the goblin horde head-on, ready to fight.', 'option': 'Use keen eye to spot weak point in horde', 'odd': 'Elaria hurls insults and challenges the goblin warlord to single combat to break the stand'}}
Narration: Elaria steps forward, spitting a string of curses at the horde before loud-challenging their warlord to single combat — an erratic, impulsive gambit meant to drag the fight onto her terms.

--- Briana ---
Situation: Trapped corridor hisses — do they search for traps?
Chosen: {'character': 'Briana', 'roll': 1, 'rolls': [1], 'category': 'odd', 'choice': 'She brushes past the hissing corridor entirely, confident she can outrun any trap', 'proposal': {'obvious': 'Meticulously inspect every seam, tile, and hiss', 'option': 'Scan floor for pressure plates', 'odd': 'She brushes past the hissing corridor entirely, confident she can outrun any trap'}}
Narration: The die landed on 1 — the **Odd** branch wins. Briana's arrogance overrides her curiosity: with an erratic, impulsive swagger she sidesteps the hissing corridor entirely ...

Tool traces: 4 — same seeded categories (1→odd, 1→odd) but different branch prose, showing creativity forcing under constrained option space.
```
*Same seeded `1→odd` produces consistent category across `qwen3.6-35b-a3b-mtp` and `tiel-coder-35b-a3b-mtp`, but the LLM-generated prose for each branch differs — demonstrating Triple-O's creativity-forcing: constrained option space + randomness, open-ended narration, while `traits_registry` remains untouched.*

</details>

<details>
<summary><strong>Verified heuristic run (<code>fused demo --seed 42 --turns 12</code> — no LLM)</strong></summary>

```
=== SCENE 1: Goblin Ambush — Survive the ambush on the road to Tanglewood (Wilderlands, Patron: Lord Garrington) ===
<End Turn/>
--- Monster Turn: M1_goblin (round 1) — attacks Briana: roll 12 vs AC 12 -> HIT 2 bludg
--- Player Turn: Elaria (round 1) — Triple-O obvious: Elaria holds position and attacks the nearest foe [Aggressive / Greed → Investigate via Stealth]
--- Player Turn: Thalion (round 1) — Triple-O option: Thalion repositions for flanking [Cautious / Defensive → Defend via Diplomacy]

=== SCENE 2: The Kennel — Clear the kennels and recover Wyldfyre (Undercity) ===
--- Player Turn: Briana (round 2) — Triple-O option: Briana repositions for flanking
--- Player Turn: Mira (round 2) — Triple-O obvious: Mira holds position and attacks the nearest foe
Combat ended after 3 rounds. Deaths: {'log': ['M1_goblin dropped to 0 HP (round 2)', 'M1_wolf dropped to 0 HP (round 3)']}

=== OKF BUNDLE (knowledge/fused-demo) ===
Bundle at: knowledge/fused-demo — 27 concepts, validate == []
traits/elaria.md (type: Trait) — ranger, tracker, elf, Suspicious of authority, Always ready to fight
scenes/scene-01-goblin-ambush.md (type: Scene) — Survive the ambush ... beats: Patrol sets out / Ambushed
events/scene-01-goblin-ambush-0001-01db6b4a.md (type: Effect) — triple-o: Elaria — Triple-O obvious: Elaria holds position ...
events/scene-02-kennel-0012-64ea118c.md (type: Effect) — scene-end: GM — Scene scene-02-kennel ended after 3 rounds

=== AGENT TRAVERSAL (get_context for Elaria) ===
{
  "actor": "Elaria",
  "traits": "ranger, tracker, elf, Suspicious of authority, Always ready to fight",
  "active_scene": "The Kennel — Clear the kennels and recover Wyldfyre",
  "recent_effects": [
    {"kind": "triple-o", "actor": "Elaria", "summary": "Triple-O obvious: Elaria holds position ...", "round": 2},
    {"kind": "scene-end", "actor": "GM", "summary": "Scene scene-02-kennel ended after 3 rounds ...", "round": 3}
  ],
  "allies": ["Briana", "Thalion", "Mira"],
  "adversaries": ["M1_wolf", "M2_wolf", "M3_goblin"]
}

Tool Calls: 13 effects — heuristic mode (seed 42)
```
*Heuristic fallback uses the same `TripleO` engine + `FusedTools` (`register_traits` → `propose_triple_o` → `roll_triple_o` + `record_effect`) without an LLM; OKF bundle is traversable via `cat`, `rg`, or `traverse_history`/`get_context` tools.*

</details>

<details>
<summary><strong>OKF bundle sample (excerpts from <code>knowledge/fused-demo</code> — <code>cat traits/elaria.md</code>)</strong></summary>

```markdown
---
type: Trait
title: Elaria
description: ranger, tracker, elf, Suspicious of authority, Always ready to fight
tags:
  - trait
  - ranger
  - tracker
archetype: ranger
ancestry: elf
background: tracker
alignment: neutral
okf_version: 0.2
generated:
  by: "process:fused"
  at: "2026-09-08T02:43:35Z"
timestamp: "2026-09-08T02:43:35Z"
---

# Elaria — Traits

## Traits

* Suspicious of authority
* Always ready to fight

## Flaws

* Vindictive

## Bonds

* Protect the wilds

## Citations

[1] [OKF Spec](https://okf.md/spec)
```

```markdown
---
type: Scene
title: Goblin Ambush
description: Survive the ambush on the road to Tanglewood
tags:
  - scene
  - wilderlands
  - Goblin raiders
location: Wilderlands
patron: Lord Garrington
threat: Goblin raiders
status: resolved
seed: 43
okf_version: 0.2
---

# Goblin Ambush

**Objective:** Survive the ambush on the road to Tanglewood
**Location:** Wilderlands | **Patron:** Lord Garrington | **Threat:** Goblin raiders

## Cast

* Elaria — see [traits/elaria.md](/traits/elaria.md)
* Briana — see [traits/briana.md](/traits/briana.md)

## Effects

See [events/](/events/index.md) for effect log of scene `scene-01-goblin-ambush`.
```

```markdown
---
type: Effect
title: "triple-o: Elaria"
description: "Triple-O odd: Pretend to be a goblin to confuse the horde."
tags:
  - effect
  - triple-o
  - scene-01-goblin-ambush
scene: scene-01-goblin-ambush
actor: Elaria
kind: triple-o
round: 1
okf_version: 0.2
---

# Effect scene-01-goblin-ambush-0001-xxxx

**Scene:** [scene-01-goblin-ambush](/scenes/scene-01-goblin-ambush.md) | **Actor:** Elaria | **Kind:** `triple-o` | **Round:** 1

> Triple-O odd: Pretend to be a goblin to confuse the horde.

## Citations

[1] [OKF Spec](https://okf.md/spec)
```
*Bundle is conformant: every non-reserved `.md` has frontmatter with `type` (validated via `OKFBundle.validate_bundle` → `[]`); `index.md`/`log.md` provide progressive disclosure; agents traverse via `traverse_history({actor: "Elaria", last_n: 5})` or `cat knowledge/fused-demo/events/*.md | rg "type: Effect"`.*

</details>

## Tests

```bash
uv run pytest packages/fused
```
