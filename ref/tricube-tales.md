# Tricube Tales — Core System Rules (Implementation Condensed)

> Tricube Tales v5 © 2019–2026 Richard Woolcock · CC BY 3.0 — condensed from `tricube-tales.txt`/`.pdf` for LLM + tool-grounded implementation.
> A minimalist, narrative-driven TTRPG: players roll 1–3d6 vs. difficulty 4–6; GM never rolls.

---

## 1. System Overview

### Core Loop
- **Players** roll **1–3d6** vs. difficulty **4–6** (GM-assigned). Only players roll.
- **Success**: ≥1 die ≥ difficulty.
- **Exceptional success**: 2–3 dice succeed → player narrates a benefit / cool outcome.
- **Critical failure**: all dice show `1` → very bad complication (GM narrates).
- **GM role**: assign `trait + difficulty + effort`, describe challenges/NPC actions; never rolls.

### Token Economy
| Token | Represents | Start | Max | Who holds |
|---|---|---|---|---|
| **Karma** | Luck / providence | 3 | 6 (every 2nd advance) | Player, spendable |
| **Resolve** | Health / stamina / determination | 3 | 6 (every 2nd advance) | Player, lost on failed defense |
| **Effort** | NPC resilience / challenge length | varies | — | GM pool per challenge/foe |

### Perks & Quirks
- **Perks** — narrow talents/items/magic/superpowers. Spend **karma** (max 1/challenge) to activate mechanical benefits: reduce difficulty by 1 (retroactively after roll), bypass a challenge without rolling (decide *before* roll), or achieve impossible feats.
- **Quirks** — hindrances declared ***before* rolling**: +1 difficulty; recover **1 karma** (or **1 resolve** if the challenge succeeds). Max 1 quirk/affliction per challenge. GM may also offer karma for a complication tied to a quirk.

---

## 2. Characters

### Creation Checklist
1. **Name + archetype** = `trait` (agile / brawny / crafty) + `concept` (profession/race/descriptor, e.g. `agile elven ranger`, `brawny draconic knight`, `crafty inventor`).
2. One **perk** (e.g. `necromancy`, `cybernetic arms`, `fearless commander`).
3. One **quirk** (e.g. `arrogant`, `peg leg`, `vindictive`).
4. **3 karma + 3 resolve**; gear is narrative unless taken as perk.

### Archetype → Dice Count
| Trait | Rolls **3d6** for | Rolls **2d6** when lacking | Combat style default |
|---|---|---|---|
| **Agile** | Quickness, dexterity, reflexes, stealth, **ranged** combat | any non-agile challenge | ranged |
| **Brawny** | Strength, toughness, athletics, **melee** combat | any non-brawny challenge | melee |
| **Crafty** | Charisma, intellect, willpower, perception, **mental** combat | any non-crafty challenge | mental |

**Out-of-scope penalty**: if challenge requires knowledge outside concept + perks → **−1 die** (so 2d6→1d6, 3d6→2d6). Minimum 1d6.
**Combat style** (melee/ranged/mental) defaults to trait but can be overridden at creation and never changes; used for both attack and defense.

### Karma & Resolve Detail
- Tokens recover during play but never exceed quota for the session (quota grows via advancement).
- **Karma spend timing**: retroactive difficulty −1 after roll (narrate how perk helps); or pre-roll bypass cost for auto-success vs. accessible challenge; or enabling impossible feat.
- **Quirk timing**: declare before roll, describe quirk in narration, +1 difficulty (can push above 6), then recover.

### Perks — Four Usage Modes (GM discretion, deterministic for tools)
1. **Impossible → possible** (no karma): perk lets you *attempt* what others cannot (e.g. lift bus with super-strength) → still roll.
2. **Story impact** (1 karma *before* roll): bypass challenge entirely (e.g. fly over river others swim) or conjure spirit for questioning.
3. **Retroactive edge** (1 karma *after* roll): −1 difficulty, narrate perk help.
4. **Flavour only** (0 karma): describe magic/tech vs mundane alternative that solves same challenge (telekinesis to push door) → no cost.
5. **Assist allies**: `divine healer` etc. may spend karma to cure ally affliction; either helper or target may pay, still max 1/challenge.
- Broadly-defined perks = wider scope but weaker per-instance; narrowly-defined perks = stronger when triggered. Multiple perks can be narrated together but still only 1 karma/challenge.

