# Blades in the Dark — Core System Rules (Implementation Condensed)

> Blades in the Dark © 2017 John Harper / Evil Hat Productions — SRD text under CC BY 3.0 (https://bladesinthedark.com/basics). Condensed below for LLM + tool-grounded implementation. See also Forged in the Dark SRD (https://github.com/amazingrando/blades-in-the-dark-srd-content).
> Reference sources consulted: SRD pages for Action Roll, Effect, Setting Position & Effect, Resistance & Armor, Stress & Trauma, Consequences & Harm, Progress Clocks, Fortune Roll.

---

## 1. System Overview

### Why Position & Effect ("The AI Fix")

Before any roll the player and GM must agree on two independent axes:

- **Position** — how dangerous is it if you fail? `Controlled` (exploit advantage) / `Risky` (act under fire, default) / `Desperate` (overreach, serious trouble).
- **Effect** — how much will success accomplish? `Limited` (partial/weak) / `Standard` (normal) / `Great` (more than usual). Trading position↔effect is allowed after assessment (e.g. take Desperate for Great).

The AI cannot soften the blow: the consequence table is tied to `position × outcome`. A failure at `Desperate/Limited` *must* produce **severe harm / serious complication / lost opportunity**, and the player *must* either take it or **mark Stress** via a resistance roll (`6 − high die`). The prompt pattern is rigid:

> "I am attempting this in a Desperate position with Limited effect. I rolled a 3 (Failure). Give me a harsh consequence and ask me how I mark Stress to avoid the worst of it."

- Single `d6` reading (not sum) enforces harsh variance: most low-pool rolls end `4/5` or `1-3` → always a consequence.
- Resistance is *always effective* (GM narrates reduction vs avoidance) but always costs stress → resource spiral guarantees hard choices.
- Effect×ticks links directly to multi-roll clocks, so LLMs cannot one-roll a score.

### Core Loop (Score → Downtime)

```
Free Play → Score (engagement → actions → position/effect roll → consequences → clocks/heat)
         → Downtime (payoff → heat → entanglements → vice → recovery/projects → craft/ritual)
         → Free Play
```

This repo implements the **Score** loop (action/resistance/fortune + clocks/heat) plus a minimal **Downtime** wrapper (vice / recovery / train). Faction/coin/stash/magnitude are referenced but not fully simulated in v1.

---

## 2. Characters

### 2.1 Playbooks & Stats

8 playbooks: `Cutter`, `Hound`, `Leech`, `Lurk`, `Slide`, `Spider`, `Whisper` (+ `Vampire`/`Ghost` expansion). Each starts with **3/2/2/1** dots across the 12 actions (max 4 dots per action). Crew type adds build.

**Actions** (12, rated 0–4):

| Attribute | Actions |
|---|---|
| **Insight** (deception/understanding) | Hunt, Study, Survey, Tinker |
| **Prowess** (physical) | Finesse, Prowl, Skirmish, Wreck |
| **Resolve** (will/social) | Attune, Command, Consort, Sway |

**Attribute rating** = sum of action dots in that attribute — used for resistance rolls (0 dice → roll 2d6 keep lowest). At chargen pick special abilities, vice, heritage/background, friends/rivals.

### 2.2 Stress, Trauma & Harm

- **Stress** — pool `0–9` (configurable, paper uses 9). Gain from: push yourself `+2`, assist `+1`, resistance `6−high`, flashback (cost = GM tier), Devil's Bargain is GM clock/heat not personal stress.
- When `stress = 9` (overflow 9) → **Trauma** (permanent condition: Cold, Haunted, Obsessed, Paranoid, Reckless, Soft, Unstable, Vicious). Clear stress to 0, gain trauma. At **4 traumas → retired**.
- **Trauma** also gives `-1d` when using its resisted attribute? Simplified in tools as narrative tag; we expose it for penalty tracking.
- **Harm** — 3 rows: `Level 1` (lesser, 2 boxes), `Level 2` (moderate, 2 boxes), `Level 3` (severe, 2 boxes). Level 4 = `Fatal` (death unless resisted). First harm box per level tracks stacking; healing/project reduces it. Tool stores `harm: list[{level,name,healing_clock?}]`.
- **Healing**: clock `4 segments` per harm level (physicker roll). Recovery removes harm after clock full.
- **Armor**: light `+1`, heavy `+1` (`armor` / `heavy` checkboxes). Mark to reduce/avoid consequence (like resistance but no stress).

### 2.3 XP & Advancement (summary v1 not enforced in simulation)

Mark XP on desperate action `0→4` dot (max 4). Playbook advances every `8 XP`. Crew XP from rep.

---

## 3. Core Rolls

### 3.1 Action Roll (Six Steps)

1. Player states **goal**.
2. Player chooses **action rating** (`0–4` dots). Must match fiction.
3. GM sets **position** (`controlled`/`risky`/`desperate`, default **risky**).
4. GM sets **effect** (`limited`/`standard`/`great`; also `zero`/`extreme` via factors).
5. Add **bonus dice** (normal cap 2, some abilities give extra):
   - `+1d` assist (helper takes `1 stress`, describes help).
   - `+1d` push yourself (`2 stress`) **OR** Devil's Bargain (GM defines cost, outcome-independent; can't take both).
