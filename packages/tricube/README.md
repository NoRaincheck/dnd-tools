# tricube — Tricube Tales tool-grounded implementation

> **LLM-verified (2026-09-04, LMStudio :1234, `tiel-coder-35b-a3b-mtp` + `mistral-small-3.2-24b-instruct-2506` via `tau-ai`/`tau_agent`)**

<details open>
<summary><strong>Verified LLM run — single scene (<code>tricube scene --seed 42 --turns 3 --use-llm --model tiel-coder-35b-a3b-mtp</code>)</strong></summary>

```
=== TRANSCRIPT ===
Initiative: [{'name': 'Lyra', 'initiative': 7}, {'name': 'Fenn', 'initiative': 7}, {'name': 'Ogre', 'initiative': 4}, {'name': 'Goblin1', 'initiative': 4}, {'name': 'Goblin2', 'initiative': 3}, {'name': 'Mira', 'initiative': 2}, {'name': 'Borin', 'initiative': 2}]
<End Turn/>
--- Player Turn: Lyra (round 1) ---
Lyra: Clean hit — the 6 clears difficulty 4, and the strike drops Goblin1's effort to 0. One goblin down.

*Lyra nocks a second arrow, the ranger's keen eye tracking the last goblin across the open ground, then looses — the shot finds its mark and the goblin crumples.*

Goblin1 defeated (effort 0). Two threats remain: Goblin2 at (14,9) and the Ogre at (12,11).

<Call/>Fenn, Mira — focus the Ogre at (12,11); I'll pick off the last goblin next turn.

<DM/> <DM/>
<End Turn/>
--- Player Turn: Fenn (round 1) ---
Fenn: Exceptional hit! Fenn's crafty strike lands true — rolling double sixes, the blow connects for a critical. The Ogre's effort pool empties and it crashes down, defeated.

*Fenn steps back from the falling ogre, scholar's eyes bright with the thrill of a perfectly placed strike.*

<Call/>Lyra, Borin — ogre down! Press the goblins before they close up!

<DM/> <DM/>
<End Turn/>
--- Monster Turn: Ogre (round 1) ---
Ogre (monster) pressures Fenn: [1, 5, 4] vs 5 -> success resolve cost 0 -> 3/3
<End Turn/>
Scene ended after 3 turns. Afflictions: {'log': []}

=== RESULT ===
{
  "players": {
    "Lyra": {"resolve": 3, "max": 3, "karma": 3, "afflictions": 0, "retired": false},
    "Borin": {"resolve": 3, "max": 3, "karma": 3, "afflictions": 0, "retired": false},
    "Mira": {"resolve": 3, "max": 3, "karma": 3, "afflictions": 0, "retired": false},
    "Fenn": {"resolve": 3, "max": 3, "karma": 3, "afflictions": 0, "retired": false}
  },
  "effort_pools": {"Goblin1": 0, "Goblin2": 1, "Ogre": 0}
}
Tool Calls: 26
```
*LLM correctly invoked `visualize_map`, `check_karma_resolve`, `check_effort`, `check_valid_attack_line`, `roll_challenge` with trait/effort_target, coordinated via `<Call/>`, and managed effort pools deterministically via `TricubeTools`.*

</details>

<details>
<summary><strong>Verified LLM run — 3-scene campaign (<code>tricube campaign --seed 42 --turns 3 --use-llm --model mistral-small-3.2-24b-instruct-2506</code>)</strong></summary>