### Quirks & Complications
- `use_quirk(trait_difficulty+1)` → on resolution fork: failure → +1 karma; success → player chooses +1 karma *or* +1 resolve.
- GM may offer karma for a complication (missed clue, insulted NPC) — tie to quirk when possible.

### Advancement & Rank
- Every **1–3 sessions** (or **100 XP**; 1 XP = 1% of an advance): add **one** of: new perk, new quirk, or convert an affliction → quirk.
- **Every second advance**: instead of perk/quirk, may **+1 karma *or* +1 resolve quota** (max 6 each).
- **Rank** (Hack-and-Slash): PCs start **rank 1**, +1 every **4th advance** (at 4,8,12,16,20 → max 6). NPC rank = GM-chosen. Higher-rank foe → +1 difficulty; lower-rank → −1 difficulty. For 3+ rank gap use **Power Levels** (narrative resolution; collateral resolve loss even if invulnerable).

---

## 3. Challenges

### Basic Resolution (authoritative flow)
1. GM assigns `trait` (agile/brawny/crafty), `difficulty` 4–6 (3/7 only in Tactics, rare), and `effort` tokens if extended.
2. Determine `dice_count` from archetype + scope (3/2/1).
3. Player rolls `dice_count × d6` (individual dice matter, not sum).
4. Count `successes = #{die ≥ difficulty}`. `0` = failure; `≥1` = success; `≥2` = exceptional; `all==1` = critical failure.
5. Each success eliminates **1 effort token** (group of similar foes = one challenge with `N` tokens).
6. Narrate outcome relative to character competence (see §§ below); on failure apply cost (often lose resolve).

### Difficulty Scale
| Die ≥ | Label | Typical use |
|---|---|---|
| 4 | Easy | Crude lock, weak foe |
| 5 | Standard | Most challenges / enemies |
| 6 | Hard | Elite foe, complex task |

### Success & Failure Are Relative
- Neither best nor worst outcome should break believability. Master thief fails simple lock → takes longer/complication, not impossible. Unarmed scholar vs dozen soldiers → best is clean escape, not slaughter. Scholar translating magic text: even exceptional success may yield less than wizard's normal failure.
- There is **always** a cost for failure; otherwise no roll.

### Exceptional Success Benefits
- Player narrates extra benefit. If no effort tokens, GM may grant mechanical benefit such as **−1 difficulty** for another roll (ally or self) — **cannot reduce below 3** (only karma can push 3→2).

### Price of Failure
- Normal failure: spotted sneaking, missed attack, failed climb; may **lose 1 resolve**, or +1 difficulty on next roll, or introduce complication.
- Critical failure (`1,1` or `1,1,1`): very bad, often bad luck; if normal failure = 1 resolve, critical = **2 resolve**. Always narrate interesting complication (tool snaps in lock, foe slams jaw).

### Defeat & Afflictions
- **Defeated** = out of **resolve** (PC) or out of **effort** (challenge/NPC). Victor decides victim's fate.
- At **0 resolve**: gain an **affliction** (`broken arm`, `phobia`, `bruised ego`, `lycanthropy`, etc.), **recover all resolve**, but **cannot participate for remainder of scene** (unconscious/fleeing/too hurt). Resume next scene.
- **>3 afflictions → retired** from play (return only if afflictions cured).
- Afflictions act like GM-triggered quirks (GM decides when they apply); quirks are player-triggered. Death is narrative; GM must warn if failure = death.

### Recovery
- Fleeting afflictions (e.g. `fleeing in fear`) removed end-of-scene automatically.
- Others last hours/days/weeks at GM discretion.
- PC with suitable **perk** may spend **karma** to cure an affliction (e.g. `regeneration`). **Permanent** afflictions (from critical failure) cost **permanent karma** to remove *unless* converted to a quirk via an advance.

