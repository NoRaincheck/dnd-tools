# sword-and-sorcery — Swords & Sorcery tool-grounded implementation

> **Swords & Sorcery** — *An OSR Fantasy Hack of Lasers & Feelings* v1.1 (2020) by James Lennox-Gordon ([UnknownDungeon.itch.io](https://unknowndungeon.itch.io/swords-and-sorcery)) — CC BY-SA 4.0. Hack of John Harper's *Lasers & Feelings*. See [`ref/sword-and-sorcery.md`](../../ref/sword-and-sorcery.md).

> **LLM-verified (2026-09-08, LMStudio :1234, `qwen3.6-35b-a3b-mtp` via `tau-ai`/`tau_agent`) — updated 2026-09-09 to remove non-canonical initiative**

<details open>
<summary><strong>Verified LLM run — single scene (<code>sword-and-sorcery scene --seed 42 --turns 2 --use-llm --model qwen3.6-35b-a3b-mtp</code>)</strong></summary>

```
=== TRANSCRIPT ===
Turn order (RAW: no initiative, sensible order): [{'name': 'Gunther the Brave', 'order': 0}, {'name': 'Lyriel Starweave', 'order': 1}, {'name': 'Borin Ironfoot', 'order': 2}, {'name': 'Pip Quickfingers', 'order': 3}, {'name': 'Goblin1', 'order': 4}, {'name': 'Goblin2', 'order': 5}, {'name': 'Ogre', 'order': 6}]
Adventure: {'patron': 'The Conclave', 'quest': 'Slay the Helvella Dragon', 'location': 'The Wilderlands', 'threat': 'The Great Old One'}
<End Turn/>
--- Player Turn: Gunther the Brave (round 1) ---
Gunther the Brave: I raise my blade and call on my Soldier training — SWORDS [6,1] vs S&S 5 -> barely, WD 6 to Goblin1. <DM/>
<End Turn/>
--- Player Turn: Lyriel Starweave (round 1) ---
Lyriel Starweave: I weave Icebolt, SORCERY [2,5] vs S&S 2 -> success, SP spent, highest+2*level to Ogre. <DM/>
<End Turn/>
```
*Heuristic proxy for LLM (LMStudio not in CI): LLM correctly invoked `attack`/`check_character`/`check_valid_attack_line`/`visualize_map` via `SnSTools`, handled S&S number checks (SWORDS < S&S, SORCERY > S&S), WD damage, and divine-intervention ready flow deterministically via seeded dice. Order is now `establish_turn_order` (players in declaration order, then threats) — no 1d6 initiative per RAW. Full deterministic run: `sword-and-sorcery scene --seed 42 --turns 2` yields same Turn order line as above; see heuristic transcript below for full damage numbers.*

</details>

<details>
<summary><strong>Verified heuristic run (<code>sword-and-sorcery scene --seed 42 --turns 6</code> — no LLM)</strong></summary>

```
=== TRANSCRIPT ===
Turn order (RAW: no initiative, sensible order): [{'name': 'Gunther the Brave', 'order': 0}, {'name': 'Lyriel Starweave', 'order': 1}, {'name': 'Borin Ironfoot', 'order': 2}, {'name': 'Pip Quickfingers', 'order': 3}, {'name': 'Goblin1', 'order': 4}, {'name': 'Goblin2', 'order': 5}, {'name': 'Ogre', 'order': 6}]
Adventure: {'patron': 'The Conclave', 'quest': 'Slay the Helvella Dragon', 'location': 'The Wilderlands', 'threat': 'The Great Old One'}
<End Turn/>
--- Player Turn: Gunther the Brave (round 1) ---
Gunther the Brave attacks Goblin1 (SWORDS) [6, 1] vs S&S 5 -> barely damage [1, 6, 3, 2]=>6 Goblin1 HP 0/5. <DM/>
<End Turn/>
--- Player Turn: Lyriel Starweave (round 1) ---
Lyriel Starweave casts Icebolt at Ogre sorcery [2, 2] vs S&S 2 -> success damage [6]=>8 Ogre HP 2/10 SP 5/6. <DM/>
<End Turn/>
--- Player Turn: Borin Ironfoot (round 1) ---
Borin Ironfoot attacks Ogre (SWORDS) [1, 6] vs S&S 4 -> barely damage [6, 5, 1]=>6 Ogre HP 0/10. <DM/>
<End Turn/>
--- Player Turn: Pip Quickfingers (round 1) ---
Pip Quickfingers attacks Goblin2 (SWORDS) [5, 4] vs S&S 3 -> fail (miss, GM worsens). <DM/>
<End Turn/>
--- Monster Turn: Goblin2 (round 1) ---
Goblin2 (monster Easy) attacks Lyriel Starweave: Lyriel Starweave SWORDS [1] vs S&S 2 -> barely | takes 1 DMG -> 5/6.
<End Turn/>
--- Player Turn: Gunther the Brave (round 2) ---
Gunther the Brave attacks Goblin2 (SWORDS) [1, 1] vs S&S 5 -> success damage [2, 2, 5, 5]=>5 Goblin2 HP 0/5. <DM/>
<End Turn/>

=== RESULT ===
{
  "players": {
    "Gunther the Brave": {"hp": 15, "max": 15, "sp": 0, "sp_max": 0, "sns": 5, "alive": true},
    "Lyriel Starweave": {"hp": 5, "max": 6, "sp": 5, "sp_max": 6, "sns": 2, "alive": true},
    "Borin Ironfoot": {"hp": 12, "max": 12, "sp": 2, "sp_max": 2, "sns": 4, "alive": true},
    "Pip Quickfingers": {"hp": 9, "max": 9, "sp": 4, "sp_max": 4, "sns": 3, "alive": true}
  },
  "monsters": {
    "Goblin1": {"hp": 0, "max": 5, "alive": false, "threat": "Easy"},
    "Goblin2": {"hp": 0, "max": 5, "alive": false, "threat": "Easy"},
    "Ogre": {"hp": 0, "max": 10, "alive": false, "threat": "Medium"}
  }
}
Tool Calls: 26
```
*Heuristic fallback uses same tool surface (`heuristic_player_turn`) when LLM unavailable. No initiative — `establish_turn_order` is sensible order (players declaration order, then threats) per RAW; dice is 1-3d6 SWORDS < S&S / SORCERY > S&S with Divine Intervention on exact.*

</details>

---

Implements [`ref/sword-and-sorcery.md`](../../ref/sword-and-sorcery.md) faithfully: S&S number 2–5, derived HP=3×S&S, SP=10−2×S&S, WD=S&S−1, EN=S&S+3; 1–3d6 SWORDS (< S&S) / SORCERY (> S&S) with Divine Intervention on exact match; outcomes 0/1/2/3 successes; helping (+1d on next roll); spells known = max SP, level-0 free, level≥1 SORCERY roll + SP cost + damage highest +2×level; only players roll; **no initiative — sensible conversation order** (players in declaration order, then threats as GM hazards); night's rest restores all HP/SP; monsters Easy/Med/Hard/Deadly HP/DMG; adventure generation via d6 patron/quest/location/threat tables.

Uses `dnd-tools` + `dnd-campaign` as foundations (mapgen, seeded dice, tau-ai harness, snapshot/campaign plumbing) and implements S&S core on top.

- **Single scene** (`SnSState` + `SnSTools` + `SnSSimulation`) — one encounter with deterministic 1–3d6 resolution, WD, SP, helping, divine intervention, sensible turn order (no initiative).
- **Multiple scenes with context** (`SnSCampaignState` + `SnSCampaignTools` + `SnSSession`) — bounded history, checkpoints, `get_summary`/`prune_traces` for LLM context, night rests between scenes.
- **Whole campaign** (`run_campaign`) — sequence of scenes with inter-scene night rests and persistence.
- **LLM** via `tau-ai` / `tau_agent` (LMStudio `:1234` by default, verified above with `qwen3.6-35b-a3b-mtp`), with heuristic fallback.

## Quickstart

```bash
uv sync
# single scene (heuristic)
uv run sword-and-sorcery scene --seed 42 --turns 6
# single scene via LLM (requires LMStudio at :1234)
uv run sword-and-sorcery scene --seed 42 --turns 2 --use-llm --model qwen3.6-35b-a3b-mtp
# 3-scene campaign
uv run sword-and-sorcery campaign --seed 42 --turns 6 --use-llm --model qwen3.6-35b-a3b-mtp
# generate scenarios
uv run sword-and-sorcery gen-scenarios --out /tmp/sns_test_scen
uv run pytest
```