6. **Roll** pool `nd6`, judge by **single highest die**:

| Highest | Outcome | Flags |
|---|---|---|
| `6` with 2+ sixes | **Critical** | `increased effect` (or extra benefit on clock) |
| `6` | **Full success** | Do it, no consequence (position tables may still describe) |
| `4–5` | **Partial success** | Do it **but** with consequence (severity = position) |
| `1–3` | **Failure** | Do **not** do it (usually) **+** consequence (severity = position) |

- `0 dice` rule: roll `2d6`, take **lowest** (critical impossible).
- Success **still** has consequence on `4/5` — most tactically interesting region.
- NPCs don't roll — action roll is **double-duty**: `6` = PC wins, `4/5` = mixed, `1–3` = NPC wins as consequence.

**Outcome × Position table** (SRD exact):

- **Controlled** — dominant advantage
  - Critical: increased effect.
  - 6: done.
  - 4/5: hesitate — *withdraw & try another approach* OR do it with minor consequence (minor complication / reduced effect / lesser harm / fall to **risky**).
  - 1-3: falter — press on via **risky** opportunity OR withdraw.

- **Risky** — default
  - Critical: increased effect.
  - 6: done.
  - 4/5: done **but** consequence (harm / complication / reduced effect / fall to **desperate**).
  - 1-3: bad — suffer harm / complication / fall to **desperate** / **lose opportunity**.

- **Desperate** — overreach
  - Critical: increased effect.
  - 6: done.
  - 4/5: done but with **severe** harm / **serious** complication / reduced effect.
  - 1-3: worst — **severe harm** / **serious complication** / **lose opportunity**.

### 3.2 Position & Effect Negotiation

Set together after action choice. Default `Risky/Standard`. Modify via action fitness + three **effect factors** (SRD §Effect):

- **Potency** (weaknesses, extra time/risk, arcane edge).
- **Scale** (number/area/scope; more allies = better in brawl, worse in sneak).
- **Quality/Tier** (gear Tier, `fine` = +1 quality).