### Effort Challenges
- Each die ≥ difficulty removes 1 token; challenge defeated when pool → 0.
- PCs may cooperate (multiple rolls required); **each failed roll has consequences** (resolve loss, complication).
- Group similar enemies: e.g. 6 goblins = one challenge with 6 effort vs. 6 individual 1-effort checks — GM's call.

### Opposed Challenges
- Both sides roll as normal (per their archetype).
- Each treats **other's highest die** as their difficulty (highest roll wins).
- Tie-break: most dice matching difficulty wins as **normal success** (e.g. `5,5,5` beats `5,5,2` beats `5,2,2`). Full tie → interpret as equally favourable.
- Both critical failures → both suffer terrible outcomes.
- NPC vs NPC: GM decides outcome or asks players to roll for them.

---

## 4. Combat (Simple Turn-by-Turn)

> For tactical grid play see `tricube-tactics.md`/`tactics.pdf`. Below is the Tales core.

### NPCs as Challenges
- Assign **difficulty** 4–6 (most = 5) + **effort** pool (1 per foe, or grouped).
- Use **Traits** to modify difficulty: `agile/brawny/crafty` → +1 vs that trait; `clumsy/weak/stupid` → −1. Example: shooting `agile+weak` goblin = 6; hitting in melee = 4.
- **Ranks**: effort ≈ `rank` (boss = `2×rank`, may be +1 rank). Bestiary:

| Creature | Rank | Traits |
|---|---|---|
| Bear | 2 | brawny |
| Dragon | 5 | brawny, crafty |
| Goblin | 1 | agile, weak |
| Golem | 3 | brawny, stupid |
| Lich | 4 | crafty |
| Ogre | 2 | brawny, stupid |
| Kobold/Skeleton | 1 | stupid (+ weak for kobold) |
| Troll | 2 | brawny, stupid |
| Vampire | 3 | agile |
| Wolf/Wraith/Yeti | 1–2 | — / brawny for yeti |
| Zombie | 1 | clumsy, stupid |

- Use common sense for trappings: non-magical arrow vs iron golem = no effect regardless of roll.

### Turn Order & Resolution
- Follow narrative where possible (no strict initiative required; for LLM use rank+2d6 or reuse `roll_initiative` pattern).
- **Players roll to attack** on their turn; **players roll to defend** on enemy's turn.
- **Lose 1 resolve on failed defense**, **2 on critical failure**. Only **one defense roll per turn** — vs. most dangerous attacker if multiple foes.
- Exceptional defense/attack benefits apply as in Challenges.

### Post-Combat
- At 0 resolve → affliction as above; recovered resolve for next scene.
- Gear/vehicles/mounts that are narrative do not add dice; perks/quirks do.

---

## 5. Genre Rules (condensed, all are perk-gated)

### Hack-and-Slash — Traits, Ranks, Effort, Trappings
- As above. Boss = double effort + possibly +1 rank. Apply rank difficulty mod and trait mods cumulatively.

### Magic & Psionics
- As **perks** (`pyromancy`, `geomancy`, `psionicist`). Spending karma enables greater feats. **Narrative only** — if GM calls for agile challenge, mage still resolves as agile even via magic. Broad magic perk → GM asks for a **limitation**:
  - `Destructive` (collateral), `Draining` (spend resolve not karma), `Focus` (wand/staff, days to replace), `Personal` (self only), `Ritualistic` (minutes to prepare, no karma without prep), `Source` (needs nearby energy/matter), `Unsubtle` (gestures/incantations obvious).
- **Fixed spell lists** (optional): choose 3 spells at creation (name + limitation; more limitations = more potent). Learn new spells in play at GM discretion (scrolls, advances).

### Fear & Insanity
- **Crafty 3d6**, others **2d6**; −1 die if no prior exposure to that fear (concept/perks). Failure → **−1 resolve**; 0 resolve → flee or gain mental disorder.

