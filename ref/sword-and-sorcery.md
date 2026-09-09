# Swords & Sorcery — Core System Rules (Implementation Condensed)

> **An OSR Fantasy Hack of *Lasers & Feelings*** — v1.1 (2020) by James Lennox-Gordon ([UnknownDungeon.itch.io](https://unknowndungeon.itch.io/swords-and-sorcery)) — **CC BY-SA 4.0**. Hack of John Harper's *Lasers & Feelings*. Layout template by Nathanaël Roux (barkalotdesigns.com); graphics by Freepik and Lorc.
> Source PDF: `ref/sword-and-sorcery.pdf` (single-page A4, landscape). Condensed below for LLM + tool-grounded implementation from the PDF text layer (`pdftotext -layout -raw` verified) and the live implementation in `packages/sword-and-sorcery/` (`src/sword_and_sorcery/models.py:1`, `dice.py:1`, `state.py:1`, `tools.py:1`, `prompts.py:1`, `simulation.py:1`).
> Reference sources consulted 2026-09-09: PDF text layer for Create Adventurers / Derived Attributes / Magic / Rolling the Dice / Divine Intervention / Helping / Running the Game / Spells & Monsters / Adventure Generator; `packages/sword-and-sorcery` for authoritative tool schemas and deterministic dice. *Lasers & Feelings* SRD (John Harper) via the same dice engine. Swords & Sorcery™ inherits the Lasers & Feelings CC BY 4.0 lineage via CC BY-SA 4.0.

---

## 1. System Overview

### Why Lasers & Feelings / Swords & Sorcery — And the AI Fix

A single number (`2–5`) plus one die mechanic covers the whole game. That minimalism is the fix:

- **One axis, two directions**: SWORDS is `< S&S number` for physicality/fighting/sneaking/intimidation; SORCERY is `> S&S number` for magic/knowledge/insight/persuasion. A higher number = better at SWORDS, worse at SORCERY (`models.py:84` `derived_hp=3*S&S`, `derived_sp=10-2*S&S`). No separate stats to hallucinate.
- **Only players roll** (`ref/sword-and-sorcery.pdf:Running the Game`): if a monster attacks, the *player* rolls to avoid. The LLM GM never rolls — it assigns `prepared / trained` flags and calls the player-facing `roll_check` tool. This makes the tool surface the single source of truth, exactly as the GUMSHOE and Tricube patterns do.
- **Player skill over character skill**: SORCERY is not intelligence; a `5` can solve puzzles as well as a `2`. The GM asks *how* you do it, not whether the sheet permits it — the LLM prompt must solicit the plan before the roll.
- **Narrative gear, lethal arithmetic**: derived `WD = S&S−1` and monster `HP/DMG` (Easy 5/2 … Deadly 30/6) mean combat is short and the LLM cannot soften failure — `0 successes = GM worsens`, `1 = barely with cost`, `2 = good`, `3 = critical + extra`.

### Core Loop

```
Scene framing (GM describes, introduces threat) → Players declare intent (how + SWORDS vs SORCERY)
  → GM sets prepared/trained → roll 1–3d6 vs S&S number (each die < or > S&S, == triggers Divine)
  → 0 fail / 1 barely / 2 success / 3 critical → GM narrates cost or extra effect
  → On helpers: helper rolls first; if that roll succeeds target gets +1d on the next roll (tools.py:help)
  → Magic: level 1+ requires a SORCERY roll (fail = backlash); success spends SP and rolls level d6 → highest+2*level
  → Attack: SWORDS roll → on success WD d6s → highest is damage vs monster HP; monster turn is a player SWORDS avoidance roll
  → Rest: night's rest restores all HP/SP (tools.py:night_rest)
```

The repo implements the **scene** loop plus a minimal **adventure** wrapper (Patron/Quest/Location/Threat `d6×4`) and a grid-aware campaign layer that reuses `dnd_tools.mapgen`/`dnd_campaign.state` patterns for positioning/LoS even though RAW has no map.

---

## 2. Characters

### 2.1 Creation Checklist

1. **Ancestry**: Human, Elf, Dwarf, Gnome, Orc, Catfolk, or make one up (`models.py:16` `ANCESTRIES`).
2. **Background**: Noble, Sage, Thief, Soldier, Tracker, or Entertainer (`models.py:17` `BACKGROUNDS`).
3. **S&S Number**: Roll `1d6` rerolling `1` and `6` until `2–5` (or GM lets you choose). Higher = better at SWORDS, worse at SORCERY (`models.py:101` `roll_sns_number`).
4. **Derive attributes** (`models.py:84`):

| Derived | Formula | Example S&S 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| **HP** max = `3 × S&S` | `state.py:186` `update_hp` tracks `0 → unconscious` | 6 | 9 | 12 | 15 |
| **SP** max = `10 − 2×S&S` (Spirit) | `state.py:221` `update_sp`; spent on cast success | 6 | 4 | 2 | 0 |
| **WD** = `S&S − 1` (Weapon Damage dice) | `dice.py:69` `roll_weapon_damage` rolls WD d6 take highest | 1 | 2 | 3 | 4 |
| **EN** = `S&S + 3` (Encumbrance, items carried) | `models.py:97` | 5 | 6 | 7 | 8 |

5. **Spells known** = `max SP` distinct picks from the Spells table (§5). Level-0 at-will; level 1+ require SORCERY rolls (§3). If not set, `models.py:154` assigns first `max SP` in table order (`Illuminate, Telepathy…`).
6. **Name** — cool fantasy adventurer name e.g. *Gunther the Brave*; optionally draw a picture.

`SP 0` is legal (S&S 5 fighter): you know zero spells, but see Lucky / Divine paths — you can still roll SORCERY for knowledge, just not cast levelled spells. `EN` is narrative in this implementation (`state.py` does not gate inventory, but `check_character` surfaces `en`/`inventory`).

### 2.2 S&S Number Distribution

`2–5` uniform if you use the reroll rule; `2` is the best sorcerer (`HP 6 / SP 6 / WD 1`), `5` the best swordsman (`HP 15 / SP 0 / WD 4`). The choice trades `HP+WD+EN` against `SP+spell access` directly — the LLM cannot earn both.

---

## 3. Rolling the Dice

Over the one-page spread the die graphic places `2 ——— 5` on a SWORDS ↔ SORCERY line. The mechanic is:

> When you do something which is possible but could fail, roll **1d6** to find out how it goes. Roll **+1d if you're prepared** and **+1d if you're trained**. The GM tells you how many dice to roll, based on your character and the situation (1–3d6).

### 3.1 Which Way to Roll

Roll and compare **each die** to your **S&S number** (`dice.py:17` `roll_sns_check`):

| Using | Want | Comparison | Example S&S 3 |
|---|---|---|---|
| **SWORDS** (physical, fighting, sneaking, intimidation) | Roll **under** | `die < S&S` counts as success | `1,2` succeed; `3` = Divine; `4,5,6` fail |
| **SORCERY** (magic, knowledge, insight, persuasion) | Roll **over** | `die > S&S` counts | `4,5,6` succeed; `3` = Divine; `1,2` fail |

Exactly equal is **Divine Intervention** — counts as a success but flagged separately (§3.3).

### 3.2 Dice Count

`state.py` / `tools.py:_dice_count` caps at `1–3d6` via GM flags:

- Base `1d6`.
- `+1d` if **prepared** (situational advantage you set up).
- `+1d` if **trained** (background/ancestry justifies it; `simulation.py:197` marks Thief/Tracker/Soldier trained on defense, Sage on sorcery, etc.).
- `+1d` via **helping** (§3.4, `state.py:87` `_pending_help`).
- Never more than `3d6`; never fewer than `1d6`. `dice.py:36` enforces `1–3`, `models.py` has no separate scope penalty — scope is narrative here (unlike Tricube's `−1 die`).

### 3.3 Outcomes (`dice.py:49` `outcome`)

| Successes (`# dice that met the comparison`) | Label | Result (PDF verbatim) |
|---|---|---|
| **0** | Goes wrong | GM says how things get worse somehow. |
| **1** | Barely manage | GM inflicts a complication, harm, or cost. |
| **2** | Do it well | Good job! |
| **3** | Critical success | GM tells you some extra effect you get. |

The GM **must** worsen on `0`; the LLM cannot narrate a lateral stall. On `1` the success stands but costs (`HP`/`SP`/position); on `3` the GM adds a player-facing benefit. Monster `DMG` is only applied on the player's `0/1` branch (`simulation.py:202` — `0→full DMG`, `1→half rounded up`, `2→no damage`).

### 3.4 Divine Intervention (`dice.py:43` `divine`, `tools.py:282` `divine_intervention`)

If **any** rolled die equals your S&S number exactly:

- The roll **still counts as a success** for that die.
- A deity/otherworldly being grants **special insight** — ask the GM a question; they answer **honestly**.
- You **may change your action and roll again** instead of accepting the success (tool records via `divine_intervention(character, question)`).

Good questions (PDF list, preserved verbatim): *What are they really feeling? Who's behind this? How could I get them to do what I want? What should I lookout for? What's the best way to do this thing? What's really going on here?*

Implementation flags `divine_intervention: bool` per roll; `simulation.py:208` automatically inserts a `divine_intervention("What should I lookout for?")` trace for monster defenses and the player heuristic proactively asks after an exact.

### 3.5 Helping (`tools.py:254` `help`)

If you want to help someone who is rolling, say **how** you help and **make a roll**:

1. Helper picks an ability (`swords`/`sorcery`) + own `prepared`/`trained`.
2. Helper rolls `1–3d6` vs their own S&S.
3. If they **succeed** (`≥1 success`), the **target gets `+1d` on their next roll** (capped at `3d6`; `state.py:87` `_pending_help[target]` = `min(2, existing+1)`). If helper fails, nothing granted.

Only one help bonus per target per roll in this implementation (additional helpers overwrite/extend pending but cap ensures `max total = 3d6` after base+prepared+trained). The GM validates the narrative coupling — e.g. "*I brace the door while you pick the lock — SWORDS?*".

---

## 4. Magic

`models.py:55` and §3 rules:

- You **know a number of spells equal to your maximum SP** (`sp_max`).
- Casting a **level 1+** spell **requires a SORCERY roll** (same dice count rules). **If you fail, something bad and magical happens** (GM backlash — no SP charged). On success, **reduce current SP by the spell's level**.
- **Level-0 spells require no roll and cost no SP**: `Illuminate, Telepathy, Mend, Minor Illusion`.
- Damage or heal (including `Heal`): roll a number of **d6s equal to the spell's level**, take the **highest**, deal damage or heal equal to **roll + 2×level** (`dice.py:79` `roll_spell_damage`). **May be split between multiple close targets** (`tools.py:419` `targets: list[str]` — GM narrates split).
- Continuous effects **last one minute** (`tools.py:378` — `level 0` note).

**Rest**: night's rest restores **all HP and SP** (`state.py:233` `night_rest`).

---

## 5. Spells & Monsters

### 5.1 Spells (`models.py:55` `SPELL_TABLE`)

| Level | Spells | Roll? | Cost |
|---|---|---|---|
| 0 | `Illuminate, Telepathy, Mend, Minor Illusion` | No | 0 SP |
| 1 | `Beast-Speak, Icebolt, Friendship, Grease` | SORCERY | 1 SP |
| 2 | `Heal, Invisibility, Fireball, Resize, Animate` | SORCERY | 2 SP |
| 3 | `Flight, Darkness, Lightning Storm, Summon` | SORCERY | 3 SP |

Implementation normalizes via `models.py:72` `SPELL_LEVEL` (case-insensitive); `tools.py:343` `cast_spell(caster, spell, level?, prepared, trained, targets?)` looks up `level` if omitted, validates against `ALL_SPELLS`, and on success rolls `level d6s → highest+2*level`.

### 5.2 Monsters (PDF side-by-side table, `models.py:64` `MONSTER_TABLE`)

| Threat | HP | DMG |
|---|---|---|
| **Easy** | 5 | 2 |
| **Medium** | 10 | 3 |
| **Hard** | 20 | 4 |
| **Deadly** | 30 | 6 |

PDF note: *An enemy's spell is a threat by itself, and a trap deals the same damage as a monster.* Use the same `DMG` column for traps/hazards.

`tools.py:504` `set_monster(name, threat, hp?, dmg?)` authorizes the GM to declare a monster per threat tier or with overrides; `state.py:186` `update_hp(name, delta)` handles `0 HP → defeated` (monsters dead) vs players at `0 → unconscious` with one save chance (§6).

### 5.3 Monster Attack Accounting (Only Players Roll)

`simulation.py:165` `_monster_turn` exemplifies the RAW loop: on a monster's turn the *player* rolls SWORDS to **avoid** (`trained` flagged for Fighter-like backgrounds), then the state applies `0→full DMG / 1→half (min 1) / 2→avoid / 3→critical avoid`. The monster never calls `roll_weapon_damage`; the player's avoidance result decides whether `mon.dmg` is applied.

---

## 6. Create a Fantasy Adventure (d6×4)

Roll or choose, each with `1d6` (`models.py:46` / `tools.py:147` `generate_adventure`):

| d6 | Your Patron… | Has Given You a Quest To… | So Adventure Forth Into… | But Beware… |
|---|---|---|---|---|
| 1 | Mage-King Tholex XI | Slay the Helvella Dragon | The Wilderlands | The Necromancer |
| 2 | Lord Garrington | Destroy the ancient seal | The Undercity | Cultists |
| 3 | The Hunters' Guild | Investigate a murder | Tanglewood | Archduke Tallan |
| 4 | Wizard Nimdronde | Recover the **Lǎo Mei** | The Planegate | The Queen of Wasps |
| 5 | The Thieves' Guild | Deliver some **Wyldfyre** | **Fröstfell** | The One-Eyed Prince |
| 6 | The Conclave | Capture the bandits | The Fissure | The Great Old One |

Diacritics per clean PDF layer: **Lǎo Mei**, **Wyldfyre**, **Fröstfell** (`Notes on this Markdown` — `pdftotext -raw` duplicate `wildfire`/`Frostfell` is an artefact). Hooks are intentionally generic; the LLM expands them into scenes without adding hidden stats.

---

## 7. Running the Game

- **The game is a conversation** (PDF): describe the scene, introduce a threat (monster/trap/hazard/ritual), ask *what do you do*, resolve in **sensible order** and **ask for rolls only when uncertain** (`prompts.py:6` `GM_PROMPT`).
- **Player skill over character skill**: "*SORCERY is not intelligence, and a character with S&S 5 can be just as smart — and help solve problems — as one with S&S 2*." Ask players how they disarm traps, sweet-talk guards, route around wards; roleplay persuasion rather than gate it behind SORCERY.
- **Only players roll dice.** If a monster attacks, ask the players what they are doing. If they fail, they take damage or are put in a worse situation (`simulation.py:193`).
- **Turn order**: RAW has **no initiative**. Use conversation order: *players in declaration order, then threats as framed hazards* (`state.py:158` `establish_turn_order`; `tools.py:480` `establish_turn_order` — `roll_initiative` kept as deprecated alias for compat). Do not invent a `1d6+mod` initiative.
- **Death & unconsciousness**: at `0 HP` a PC is **knocked unconscious** and allies have **one chance to save before death** (`state.py:186` — `hp 0 → unconscious True + death_log entry`). The next turn label is `(unconscious — save chance)` (`simulation.py:229` — `roll_check(..., trained=True)`; success `hp→1` and clears unconscious, fail `alive→False`). Monsters at `0 HP` are simply defeated.
- **Encumbrance**: `EN = S&S+3` caps items narratively; not enforced by tool gate (surfaced via `check_character` for GM audits).

---

## 8. Example Play

```
GM: The Wilderlands road is blocked — two cultists chant beside a humming crystal that looks a lot like Wyldfyre.
Ari (Catfolk, Thief, S&S 2, HP 6, WD 1, SP 6): "I slip between the rocks and get behind them."
GM: Give me a SWORDS roll — you're trained to sneak, not prepared. So 2d6.
Ari: *roll_swords(prepared=False, trained=True) → rolls [2,5] vs S&S 2 → SWORDS wants <2, so only 1 counts; no Divine; 1 success → barely.*
GM: You barely manage — you get behind them, but a loose stone clatters. One turns.
Bren (Human, Soldier, S&S 5, HP 15, WD 4): "I charge the crystal while Ari distracts — I'm trained and my friend just helped."
Ari: *help(helper=Ari, target=Bren, ability=swords) → Ari SWORDS [1,6] vs 2 → 1 success → Bren gets +1d pending*
GM: Bren, you're prepared (you ran) and trained (Soldier) plus help → 3d6.
Bren: *roll_check(swords, prepared=True, trained=True) → [4,2,5] vs 5 → all <5 → 3 successes → critical!* Extra: you slam the crystal and it cracks.
GM: Monster turn — cultist slashes at Ari. Ari, what do you do?
Ari: "I duck — SWORDS!"
Ari: *roll_check(swords) → [2] vs 2 → equals S&S → Divine Intervention!* (1 success + flag)
GM: Divine: a cold wind carries a whisper — "They fear the water." You may keep the dodge or change action.
Bren (S&S 2 sage offshoot): "I try Friendship to turn one cultist — SORCERY, trained?"
GM: Trained (Entertainer). Roll 2d6.
Bren: *cast_spell(spell=Friendship, level=1) → SORCERY [5,6] vs 2 → both >2 → 2 successes → spell succeeds, costs 1 SP (6→5).*
     Effect: not damage, so GM narrates the cultist hesitating. Night's rest later will restore all HP/SP.
```

---

## 9. Implementation with `dnd-tools` + `dnd-campaign` via LLMs

> Goal: keep paper `packages/dnd-tools` **untouched** for metrics fidelity; build S&S as an additive mode on top, with `dnd-campaign` handling multi-scene horizons. Both packages expose **tool-grounded** LLM loops via `tau-ai` / `tau_agent`.

### 9.1 Architecture

```
packages/dnd-tools/src/dnd_tools/        # paper-faithful, frozen semantics
  models.py   Character, Weapon, SpellDef, Cell, Buff, ResistEntry
  dice.py     seeded RNG, roll_dice("2d20kh1"), roll_with_parts
  state.py    GameState — HP/pos/initiative/LoS/death_log/tool_trace
  tools.py    Tools — 30+ typed tools + OpenAI schemas + dispatch()
  agents.py   Tau provider/harness, run_tau_player_turn_sync(), heuristic fallback
  simulation.py  Scenario generation (27) + Simulation loop
  prompts.py  GM_PROMPT / PLAYER_PROMPT
  mapgen.py   indoor (JSON rooms) / outdoor (procedural)
  cli.py      dnd-tools demo / gen-scenarios / run-scenario / eval

packages/dnd-campaign/src/dnd_campaign/  # long-horizon wrapper, never edits dnd-tools
  state.py    CampaignState — wraps GameState; snapshots/history/save-load/short+long rest/prune
  tools.py    CampaignTools — delegates all Tools + adds campaign tools
  memory.py   summarize_state(), compact_transcript() — bounded LLM context
  session.py  CampaignSession — multi-encounter orchestration
  cli.py      dnd-campaign demo

packages/sword-and-sorcery/src/sword_and_sorcery/  # additive S&S package
  models.py   SnSCharacter (ancestry/background/sns/hp/sp/wd/en/spells/inventory),
              SnSMonster (threat/hp/dmg), SPELL_TABLE/MONSTER_TABLE/ADVENTURE_TABLES
  dice.py     seeded RNG helpers: roll_sns_check(sns, swords|sorcery, 1-3d6),
              roll_weapon_damage(wd), roll_spell_damage(level), roll_d6
  state.py    SnSState (map 20×20, players/monsters/pos, establish_turn_order, update_hp/sp,
              night_rest, distance/LoS, log_tool), SnSCampaignState (snapshot/restore/prune)
  tools.py    SnSTools — ~25 typed tools (see §9.5) + OpenAI schemas + dispatch();
              SnSCampaignTools wrapper (long_rest = night_rest, checkpoint, save/load)
  prompts.py  GM_PROMPT / PLAYER_PROMPT — RAW conversation, only-players-roll, sensible order
  agents.py   Tau harness wrappers + heuristic (greedy nearest foe, check LoS, help before roll)
  simulation.py SnSSimulation — scene init (indoor/outdoor), turn loop, monster-as-player-roll
  session.py  CampaignSession — multi-scene orchestration via SnSCampaignState
  memory.py   summarize_state(), compact_transcript() — bounded LLM context
  cli.py      sword-and-sorcery / sns demo / gen-scenarios
```

No file under `dnd-tools/` is edited for S&S. The `sword-and-sorcery` package is a workspace member (`pyproject.toml:1` `members = ["packages/*"]`, `sword-and-sorcery` declares `dependencies = [dnd-tools, dnd-campaign, tau-ai]`).

### 9.2 New Models (additive, isolated)

```python
# packages/sword-and-sorcery/src/sword_and_sorcery/models.py  (actual, trimmed)

from dataclasses import dataclass, field

ANCESTRIES = ["Human","Elf","Dwarf","Gnome","Orc","Catfolk"]
BACKGROUNDS = ["Noble","Sage","Thief","Soldier","Tracker","Entertainer"]
PATRONS = ["Mage-King Tholex XI", ...]   # d6 table
QUESTS  = ["Slay the Helvella Dragon", ...]
LOCATIONS = ["The Wilderlands", ...]     # includes Fröstfell
THREATS = ["The Necromancer", ...]
SPELL_TABLE: dict[int, list[str]] = {0:[...],1:[...],2:[...],3:[...]}
MONSTER_TABLE: dict[str, dict] = {"Easy":{"HP":5,"DMG":2},"Medium":{"HP":10,"DMG":3},"Hard":{"HP":20,"DMG":4},"Deadly":{"HP":30,"DMG":6}}

def derived_hp(sns:int) -> int: return 3*sns
def derived_sp(sns:int) -> int: return 10 - 2*sns
def derived_wd(sns:int) -> int: return sns - 1
def derived_en(sns:int) -> int: return sns + 3
def roll_sns_number(rng=None) -> int:  # 1d6 reroll 1 & 6 until 2-5
    ...

@dataclass
class SnSCharacter:
    name: str; ancestry: str = "Human"; background: str = "Soldier"; sns: int = 3
    hp: int = 0; hp_max: int = 0; sp: int = 0; sp_max: int = 0; wd: int = 0; en: int = 0
    spells_known: list[str] = field(default_factory=list)
    inventory: list[str] = field(default_factory=list)
    pos: tuple[int,int,int] = (0,0,0); alive: bool = True; unconscious: bool = False
    # help gating
    _help_bonus: int = 0

@dataclass
class SnSMonster:
    name: str; threat: str = "Medium"; hp:int=0; hp_max:int=0; dmg:int=0
    pos: tuple[int,int,int] = (0,0,0); alive:bool=True; is_player:bool=False
```

Map to existing `Cell/Character` where possible: `SnSState` reuses `dnd_tools.models.Cell` and `dnd_tools.dice.seed` for determinism, but keeps a parallel `SnSState` rather than patching `GameState` fields (`ac/initiative_order` alias to `turn_order`/`initiative_order` for compat, but no `1d20`).

### 9.3 Dice Engine Extension (`dice.py`)

Add deterministic helper seeded by `SnSState.seed` via `dnd_tools.dice.seed`:

```python
def roll_sns_check(sns:int, mode:str, dice_count:int=1) -> dict:
    rng = _rng()  # dnd_tools.dice._rng
    rolls = [rng.randint(1,6) for _ in range(dice_count)]
    successes, divine = 0, False
    for r in rolls:
        if r == sns:
            divine = True; successes += 1
        elif (mode=="swords" and r < sns) or (mode=="sorcery" and r > sns):
            successes += 1
    outcome = {0:"fail",1:"barely",2:"success",3:"critical"}[successes]
    return {"rolls":rolls, "sns":sns, "mode":mode, "successes":successes,
            "success":successes>=1, "divine_intervention":divine, "outcome":outcome}
```

Also `roll_weapon_damage(wd)` = `wd d6` keep max, `roll_spell_damage(level)` = `level d6` highest + `2*level`, `roll_d6(n)` — all via the same `_rng` for seed fidelity. Keep existing `roll_dice()` for 5e paths.

### 9.4 GameState / CampaignState Additions

**`state.py : SnSState`** — replaces 5e `GameState` for S&S scenes:
- `map` is `20×20` by default, each cell `5ft` for `distance_feet(a,b)` and `z` for height-aware `line_of_sight(a,b)` (reuses `dnd_tools` LOS math).
- `update_hp(name, delta)` encodes `0 HP → unconscious` + `death_log`, with a single save chance on the next turn (`hp 0 + unconscious → second 0 ⇒ dead`). `alive` gates until explicit death.
- `update_sp(name, delta)` with bounds; `night_rest(names?)` restores all HP/SP and clears unconscious.
- `establish_turn_order()` = RAW sensible order (`players` in declaration order, then `monsters`); `turn_order`/`initiative_order` aliases + `current_turn_idx`/`round` for trace compat.
- `log_tool`/`transcript` mirror `dnd_tools.state.GameState` shape for `metrics.py`.

**`state.py : SnSCampaignState`** — already wraps `SnSState`:
- `snapshot()`/`restore()` serialize `players/monsters/pos/map/turn_order/round/death_log/adventure/campaign_meta` plus `seed`; re-seeds dice on restore.
- `history` is a bounded ring (`max_history` 100); `save(path)`/`load(path)` persist `snapshot` + tail `tool_trace`/`transcript`.
- `long_rest(name?)` → `night_rest` (full HP/SP); `short_rest` is a narrative no-op (`short_rest` kept for compat but notes "S&S has only night rest").
- `checkpoint()`/`prune_traces(keep_last=200)` unchanged — call between scenes to bound LLM context (`[:10]+[-keep_last:]`).

### 9.5 Tool Schemas (LLM-visible)

**Scene-level `SnSTools`** (each logs to `state.log_tool` and returns JSON; `dispatch(name, args)` matches `tools.py:883`):

| Tool | Purpose | Key params |
|---|---|---|
| `check_character(name)` | Sheet: ancestry/background/S&S + derived HP/SP/WD/EN + spells/inventory/pos/alive/unconscious | `name` |
| `check_monster(name)` | Monster: threat/HP/DMG/pos/alive | `name` |
| `check_hp(name)` | `hp/max/alive/unconscious` | `name` |
| `check_sp(name)` / `check_sns(name)` | SP pool and S&S + derived block | `name` |
| `check_valid_attack_line(a,b)` / `check_distance(a,b)` | Grid+height LOS vs feet | `a,b` |
| `list_spells(level?)` / `list_monster_table()` | Tables from PDF | `level?` |
| `generate_adventure()` | Roll `patron/quest/location/threat` (d6 each), sets `state.adventure` | — |
| `move_player(name,x,y)` / `move(name,x,y)` / `visualize_map()` | Grid movement/LoS map | `name,x,y` |
| `roll_check(character, ability swords|sorcery, prepared, trained)` | **Authoritative 1–3d6** vs S&S: returns `rolls/successes/divine/outcome + outcome_desc` | `character`, `ability`, `prepared`, `trained` |
| `roll_swords / roll_sorcery` | Aliases for `roll_check` | `character` |
| `help(helper,target, ability, prepared, trained)` | Helper rolls vs own S&S; on success target gets `+1d` next roll (`_pending_help`) | `helper`,`target`,`ability` |
| `divine_intervention(character, question)` | After exact-equals: ask honest GM question; may change action and reroll | `character`,`question` |
| `attack(attacker, defender, prepared, trained)` | SWORDS roll then `WD d6s keep max` damage vs defender HP | `attacker`,`defender` |
| `cast_spell(caster, spell, level?, prepared, trained, targets?)` | Level `0` auto/no cost; `1+` SORCERY roll → fail = backlash/no SP, success = `SP−=level` + `highest+2*level` split | `caster`,`spell`,`level?`,`targets?` |
| `heal_spell(caster,target,level?)` | Shortcut for Heal (default lv2) | `caster`,`target` |
| `update_hp / update_sp` | Direct pool deltas (2/day rest vs night rest) | `name,delta` |
| `night_rest(names?)` | Full restore all HP/SP; clears unconscious | `names?` |
| `establish_turn_order()` / `roll_initiative()` | Sensible order (deprecated alias) | — |
| `end_turn(character)` / `print_death_log()` / `set_monster(name,threat,hp?,dmg?)` | Bookkeeping/GM monster declarer | `name,threat` |

**Campaign tools** (`SnSCampaignTools`):

`long_rest(name?)` (=`night_rest`), `short_rest(name)` (no-op note), `checkpoint()`, `save_checkpoint(path)`, `load_checkpoint(path)`, `get_summary()` (compact state for prompt), `prune_traces(keep_last)`.

All tools expose `tool_schemas()` → OpenAI-compatible `{type:"function", function:{name,description,parameters}}` (see `tools.py:523`).

### 9.6 Agent Prompts & Harnesses

Reuse `dnd_tools.agents` pattern verbatim — **never subprocess, never raw LLM strings as truth**:

```python
# prompts.py — GM_PROMPT / PLAYER_PROMPT verbatim (truncated for reference)
GM_PROMPT = """You are the Guild Manager ... Only players roll ... sensible order ... etc."""
PLAYER_PROMPT = """You play as a Swords & Sorcery adventurer ... Sense → Plan → Validate → Act → Communicate ..."""
```

Wire via `agents.py:_tools_to_agent_tools()` + `AgentHarness` (`OpenAICompatibleProvider` for LMStudio at `:1234`):

```python
from dnd_tools.agents import make_tau_provider, _tools_to_agent_tools
from tau_agent.harness import AgentHarness, AgentHarnessConfig

tools = SnSTools(state)  # or SnSCampaignTools(SnSCampaignState(...))
provider = make_tau_provider("http://127.0.0.1:1234/v1", "lm-studio")
harness = AgentHarness(AgentHarnessConfig(
    provider=provider, model="qwen3.6-35b-a3b-mtp",
    system=GM_PROMPT, tools=_tools_to_agent_tools(tools), max_turns=6,
))
```

**Simulation loop** (`simulation.py : SnSSimulation`): keep `Simulation.run()` sensibility — `establish_turn_order` → `generate_adventure` (optional) → per-turn `check_character` → (optional `move` toward target) → `check_valid_attack_line` → `roll_check`/`attack`/`cast_spell` (`help` before roll, `divine_intervention` after exact) → `update_hp/sp` → `night_rest` between scenes → `<End Turn/>`. Monster turns are **not** LLM-attack rolls; they trigger **player avoidance** `roll_check(swords)` → `0→full DMG / 1→half / 2→avoid` (`simulation.py:198`). Campaign `Session.add_encounter()` initializes S&S parties + adventure, `run_encounter()` delegates to `SnSSimulation`, then `checkpoint()` + `prune_traces()`.

### 9.7 Determinism & Evaluation

- **Seeded RNG**: all `1d6/WD/spell` via `dnd_tools.dice.seed(seed_val)` derived from `SnSState.seed` / `SnSCampaignState` snapshot; re-seed on `restore()`.
- **Authoritative state**: narration never overrides tool results; `0 → worsens`, `1 → barely with cost`, `2/3 → success/critical`, `exact → Divine flag` are enforced by `dice.py` + `state.update_hp/sp` gates. Tools are isolation boundary (return `error` not raise on obvious misuse — harness catches).
- **Traces**: every tool call logs to `state.tool_trace` with `{tool,args,result,round,actor}` — same shape as 5e for `metrics.py` (`function_usage`, `acting_quality`, `tactical_optimality` heuristics remain valid; SnS simply scores `0/1/2` outcomes differently).
- **Heuristic fallback**: `agents.py:heuristic_player_turn()` mirrors the paper's greedy policy but for S&S: pick nearest foe, check LoS, `help` if ally nearby and S&S favors, then `attack` (trained if your background suggests it) or `cast_spell` if you have SP and a target in range, preferring `roll_check` for utility.

### 9.8 Minimal CLI Wiring

```python
# sword-and-sorcery/cli.py pattern (also exposed as `sns`)
# sns demo --seed 42 --turns 10 [--use-llm --model qwen3.6-35b-a3b-mtp] [--map indoor|outdoor]
# sns gen-scenarios --seed 42 --out scenarios  # 27 like dnd but 3×3×3 S&S flavor
# sns run-scenario scenarios/sns_scenario_01.json --turns 10
```

Reuse `dnd_tools.cli` arg parsing; `llm = LLMClient` alias → `TauLLM(provider, model)`. Hook mapgen: `make_indoor_map(seed)` / `make_outdoor_map(seed)` from `dnd_tools.mapgen`.

### 9.9 What *Not* to Port

- Do **not** reintroduce D&D AC/initiative/`1d20kh1` (`roll_check` *is* the entire engine; `roll_initiative` is deprecated to sensible order).
- Do **not** gate puzzles behind SORCERY — keep RAW "*player skill over character skill*" (the GM prompt explicitly tells the LLM to ask *how*).
- Keep `EN` narrative; full inventory simulation is phase-2.
- Tactics-style `stride/knacks/minions` are not imported — S&S threats stay as `HP/DMG` + spell threats; per-encounter `generate_adventure` is flavour, not a full hex-crawl.

---

## 10. Challenge Resolution Flow (pseudocode, deterministic)

```python
# GM pre-assign
dice_count = 1 + prepared + trained + help_bonus  # capped 1..3
# authoritative roll
r = roll_sns_check(sns, ability)  # ability = swords (<) or sorcery (>)
# outcome mapping is authoritative
if r.divine_intervention:
    divine_intervention(character, question="What's really going on here?")
    # player may optionally: r = roll_sns_check(sns, new_ability)  # change action
if r.outcome == "fail":          # 0
    gm_worsens()                 # monster DMG if monster turn, or trap DMG, or narrative cost
    if monster_turn:
        defender_hp -= monster_dmg  # via update_hp
elif r.outcome == "barely":      # 1
    gm_costs()                   # e.g. monster DMG//2, or complication
    if attack and r.success:
        dmg = roll_weapon_damage(wd)["damage"]  # still counts as success → damage
elif r.outcome in ("success","critical"):  # 2,3
    if attack:
        dmg = roll_weapon_damage(wd)["damage"]  # WD d6s keep highest
        defender_hp -= dmg
    elif cast_spell and level>=1 and r.success:
        if r.success:
            sp -= level
            dmg = roll_spell_damage(level)["total"]  # highest+2*level, split if needed
    if r.outcome == "critical":
        gm_extra_effect()       # e.g. disarm, extra info, free help
```

```
# Helping — declared BEFORE the next check
helper_roll = roll_sns_check(helper_sns, ability)
if helper_roll.success:
    _pending_help[target] = min(2, _pending_help.get(target,0)+1)  # +1d next roll
```

```
# Rest / death
if hp == 0:
    unconscious = True  # death_log: "one chance to save before death"
    # next turn for that character:
    save = roll_sns_check(sns, swords, trained=True)
    if save.success: hp = 1; unconscious=False
    else: alive=False  # death
if night_rest:  # between scenes or long rest wrapper
    for c in party: c.hp=c.hp_max; c.sp=c.sp_max; c.unconscious=False
```

---

## 11. References

- Source PDF: `ref/sword-and-sorcery.pdf` — "Swords and Sorcery v1_1.pdf" (single-page A4, landscape) — layout verified via `pdftotext -layout -raw`.
- Design thread: James Lennox-Gordon / UnknownDungeon.itch.io — **v1.1, 2020 — CC BY-SA 4.0**; hack of John Harper's *Lasers & Feelings* (CC BY 4.0) — layout Nathanaël Roux, graphics Freepik/Lorc.
- Implementation ground truth: `packages/sword-and-sorcery/src/sword_and_sorcery/models.py:1` (derived formulas, tables), `dice.py:1` (exact success/divine/outcome), `state.py:1` (HP/SP unconscious + night rest + turn order), `tools.py:1` (schemas + `roll_check/help/divine_intervention/attack/cast_spell`), `prompts.py:1` (GM only-players-roll + sensible order contract), `simulation.py:1` (monster-as-player-avoidance, help/divine flow, unconscious save, `SnSSimulation.run`).
- Paper frame: `ref/31_Setting_the_DC_Synthesis.md` — DC-setting evaluation frame this implementation extends (initiative/LoS/tool-trace audit lineage).
- Cross-system precedents: `ref/tricube-tales.md` / `ref/tricube-tactics.md` / `ref/fate-core.md` / `ref/gumshoe-srd.md` — architecture/prompt/harness/tool-trace patterns reused.

---

## 12. Notes on this Markdown

- Reformatted from `Swords and Sorcery v1_1.pdf` using `pdftotext -layout` / `-raw` verification. Excessive whitespace, duplicate layered text, and bullet-vs-table rendering from the auto-conversion have been corrected.
- Diacritics preserved as in the clean layer: **Lǎo Mei**, **Wyldfyre** (capital W), **Fröstfell** (ö). A lower duplicate layer renders these as `wildfire`/`Frostfell` — treated as artefact and omitted.
- The central S&S scale graphic (SWORDS ↔ SORCERY number line 2–5) is visual only and not transcribed; its mechanic is fully covered by §2–§3.
- No rules were invented for §1–§7; wording is kept verbatim where possible, with only formatting/punctuation/table structure normalised. §9–§10 are additive implementation guidance and are explicitly marked as such.