Result may be `zero` (need different approach) or `extreme` (full clock). After assessment player may **trade position for effect** (“I'll go Desperate for Great?”) — GM may grant at cost.

`+1 effect` abilities apply **after** assessment. Push for `+1 effect` costs `2 stress` (alternative to `+1d` push).

### 3.3 Resistance Roll

When GM declares a consequence player may say `"I resist that"` **before** rolling:

- GM decides: **reduced** (harm down one level, complication ticks fewer) vs **avoided** (weapon kept) — tone dial.
- GM picks **attribute** (Insight = deception/understanding, Prowess = physical, Resolve = mental/will).
- Roll `attribute` dice pool (0 → 2d6 keep lowest).
- `stress taken = 6 − high die`. Critical (2+ sixes) → **clear 1 stress** after.
- Once you declare, you eat the stress — no take-backs.

**Armor alternative**: mark `armor` or `heavy` box to avoid/reduce same consequence without stress; cleared on next load selection.

### 3.4 Fortune Roll

For uncertain futures not driven by PC action. GM picks attribute or Tier, sets dice (0→2d6 keep lowest), result same tiers `6` superlative / `4-5` mixed / `1-3` poor. Used for engagement payoff, gathers.

### 3.5 Gathering Information & Group/Setup

- **Gather Information** = action roll (usually Survey/Study/etc.) whose effect is information quality; consequence is start clock or danger.
- **Teamwork**: `Group Action` (one leader, others `1 stress` to give `+1d` each up to leader's bonus), `Protect` (resist teammate consequence), `Setup` (effect bonus on next actor), `Lead` (followers +1d).

---

## 4. Scores — Engagement & Clocks

### 4.1 Plan → Detail → Engagement Roll

Players choose **plan** (`assault`, `deception`, `infiltration`, `mysticism`, `social`, `transport`) + **detail** (approach, location, asset). GM sets **engagement fortune**: dice from plan viability (`1d` baseline ± plan quality, crew Tier vs target Tier, wildcard) — Fortune roll (`6` controlled start, `4-5` risky, `1-3` desperate).

### 4.2 Progress Clocks

Generic obstacle clocks (`4/6/8` segments). On ticks:

| Effect | Ticks |
|---|---|
| Limited | 1 |
| Standard | 2 |
| Great | 3 |
| Critical (extra benefit) | +1 tick (often 5 or custom) |
| Extreme | 5 (use for supernatural/v1 optional) |
| Zero | 0 |

Clocks also track complications (`Alert 6`, `Doom 8`), long-term projects, healing.

### 4.3 Heat, Wanted & Entanglements (score fallout)

Score payoff generates **coin**, **heat** (`0–9`, + from bodies/witnesses, supernatural display, high-profile), and **rep**. At `9 heat` → **Wanted** level. Downtime entanglements roll `2d6 + heat` (`6` clean, `5` trouble, `1-3` serious entanglement). Simplified in tools as numeric heat; entanglements are narrative prompts.

---

## 5. Example Play (SRD verbatim flow, paraphrased)

```
Player: "I want to pickpocket the inspector. My goal is to get the ledger without her noticing."
GM: "How? She’s alert, surrounded by Bluecoats."
Player: "I’ll Sway her — act like a fellow officer, misdirect her."
GM: "Sway fits, but with so many witnesses this is Desperate/Limited. Risky/Standard if you Prowl instead."
Player: "I’ll stay Sway, take the Desperate/Limited. Can I push for Great effect?"
GM: "Push is 2 stress for +1 effect → Standard. Also, do you want assist from Locke?"
Locke: "I’ll assist, take 1 stress, pretend to be his junior officer. +1d."
Player: *rolls 3d6 = [5,3,2] → 5 (4/5, Desperate) → success but severe harm/serious complication, limited effect becomes Standard via push so 2 ticks on Ledger clock*
GM: "You get the ledger (2 ticks /6), but the Inspector clocks you — you take level 2 harm 'Suspicious glance', and Bluecoats ask questions. Want to resist?"
Player: "I resist with Insight (Resolve for mental stress? GM says Prowess is physical, but harm is social so Resolve). Roll 2d6 = [4,2] → 2 stress, harm reduced to level1 'Ruffled feathers'."
```

---

## 6. Implementation with `dnd-tools` + `dnd-campaign` via LLMs

Goal: keep `packages/dnd-tools` **frozen**; build Blades as additive Forged package mirroring `tricube`/`sword-and-sorcery`.

### 6.1 Architecture

```
packages/blades-in-the-dark/src/blades_in_the_dark/
  models.py     BladesCharacter (actions 0-4, attributes derived, stress 0-9, trauma, harm, vice, playbook, crew), BladesClock, Crew
  dice.py       seeded RNG, roll_action(pool, zero_dice rule), roll_resistance(attr), roll_fortune(dice), outcome & critical logic
  state.py      BladesState (characters, clocks, heat/wanted/rep, load/armor, flashbacks) + BladesCampaignState (checkpoint/save/prune)
  tools.py      BladesTools — 20+ typed tools (set_position_and_effect, action_roll, push_yourself/assist/devil_bargain, resistance_roll, tick_clock, etc.)
  prompts.py    GM_PROMPT / PLAYER_PROMPT — rigid recipe: goal → action → position/effect negotiation → bonus dice → roll → consequence → resist → clock ticks
  agents.py     Tau harness wrappers + heuristic (greedy closest clock tick)
  simulation.py Single score simulation (engagement → action loop → clocks)
  session.py    Multi-score campaign (heat/entanglements/downtime)
  memory.py     summarize_state, compact_transcript
  cli.py        blades demo scene / campaign
```

### 6.2 New Models (additive, isolated)

```python
@dataclass
class BladesCharacter:
    name: str
    playbook: str  # cutter/hound/leech/lurk/slide/spider/whisper
    actions: dict[str, int]  # 12 keys 0-4
    stress: int = 0
    stress_max: int = 9
    trauma: list[str] = field(default_factory=list)  # up to 4 causes, then retired
    harm: list[dict] = field(default_factory=list)  # {level,name}
    healing: dict[str, Heartbeat] = field(default_factory=dict)
    vice: str = ""
    xp: int = 0
    load: int = 5
    armor: dict[str, bool] = field(default_factory=lambda: {"armor": False, "heavy": False})


@dataclass
class BladesClock:
    name: str
    segments: int  # 4/6/8
    ticks: int = 0
    kind: str = "obstacle"  # obstacle/danger/project/healing
```

`crew` fields (tier, heat 0-9, wanted, rep) live on `BladesState`.

### 6.3 Dice Extension (`dice.py`)

Add helpers seeded by `BladesState.seed`:

```python
def roll_action(pool: int) -> dict:
    if pool <= 0:
        rolls = sorted([_rng.randint(1, 6) for _ in range(2)])
    else:
        rolls = [_rng.randint(1, 6) for _ in range(pool)]
    high = min(rolls) if pool <= 0 else max(rolls)
    crit = rolls.count(6) >= 2 and pool > 0
    ...


def roll_resistance(attr: int) -> dict:  # same zero rule, stress = 6-high, crit clears 1
    ...
```

Keep `dnd_tools.dice` untouched.

### 6.4 GameState / CampaignState Additions

- Replace HP-centric `update_hp` with `mark_stress(delta)` / `mark_harm(level,name)` / `clear_stress` semantics. `death_log` → `trauma_log` / `harm_log`.
- Add `clocks: dict[str, BladesClock]`, `heat/wanted`, `devil_bargain_pending`.
- `BladesCampaignState.snapshot/restore` mirrors `dnd_campaign` pattern; re-seeds dice on restore.
- Downtime: `indulge_vice(name)` (clear stress = highest vs vice?), `recover(harm)`, `train(action)`, `reduce_heat` via coin.

### 6.5 Tool Schemas (LLM-visible)

| Tool | Purpose | Key params |
|---|---|---|
| `set_position_and_effect(character, action, position, effect)` | Gate: must precede `action_roll`; GM/player agreement. | `position controlled/risky/desperate`, `effect limited/standard/great/zero/extreme` |
| `action_roll(character, action, position, effect, push, assist, devil_bargain)` | Pool = action rating + bonus dice; zero-dice rule; returns highest/critical/outcome + consequence severity per position table. | `action e.g. Prowl`, `pool` auto from sheet |
| `push_yourself(character, bonus)` | `2 stress` for `+1d` or `+1 effect` (choose one per roll) | `bonus: dice|effect` |
| `assist(helper, target)` | Helper `+1 stress` → target `+1d` next roll | `helper`, `target` |
| `devil_bargain(character, description)` | Grants `+1d`, complication ticks independent of outcome | `description` |
| `resistance_roll(character, attribute)` | `6−high` stress, crit clears 1 | `attribute insight/prowess/resolve` |
| `mark_stress`, `clear_stress`, `mark_trauma`, `check_stress` | Stress lifecycle | |
| `apply_harm`, `heal_harm`, `use_armor` | Harm 1-4 boxes | |
| `set_clock`, `tick_clock`, `check_clock` | Effect→ticks (1/2/3) +1 on crit | |
| `engage_roll(plan, detail, dice)` | Fortune for starting position | |
| `gather_information`, `flashback` | Utility | |
| `check_character`, `list_actions`, `visualize_clocks` | Queries | |

All tools log to `state.log_tool` and expose `tool_schemas()` → OpenAI-compatible + `dispatch()`.

### 6.6 Agent Prompts & Harness

**GM** is transactional controller: never rolls, sets position/effect via tools, inflicts consequence strictly by table, narrates but tools are authoritative. **Player** loop: `sense → negotiate position/effect → allocate bonus dice → roll → accept/resist consequence → clock ticks`.

Wire via `tau_agent.harness.AgentHarness` with `OpenAICompatibleProvider` (LMStudio `:1234`), same shim as `dnd_tools.agents`.

### 6.7 What *Not* to Port (v1 scope)

Defer full Coin/Stash, detailed Ritual/Crafting, and faction ledger to later; heat/entanglements are tracked numerically but resolved narratively. Full advancement (XP triggers) is exposed via tools but not auto-enforced.

---

## 7. The AI Fix — Rigid Prompt Template

The repo should ship a reusable prompt fragment LLM players can paste when they fear softening:

```
I am attempting [action: Prowl, goal: steal ledger] in a Desperate position with Limited effect (agreed via set_position_and_effect).
I rolled a 1-3 Failure (highest 2). Per the Controlled/Risky/Desperate table, give me a harsh consequence:
- Severe harm OR serious complication OR lost opportunity (or 2+)
- Ask me how I mark Stress to resist (resistance_roll with Insight/Prowess/Resolve) or mark armor.
- If I do not resist, tick the consequence exactly as severe and show clock impact (Limited=1, Standard=2, Great=3).
Do not soften, do not handwave — use the Blades consequence table verbatim.
```

The tool surface enforces this by *requiring* `set_position_and_effect` before any `action_roll`, and by requiring a `resistance_roll` or `mark_stress` flow when `position=desperate` + `outcome=1-3`.

---

## 8. References

- SRD HTML source: https://github.com/amazingrando/blades-in-the-dark-srd-content (markdown sources for every section above).
- Online SRD: https://bladesinthedark.com/action-roll, /effect, /setting-position-effect, /resistance-armor, /core-system, /stress-trauma, /progress-clocks. Fetched 2026-09-09 for this note.
- Paper frame: `ref/31_Setting_the_DC_Synthesis.md` — the tool-grounded audit pattern this implementation extends.

*End of condensed implementation reference.*