### Superheroes
- Powers = **perks** (e.g. `spider powers`, `iron power suit`). Broad powers take **limitations**: `Devices`, `Grounded`, `Intimidating`, `Negation` (substance), `Non-Offensive`, `Suit-Up`, `Unreliable` (GM may replace karma spend with complication).

### Power Levels
- Extreme mismatches → no roll, narrate. Even invulnerable PCs can lose resolve via collateral (bystanders, humiliation, press).

### Vehicles
- Minor: treat as gear/perk.
- **Major vehicles as characters**: `concept + perk + quirk`, **3 resolve** (no karma), advance at GM discretion. Driver rolls with **own trait** but may use vehicle's concept/perks/quirks as if own. Use Power Levels for starfighter vs dreadnought.

### Sieges & Battles
- Each side maintains token pool. PC commander uses **crafty** challenges to eliminate opposing tokens; difficulty set by relative power/position. Individuals may eliminate tokens but risk own resolve on failed defense.

### Other Subsystems
- **Cybernetics**: background flavour or perk; heavy augmentation → take quirk for physical/psychological drawbacks.
- **Mounts & Minions**: flavour or perk; each 1 minion token if using Tactics supplement.
- **Non-Human Races**: part of archetype (`agile elven ranger`) *or* perk/quirk (darkvision vs outsider) *or* both (GM option: race = perk *and* quirk).
- **Supernaturals (infectious afflictions)**: bite/claw at defeat may inflict `lycanthropy`/`vampire`/`zombie virus` affliction. GM triggers transformations; player may later convert to quirk (control) and buy supernatural perks (`rending claws` — needs limitation like `must shapeshift first`). Cure via story or permanent karma; `amputated leg` quirk can replace `zombie virus` at advance. Gradual decline: future afflictions model slow transformation.

---

## 6. Example Play

```
GM: A heavy door blocks your way.
Mage: Can I open it?
GM: Door solid, lock crude. Easy agile to pick, but outside your
    concept → you lose a die. Or standard brawny to break down.
Mage: I summon a fire elemental with 'pyromancy' and order it to
    incinerate the door — brute force!
GM: Nice, still standard brawny, difficulty 5.
Mage: *rolls 1d6* → spends karma, difficulty 5→4, succeeds; narrates elemental blasting door.
GM: Two skeletons turn to face you.
Mage: Fireball them!
GM: Standard crafty, 1 effort per skeleton.
Mage: *rolls 2d6* → both dice ≥5, 2 successes → both skeletons defeated, exceptional narration.
```

---

## 7. Implementation with `dnd-tools` + `dnd-campaign` via LLMs

> Goal: keep paper implementation (`packages/dnd-tools`) **untouched** for metrics fidelity; build Tricube as a new mode on top, with `dnd-campaign` handling long-horizon play. Both packages expose **tool-grounded** LLM loops via `tau-ai` / `tau_agent`.

### 7.1 Architecture

```
packages/dnd-tools/src/dnd_tools/     # paper-faithful, frozen semantics
  models.py   Character, Weapon, SpellDef, Cell, Buff, ResistEntry
  dice.py     seeded RNG, roll_dice("2d20kh1"), roll_with_parts
  state.py    GameState  — HP/pos/initiative/LoS/death_log/tool_trace
  tools.py    Tools — 30+ typed tools + OpenAI schemas + dispatch()
  agents.py   Tau provider/harness, run_tau_player_turn_sync(), heuristic fallback
  simulation.py  Scenario generation (27) + Simulation loop (turn/round/bookkeeping)
  prompts.py  GM_PROMPT / PLAYER_PROMPT
  mapgen.py   indoor (JSON rooms) / outdoor (procedural)
  cli.py      dnd-tools demo / gen-scenarios / run-scenario / eval

packages/dnd-campaign/src/dnd_campaign/  # long-horizon wrapper, never edits dnd-tools
  state.py    CampaignState — wraps GameState; snapshots/history/save-load/short+long rest/prune
  tools.py    CampaignTools — delegates all Tools + adds campaign tools (long_rest … get_summary)
  memory.py   summarize_state(), compact_transcript() — bounded LLM context
  session.py  CampaignSession — multi-encounter orchestration (add_encounter/run_encounter/run_campaign)
  cli.py      dnd-campaign demo (2-encounter example)
```