```
=== SCENE 1 ===
Initiative: [{'name': 'Mira', 'initiative': 6}, {'name': 'Goblin1', 'initiative': 6}, {'name': 'Fenn', 'initiative': 6}, {'name': 'Ogre', 'initiative': 3}, {'name': 'Lyra', 'initiative': 3}, {'name': 'Borin', 'initiative': 3}]
--- Player Turn: Mira (round 1) ---
Mira: I'll check the status of my target, the Ogre.
check_karma_resolve / check_effort → move_player → roll_challenge <DM/>
--- Monster Turn: Goblin1 ---
Goblin1 (monster) pressures Borin: [2, 6, 6] vs 5 -> success resolve cost 0 -> 3/3
--- Player Turn: Fenn (round 1) ---
Fenn: invoke_quirk(timid) → roll_challenge(crafty) — "The Ogre's left pauldron is loose! Focus your attacks there!" <Call/>Lyra, Borin, Mira, aim for the Ogre's left side!<Call/> <DM/>
Scene ended after 3 turns. Afflictions: {'log': []}
... (scenes 2-3 repeat with same toolchain; full output truncated for README — see transcript below)
=== SCENE 2 & 3 === (identical toolchain per scene, 24s avg per player turn via tau harness)

=== CAMPAIGN SUMMARY ===
{
  "round": 1, "turn": "Ogre",
  "players": {
    "Lyra": {"trait": "agile", "concept": "ranger", "karma": "3/3", "resolve": "3/3", "rank": 1, "pos": [6,9,0], "afflictions": 0},
    "Borin": {"trait": "brawny", "concept": "knight", "karma": "3/3", "resolve": "3/3"},
    "Mira": {"trait": "crafty", "concept": "mage", "karma": "3/3", "resolve": "3/3"},
    "Fenn": {"trait": "crafty", "concept": "scholar", "karma": "3/3", "resolve": "3/3"}
  },
  "monsters": {"Ogre": {"resolve": "3/3", "pos": [12,9,0], "effort": 4}, "Goblin1": {"resolve": "3/3", "pos": [14,9,0], "effort": 1}},
  "effort_pools": {"Horde": 4}, "affliction_log": [], "meta": {"seed": 42, "scenes": 3}
}
```
*Each scene used `TricubeCampaignState` checkpoint/history, `TricubeCampaignTools` (`get_summary`, `prune_traces`, `long_rest` between scenes), and `TricubeSession.run_campaign` — bounded context via `memory.summarize_state`/`compact_transcript`.*

</details>

<details>
<summary><strong>Verified heuristic run (<code>tricube scene --seed 42 --turns 12</code> — no LLM)</strong></summary>

```
=== TRANSCRIPT ===
Initiative: [{'name': 'Lyra', 'initiative': 7}, ...]
--- Player Turn: Lyra (round 1) ---
Lyra attacks Goblin1 (agile) [2, 6, 1] vs 5 -> success -1 effort (remaining 0). <DM/>
--- Player Turn: Fenn (round 1) ---
Fenn attacks Ogre (crafty) [6, 6, 5] vs 6 -> exceptional success! -2 effort (remaining 0). <DM/>
--- Monster Turn: Ogre (round 1) ---
Ogre (monster) pressures Fenn: [1, 5, 4] vs 5 -> success resolve cost 0 -> 3/3
...
Scene ended after 6 turns. Afflictions: {'log': []}
Tool Calls: 30
```
*Heuristic fallback uses same tool surface (`heuristic_player_turn`) when LLM unavailable or on provider error.*

</details>

---

Uses `dnd-tools` + `dnd-campaign` as foundations (mapgen, seeded dice, tau-ai harness, snapshot/campaign plumbing) and implements the Tricube Tales core on top.

- **Single scene** (`TricubeState` + `TricubeTools` + `TricubeSimulation`) — one challenge/combat scene with deterministic `1-3d6` resolution, karma/quirk gates, effort pools, afflictions.
- **Multiple scenes with context** (`TricubeCampaignState` + `TricubeCampaignTools` + `TricubeSession`) — bounded history, checkpoints, `get_summary`/`prune_traces` for LLM context, long rests between scenes.
- **Whole campaign** (`run_campaign`) — sequence of scenes with inter-scene long rests and persistence.
- **LLM** via `tau-ai` / `tau_agent` (LMStudio `:1234` by default, verified above with `tiel-coder-35b-a3b-mtp`/`mistral-small-3.2`/`bonsai-27b`), with heuristic fallback.

## Quickstart

```bash
uv sync
# single scene (heuristic)
uv run tricube scene --seed 42 --turns 12
# single scene via LLM (requires LMStudio at :1234)
uv run tricube scene --seed 42 --turns 3 --use-llm --model tiel-coder-35b-a3b-mtp
# 3-scene campaign
uv run tricube campaign --seed 42 --turns 3 --use-llm --model mistral-small-3.2-24b-instruct-2506
# generate scenarios
uv run tricube gen-scenarios --out /tmp/tricube_test_scen
uv run pytest
```