### 7.2 New Models for Tricube (additive, isolated)

```python
# packages/dnd-tools/src/dnd_tools/models_tricube.py  (new, or extend models.py via imports)
from dataclasses import dataclass, field


@dataclass
class Affliction:
    name: str  # "broken arm", "lycanthropy", "despair"
    permanent: bool = False  # True if from critical failure
    recovery: str = "scene"  # "scene"|"hours"|"days"|"weeks"|"months"|"permanent"
    location: str | None = None
    source: str | None = None


@dataclass
class TricubeCharacter:
    name: str
    trait: str  # agile|brawny|crafty
    concept: str  # "elven ranger", "draconian knight"
    combat_style: str  # melee|ranged|mental (defaults to trait, frozen)
    perks: list[str] = field(default_factory=list)
    quirks: list[str] = field(default_factory=list)
    afflictions: list[Affliction] = field(default_factory=list)
    karma: int = 3
    karma_max: int = 3  # grows to 6
    resolve: int = 3
    resolve_max: int = 3  # grows to 6
    rank: int = 1  # 1..6, +1 per 4 advances
    advances: int = 0
    # optional subsystems
    xp: int = 0  # 1 XP = 1% of an advance; decorative unless using XP
```

Map to existing `Character` where possible: reuse `Character` with extra fields (`karma`, `resolve`, `trait`, `afflictions`, `rank`) or keep a parallel `TricubeState` that stores both. **Do not break** `GameState` fields (`hp`, `ac`, `pos`); instead let Tricube resolve = `hp` proxy for reuse, or shadow with explicit `resolve` in `CampaignState` snapshot.

### 7.3 Dice Engine Extension (`dice.py`)

Add deterministic helper (seeded by `GameState.seed` via `dice.seed`):

```python
def roll_challenge(dice_count: int, difficulty: int) -> dict:
    rolls = [_rng.randint(1, 6) for _ in range(dice_count)]  # 1-3d6
    successes = sum(1 for r in rolls if r >= difficulty)
    return {
        "rolls": rolls,
        "successes": successes,
        "success": successes >= 1,
        "exceptional": successes >= 2,
        "critical_failure": all(r == 1 for r in rolls),
        "effort_removed": successes,  # 1 per success vs effort pool
    }
```

Keep existing `roll_dice()` for d20/AC paths; add `roll_tricube()` without touching 5e semantics.

### 7.4 GameState / CampaignState Additions

**`state.py` — TricubeGameState** (either subclass `GameState` or new module `state_tricube.py`):
- Replace HP-centric `update_hp` with `update_resolve(name, delta)` and `check_resolve`; death_log becomes `affliction_log`.
- Add `effort_pools: dict[str,int]` for multi-token challenges (grouped foes share a pool).
- Keep `map`, `pos`, `initiative_order`, `round`, `tool_trace`, `transcript` exactly as before for trace compatibility.
- Keep `seed()` determinism — every roll goes through `_rng`.

**`dnd_campaign/state.py` — already wraps `GameState`**:
- `snapshot()` / `restore()` already serialize `players/monsters/positions/initiatives/round/death_log/campaign_meta`. Extend to include `karma/resolve/afflictions/rank/effort_pools`.
- `long_rest` → full resolve + clear non-permanent afflictions + restore economy (no HP/AC reset for Tricube).
- `short_rest` → reset speed/resources only; no resolve.
- `checkpoint()` / `prune_traces()` unchanged — call between scenes to bound LLM context (keep first ~10 + last 200 entries).

### 7.5 Tool Schemas (LLM-visible)

**Base Tricube tools** (new `tools_tricube.py`, mirrors `tools.py` pattern: each method logs to `state.log_tool` and returns JSON):

| Tool | Purpose | Key params |
|---|---|---|
| `roll_challenge(character, trait, difficulty, dice_count, effort_target)` | Authoritative 1–3d6 roll; counts successes, removes effort, logs rolls | `character`, `trait`, `difficulty 3–7`, `dice_count 1–3`, `effort_target?` |
| `spend_karma(character, challenge_id)` | −1 difficulty retroactively (after roll), consume 1 karma, max 1/challenge, cannot stack | `character` |
| `bypass_challenge(character, perk)` | 1 karma *before* roll to auto-succeed flavour-bypassable challenge | `character`, `perk` |
| `invoke_quirk(character, quirk, challenge_id)` | Declare before roll: +1 difficulty, on resolve → +1 karma (or +1 resolve if success) | `character`, `quirk` |
| `apply_affliction(target, name, permanent, recovery)` | Victim decides affliction at 0 resolve; sets `permanent` if from crit fail | `target`, `name` |
| `check_afflictions(target)` | Return affliction list + retirement check (>3 → retired) | `target` |
| `recover_affliction(target, affliction, perk)` | Spend karma (+ permanent karma if `permanent`) to cure; or convert via advance | `target`, `affliction` |
| `check_karma_resolve(target)` | Current/max karma & resolve + rank + effort remaining | `target` |
| `set_effort(target, tokens)` | GM initializes effort pool (rank or 2×rank for boss) | `target`, `tokens` |
| `opposed_challenge(char_a, char_b)` | Both roll `roll_challenge`; compare highest die + tie-break rule | `char_a`, `char_b` |
| `fear_check(character, difficulty, inexperienced)` | Crafty 3d6 else 2d6, −1 die if inexperienced; failure → −1 resolve | `character`, `difficulty` |

**Retained 5e tools** where still useful: `check_valid_attack_line`, `move`/`move_player`, `dash`/`disengage`/`opportunity_attack`, `get_names_of_all_players/monsters`, `check_side`, `visualize_map`, `roll_initiative` (or replace with trait-based initiative mod).

**Campaign tools** (from `dnd_campaign/tools.py`, delegate unchanged):
`long_rest(name?)`, `short_rest(name)`, `checkpoint()`, `save_checkpoint(path)`, `load_checkpoint(path)`, `get_summary()` (compact state for prompt), `prune_traces(keep_last)`.

All tools expose `tool_schemas()` → OpenAI-compatible `{type:"function", function:{name,description,parameters}}` and `dispatch(name, args)` for the harness.

### 7.6 Agent Prompts & Harnesses

Reuse `agents.py` pattern verbatim — **never subprocess, never raw LLM strings as truth**:

```python
# prompts_tricube.py
GM_PROMPT_TRICUBE = """You are the GM (transactional controller). Use tools for all
mechanics. Never roll yourself. For each challenge: assign trait+difficulty+effort,
determine dice_count from archetype/scope, call roll_challenge, apply karma/quirk
mods, remove effort, narrate relative outcome, apply resolve/affliction costs, bookkeep,
say <End Turn/> ..."""
PLAYER_PROMPT_TRICUBE = """You are a Tricube player. Sense→plan→validate→act→communicate.
Query karma/resolve/afflictions, declare quirks *before* rolling, spend karma *after*
only once/challenge, narrate exceptional benefits, coordinate via <Call/>Name, msg<Call/>.
End with <DM/>."""
```

Wire via `agents.py:_tools_to_agent_tools()` + `AgentHarness` (provider = `OpenAICompatibleProvider` for LMStudio at `:1234`):

```python
from dnd_tools.agents import make_tau_provider, _tools_to_agent_tools
from tau_agent.harness import AgentHarness, AgentHarnessConfig

tools = TricubeTools(state)  # or CampaignTools(CampaignState(...))
provider = make_tau_provider("http://127.0.0.1:1234/v1", "lm-studio")
harness = AgentHarness(
    AgentHarnessConfig(
        provider=provider,
        model="qwen3.6-35b-a3b-mtp",
        system=GM_PROMPT_TRICUBE,
        tools=_tools_to_agent_tools(tools),
        max_turns=6,
    )
)
```

**Simulation loop** (`simulation.py` / `session.py`): keep `Simulation.run()` structure — `roll_initiative` → per-turn `check_side` → (optional `move` toward target) → `check_valid_attack_line` → `roll_challenge` → (`spend_karma`/`invoke_quirk` gates) → `apply_affliction` at 0 resolve → `reset_resources`/`reset_speed`/buff expiry → `<End Turn/>`. For campaign, `CampaignSession.add_encounter()` initializes Tricube parties + effort pools, `run_encounter()` delegates to `Simulation`, then `checkpoint()` + `prune_traces()`.

### 7.7 Determinism & Evaluation

- **Seeded RNG**: all rolls via `dice.seed(seed_val)` derived from `GameState.seed` / `CampaignState` snapshot; re-seed on `restore()`.
- **Authoritative state**: narration never overrides tool results; tools are isolation boundary (return `error` not raise on misuse — harness catches).
- **Traces**: every tool call logs to `state.tool_trace` with `{tool, args, result, round, actor}` — same shape as 5e for `metrics.py` (`tactical_optimality`, `acting_quality`, `function_usage`, etc.).
- **Heuristic fallback**: `heuristic_player_turn()` mirrors paper's greedy policy but for Tricube: pick nearest foe, check LoS, declare quirk if karma-starved, roll, spend karma if 1 short of success on 1 die, degrade gracefully if LLM unavailable.

### 7.8 Minimal CLI Wiring

```python
# dnd_tools/cli.py pattern — add tricube subcommand
# dnd-tools tricube-demo --seed 42 --turns 10 [--use-llm --model qwen3...]
# dnd-campaign tricube-demo --seed 42 --turns 15 --save run.json
# Both reuse existing arg parsing; llm = LLMClient alias → TauLLM(provider, model)
```

### 7.9 What *Not* to Port

- Do **not** reintroduce AC/HP/damage dice for Tricube combat (resolve + effort are sufficient). Tactics supplement's `stride`, `knacks`, `edge modifiers` are optional phase-2 — keep Tales core first, add Tactics later behind a feature flag.

---

## 8. Challenge Resolution Flow (pseudocode, deterministic)

```python
# GM assigns
difficulty = 5  # 4 easy, 5 standard, 6 hard
trait = "brawny"
effort = target.rank  # or 2*rank for boss
dice_count = 3 if chr.trait == trait else 2
if out_of_scope(chr.concept, chr.perks, challenge):
    dice_count = max(1, dice_count - 1)

# optional quirk gate (before roll)
if player_declares_quirk:
    difficulty += 1  # can exceed 6; record for karma/resolve recovery

# authoritative roll
r = roll_challenge(dice_count, difficulty)  # rolls, successes, critical_failure
# optional karma gate (after roll, max 1)
if r.successes == 0 and player_spends_karma and chr.karma > 0:
    difficulty -= 1
    r = reevaluate(r.rolls, difficulty)  # recount successes vs new difficulty
    chr.karma -= 1

effort_removed = min(effort_pool[target], r.successes)
effort_pool[target] -= effort_removed
if r.critical_failure:
    affliction_permanent = True
    resolve_cost = 2
elif not r.success:
    resolve_cost = 1
else:
    resolve_cost = 0  # exceptional → narrate benefit
if resolve_cost:
    chr.resolve = max(0, chr.resolve - resolve_cost)
if chr.resolve == 0:
    apply_affliction(chr.name, name=choose_affliction(), permanent=affliction_permanent)
    chr.resolve = chr.resolve_max
    chr.afflictions.append(...)
    # cannot act remainder of scene
if len(chr.afflictions) > 3:
    retired = True
```

---

## 9. References

- Full text: `ref/tricube-tales.txt` / `tricube-tales.pdf` (print & phone PDF, DriveThruRPG).
- Tactical supplement: `ref/tricube-tactics.txt` / `.pdf` — adds strides, knacks, edge modifiers, etc. (phase 2, optional).
- Paper context: `ref/31_Setting_the_DC_Synthesis.md` — DC-setting evaluation frame this implementation extends.

*End of condensed implementation reference.*
