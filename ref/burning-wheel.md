# Burning Wheel Gold — Core System Rules (Implementation Condensed)

> **Burning Wheel Gold** © 2002–2011 Luke Crane / Burning Wheel HQ — by Luke Crane, Thor Olavsrud, et al. Condensed below for LLM + tool-grounded implementation from *Burning Wheel Gold* (Hub and Spokes, Rim, Character Burner) and public SRD-adjacent summaries. **No open CC SRD exists** — this is a fair-use synthesis of published mechanics for implementation reference, not a reproduction of copyrighted text. Burning Wheel™ is a trademark of Luke Crane.
> Reference sources consulted 2026-09-09: *Burning Wheel Gold* Hub & Spokes (Intent & Task, Say Yes or Roll, Let It Ride, Help, FoRKs, Artha, BITs), Character Burner (Lifepaths, Stats, Skills, Traits, Circles/Resources/Steel), *The Spokes* (Versus/Bloody Versus, Advancement, Beginner's Luck), Rim conflict chapters (Duel of Wits, Fight!, Range & Cover), plus BWHQ trait-vote and advancement errata. Cross-checked against community SRD summaries (2017–2024) for obstacle tables and shade math. No verbatim text beyond short attributed quotes.

---

## 1. System Overview

### Why Burning Wheel — And the AI Fix

Burning Wheel inverts trad D&D assumptions. The GM does not prep plot — the players do, via **Beliefs**. The engine is fiction-first, intent-driven, fail-forward, and relentlessly player-facing. Three design choices break LLM autopilot:

- **Beliefs drive play.** Every PC carries 3 Beliefs of the form *I believe ___ and will ___* (`Hub: Beliefs`). Artha (Fate/Persona/Deeds) flows *only* when Beliefs are challenged, pursued, or broken. Without a belief audit the LLM invents generic fantasy.
- **Intent & Task + Say Yes or Roll.** No roll without opposed intent. If failure isn't interesting, **Say Yes** — don't roll. If you roll, **Let It Ride** locks the result until fiction changes (`Hub: Let It Ride`). The LLM cannot reroll-spam or soften with a lateral second check.
- **Counted successes, not sums.** Roll `N d6` where `≥4 = 1 success` (black shade; grey `≥3`, white `≥2`), compare successes to **Obstacle (Ob)**. Help (`+1D` per helper), **FoRKs** (Fields of Related Knowledge, `+1D` per relevant skill), and **Artha** (Fate open-ends 6s, Persona `+1D…+3D`, Deeds doubles dice) are the *only* modifiers. No stacking +2 soup.

> Failure is not null — the GM must narrate a complication that *matters* and still advances the world. Success without cost only when belief-irrelevant → Say Yes.

### Core Loop (Authoritative Flow)

```
Belief framing (3 Beliefs/Instincts/Traits per PC, Artha pools) → Scene framing (situation + intent)
  → GM: Say Yes or set Ob (intent + task → Ob 1–10 table) → Declare Help/FoRK/Artha BEFORE roll
  → Roll N d6 vs Ob (shade threshold) → Success / Failure → GM narrates failure consequence (no reroll; Let It Ride)
  → Log routine/difficult/challenging test for skill/stat advancement → Award Fate/Persona/Deeds if BITs hit
  → Next intent (Duel of Wits / Bloody Versus / Fight! if opposed wills; else next versus/simple)
```

This repo implements the **Hub & Spokes** loop (Intent & Task, Versus, Bloody Versus, Circles/Resources/Steel) plus **Duel of Wits** as the scaled conflict; full **Fight!** and **Range & Cover** are referenced but gated behind a scripted-conflict flag (v1 uses Bloody Versus as default, see §4.7).

---

## 2. Characters

### 2.1 Burning a Character (Lifepaths)

Character Burner builds history via **Lifepaths (LPs)** — pick `3–5 LPs` (Born → Apprentice → Journeyman → Master path). Each LP grants `years`, `stat points`, `skill points`, `trait points`, `resources points`, and access to `skills/traits` lists. Settings carry distinct LP banks (Man, Dwarf, Elf, Orc).

Implementation stores `lifepaths: list[str]`, `age: int`, `stock: man|dwarf|elf|orc`.

Resets per chapter: starting **Resources** exponent = `15 + sum(LP resource points)` rolled as attribute; **Circles** from LP + affiliations/reputations; **Steel** from Will + Forte.

Shorthand for LLM chargen when not burning fully: pick `stock + concept + 3 LPs + 12 skills` distributed by LP lists + 5 traits (see §2.5).

### 2.2 Stats & Attributes

**Stats** (all `1–6` exponent at start, `1–10` viable via advancement, shade = `B` default, `G/W` rare):

| Stat | Tests | Root for |
|---|---|---|
| **Will** | Social, Steel hesitation, Duel of Wits body | Social skills (Persuasion, Oratory, Interrogation) |
| **Perception** | Observation, search | Perception skills (Observation, Search) |
| **Agility** | Quickness, fine motor | Agility skills (Brawling, Throwing) |
| **Speed** | Initiative, reflexes | Speed skills (Stealth, Climbing, Speed itself) |
| **Power** | Raw strength | Power skills (Brawling, Power) |
| **Forte** | Health, endurance | Forte skills (Health-like) |

**Attributes** (derived but advance independently like skills):

| Attribute | Exponent | Purpose |
|---|---|---|
| **Health** | `Forte + Will / 2` (round down) | Wound recovery, resist poison/disease; tests like Forte |
| **Steel** | `Will + Forte` derived, then rolled | Hesitation vs fear/pain (see §4.5) |
| **Circles** | `Will`-based + LP affiliations/reps | Find NPCs (see §4.3) |
| **Resources** | `Generic` + LP + property | Buy gear/property (see §4.4); taxed on failure |
| **Reflexes** | `Agility+Speed+Perception / 3` | Ordering (Fight! only; Bloody Versus uses versus) |

Each stat/attribute/skill has `exponent` (dice count) + `shade` (`B/G/W`). Shade sets success threshold: `B≥4, G≥3, W≥2`. Exponent 0 is possible for untrained (use Beginner's Luck).

### 2.3 Skills

- **Exponent `1–10`** (starting `2–5` typical, `6+` is heroic). Listed by root: e.g. `Sword B4` (Power), `Persuasion B3` (Will), `Stealth B4` (Agility).
- **Shades**: writing `B4 / G4 / W4` matters; advancement shade shifts require Persona/Deeds + trait vote.
- **Training**: must have `skill exponent ≥1` to test normally. At `0` use **Beginner's Luck** (§3.7) — roll `root stat halved (round up)` at `double Ob`, failures count toward learning the skill (and advancement of the root).
- **Skill lists**: `100+` skills (Sorcery, Sword, Bow, Persuasion, Circles, etc.). BWHQ table governs roots; many skills are setting-agnostic. Tool validates `skill in SKILL_ROOTS` and `exponent` bounds.

### 2.4 BITs — Beliefs, Instincts, Traits

Every PC has exactly **3 Beliefs**, **3 Instincts**, **5–7 Traits** (mix of character/die/call-on).

**Beliefs** — `I believe [world truth] and will [concrete action]`:

- Must be actionable and testable this session. Bad: `Love conquers all`. Good: *I believe the Duke is a traitor and will prove it by stealing his ledger tonight*.
- Reviewed **every session** (start + end); expected to change `≥1` per session as they resolve. Beliefs that aren't challenged are rewritten or lost (0–1 Persona consequence if ignored).

**Instincts** — `Always / Never / When X, then Y` reflex:

- `Always draw steel when ambushed`, `Never leave a man behind`. Fires even if player forgot — point to the instinct and it happens.
- Following an instinct that causes trouble → **Fate**; breaking an instinct for drama → potential **Persona (Moldbreaker)**; can be changed between sessions.

**Traits** — three types:

| Kind | Effect | Cost |
|---|---|---|
| **Character trait** | Pure narrative (e.g. `Curious`, `Stubborn`, `Albino`). Guides RP, gives Fate when it complicates you, flipped by trait vote. | 1 pt |
| **Call-on trait** | `1/session` invoke: reroll failures or swap 1 die for a success on relevant test, OR break a tie in your favour. E.g. `Linguist` for translation, `Iron Will` vs Steel. | 2–3 pts |
| **Die trait** | Alters the roll itself: `+1D`, `+1 Ob`, advantage, shade shift, etc. E.g. `Gifted` (permits Sorcery), `Faithful`, `Essence of Earth`. Voted, rarely bought. | 3–5 pts |

Trait vote: other players vote at end of session/arcs to add, remove, or **promote** character → call-on → die (incremental path is canonical, e.g. `Devout → Believer → Faithful`).

### 2.5 Artha — Fate, Persona, Deeds

Meta-currency spent to bend rolls; earned *only* via BITs and playstyle awards. Pools are per-PC, tracked openly. GM never spends Artha for NPCs unless flagged elite.

| Artha | Earn when | Spend effect |
|---|---|---|
| **Fate** (`F`) | Play a Belief/Instinct/Trait even though it hurts; embody trait to complicate story; invoke trait in wrong direction deliberately. Most common. | **Open-ended**: every `6` rolled explodes — roll another die, `≥4` (=shade threshold) counts as an extra success, and that die also explodes on 6. Apply to one test; declare **before** roll or immediately after seeing 6s (tool enforces declaration before). |
| **Persona** (`P`) | **Moldbreaker**: break a Belief/Instinct/Trait for drama; **Workhorse**: do the grunt work; **Embodiment**: become the party's locus for a session. Also when a Belief resolves. | `+1D` per Persona (max 3 on one roll), **or** `+1 success per 2 dice` via `Deepen` variant; or shade-shift one die? Canonical: `Persona = +1D` (declare before roll), stacking `1–3P → +1D…+3D`. Alternative spend: `Save from death` / `Shrug` costs tracked but v1 implements `+1D` path. |
| **Deeds** (`D`) | Go beyond self — heroic act that aids the whole group/world at great cost; voted at arc end. Rarest. | **Double the dice** of the ability for one test (declare before roll), or auto-success variant for advancement? Canonical: `Deeds = double exponent` for one roll — *the* heroic swing. |

Tool enforces `F/P/D` inventory (`fate`, `persona`, `deeds`) and the **one-Fate-open + one-Persona/Deeds-boost per test** convention.

### 2.6 Wounds & PTGS (Physical Tolerance Greeting Scale)

Wounds are **not HP** — they are penalties + fictional impairment tied to **Physical Tolerance Greeting Scale (PTGS)** derived from Forte+Power. PTGS yields thresholds:

| Wound class | Penalty | Source threshold (example Forte 4 → thresholds Superficial/Light/Midi/Severe/Traumatic/Mortal) |
|---|---|---|
| **Superficial** (`Su`) | `+1 Ob` to next test only (or `+1 Ob` ongoing if optional rule) | `1–2` over tolerance |
| **Light** (`Li`) | `+1D penalty` (remove one die before roll) | `3–4` |
| **Midi** (`Mi`) | `−1D` (same as Light but stacks; some tables call `+2 Ob`) | `5–6` |
| **Severe** (`Se`) | `−2D` | `7–8` |
| **Traumatic** (`Tr`) | `−4D` | `9–10` |
| **Mortal** (`Mo`) | Dead in minutes without `2 Persona` rescue | `11+` |

Penalties are **cumulative** (Light + Superficial = −1D and +1 Ob next roll; Severe adds −2D). Healing uses Health tests with Ob = wound class. Mortal requires `2 Persona` for last-hour reprieve. **Steel** hesitation may stack orthogonally (§4.5).

---

## 3. Core Mechanics

### 3.1 The Die & Shades

Every roll uses `d6` pools:

```
success = 1 if die ≥ threshold(shade)
threshold(B)=4, threshold(G)=3, threshold(W)=2
total_successes = count(successes) + fate_explosions(6s)
explode: each natural 6 → roll 1 extra d6, same threshold, recursive on new 6
critical-notion: double-sixes are not a crit concept; open-ended Fate is the exception path
```

Seeded RNG via `dice._rng` (inherits `dnd_tools.dice`), re-seeded on `restore()`.

### 3.2 Intent & Task, Obstacle, and Say Yes or Roll

**Intent** = what you want in fiction (*steal the ledger to prove treason*). **Task** = how you do it (*pick the lock with Lockpick*). Both must be stated **before** Ob is set. If intent and task don't align, GM reframes intent or raises Ob.

**Obstacle (Ob)** — difficulty `1–10` (`0 = Say Yes`):

| Ob | Label | Use |
|---|---|---|
| 1 | Easy | Everyday, or aided |
| 2 | Routine | Professional with right tool |
| 3 | Difficult (baseline) | **Default** for Versus; most tests |
| 4–5 | Hard / Very Hard | Interesting but nonessential; no Help needed |
| 6+ | Extreme | Reserve for `3-point spends` or layered disadvantage |
| 7–8 | Legendary | Cap; use staged tests instead |

Rule: **essential forward momentum ≤ Ob 4** (CR likens to GUMSHOE's core-clue ease). If Ob would block and no interesting failure exists, **Say Yes** — grant intent without rolling (optionally charge a minor cost / Resources tap).

### 3.3 Simple Test

1. Player declares `intent + task + skill/stat`.
2. GM sets **Ob** `1–10` (hidden until declared; Toll variant reveals — kept for parity with GUMSHOE but BW's default is to state Ob after intent).
3. Player declares **Help** (see §3.4), **FoRKs** (see §3.5), **Artha** (Fate for open, Persona +1D…+3D, Deeds double) *before* rolling — tool gates order.
4. Roll `exponent dice + help dice + FoRK dice + persona dice (then Fate explosions)`. `total = successes (+ Fate dice)`.
5. `total ≥ Ob → success` (intent achieved). `total < Ob → failure` → GM narrates failure consequence tied to **Belief** (not HP tax); no retry — **Let It Ride** until fiction changes.

**No double-spend gate**: the test *is* your best shot.

### 3.4 Help

One helper → `+1D` to the leader's roll (helper must have a relevant skill/stat ≥ `B2`, and must narrate how they help). Multiple helpers each give `+1D` (cap `+3D`, typically `2 helpers`). Helper's failure never penalizes leader; but helper may be exposed to failure consequence fictionally. Helpers cannot Help if they've already rolled same intent (Let It Ride applies to them too). Tool validates `helper_skill_present && helper_narration`.

### 3.5 FoRKs (Fields of Related Knowledge)

Each **related but not identical** skill grants `+1D` (max `+2 FoRK dice`, once per skill per session). E.g. `Foraging B3` helps a `Cook B4` test; `Anatomy B3` FoRKs `Surgery B3`. Implementation tracks `forks_used_this_session: set[skill]` and enforces `len(forks) ≤2` and `fork_skill != tested_skill`.

### 3.6 Versus & Bloody Versus

**Versus test** — direct contention (stealth vs observation, persuasion vs will):

- Both sides independently roll `skill vs Ob = opponent's successes` (simultaneous). Higher successes wins intent; **tie = defender wins** (or most dice matching — tie-breaker: attacker needs *strictly* more). Some tables resolve as one roll vs opponent's successes as Ob; tool implements symmetric count and compares.

**Bloody Versus** — abbreviated fight that preserves Let It Ride:

- Each side scripts **one action** (Strike / Defend / Feint / etc. stripped to `attack/defend` intent) and rolls relevant weapon skill (Sword, Bow, etc.) or Power/Speed if unarmed. Higher successes wins, loser takes wound at margin (difference + weapon IMS). Fast, single-roll, GM narrates positioning. This is the **v1 default** for combat — see §4.7 for Fight! gating.

### 3.7 Beginner's Luck & Practice

If `skill exponent = 0`, halve the **root stat** (`ceil(stat/2)`) and roll at **double Ob**. Losses count as tests for *learning* the skill (see §5); successes don't yet give skill tests. Once `routine` tests accumulate, skill opens at `B2`. Tool path `beginners_luck = True` halves dice and doubles Ob, logs `luck_test`.

### 3.8 Graduated Tests & Linked Tests

- **Graduated** — GM states what *failure gradient* buys: `Ob 1 = basic info`, `Ob 3 = deeper`, `Ob 5 = full`. Player rolls once; successes locate outcome on gradient.
- **Linked tests** — prior test grants `+1D` advantage on next if succeeded, `+1 Ob` disadvantage if failed. E.g. `Scavenging` → `Mending`. Tool logs `linked_advantage: +/-1`.

### 3.9 Let It Ride (LiR)

A roll's outcome **stands for the session** until `intent, task, or conditions` change significantly. You cannot re-roll a failed `Stealth` by declaring the same stealth again; you must change approach (new Belief angle, new tool, new route) or wait until next session. Tool enforcement: hash `intent+task+character+scene` → `ride_key`; second `simple_test` with same key returns `{error: "Let It Ride"}` unless `li_ride_override: changed_task|changed_intent|session_advanced`.

### 3.10 Wises & Circles/ Resources Tests (preview)

`Wise` skills (e.g. `Orc-wise`) act as knowledge FoRKs and as in-fiction declarations (spend a test to declare a fact anchored in the Wise — spend governs plausibility). Circles and Resources are rolled like skills but with distinct failure costs (enemy found, tax — see §4.3–4.4).

---

## 4. Running the Game — GM Guidance (Implementable)

### 4.1 Belief Lifecycle (Load-Bearing)

Every case-of-play encodes:

- **Situation** = the inciting crisis (the hook).
- **3 Beliefs per PC**, each referencing situation + an actionable next step.
- **Instincts** as safety nets (`Always cast Aura Reading before opening a door` → you get the chance).
- **Traits** as Fate generators and social facts.

Authoring structure: trail of **Obstacles** reverse-engineered from Beliefs, not a railroad. GM's prep is `what the NPCs want × what the PCs believe`, not `what happens next`.

Tool stores `beliefs: list[{id, text, target, goal}]`, `instincts`, `traits`, `artha_log: list[{type, reason, belief_id}]`.

GM principles to encode:
- **Challenge Beliefs every scene** (test the player, not the stat).
- **Failure = complication tied to BIT** — not `no`, but `yes, but the world moves`.
- **Let It Ride strictly** — don't let LLMs re-ask for a check.
- **Say Yes** when stakes are low — preserve rolls for belief-relevant intents.

### 4.2 Scene Types (for scenario design)

| Type | Role | Belief hook? |
|---|---|---|
| **Building** | Exposition, camp, travel | Sets up beliefs |
| **Conflict** | Versus / Duel of Wits / Bloody Versus | **Yes — must** |
| **Resolution** | Wound treatment, belief rewrite, trait vote | Re-anchors BITs |

Include `belief_ref: belief_id` on every scene header the GM writes; validator warns if a scene has no `belief_ref` for any PC.

### 4.3 Circles

Roll `Circles exponent + affiliations + reputation + relationship dice` vs Ob by NPC power (townsman Ob1, notable Ob2, lord Ob3, king Ob4; +1 if hostile, −1 if friendly). Success = NPC found and willing. **Failure = enmity** — GM introduces NPC but as an enemy, complication, or with a cost (town guard who hates you). Circles failure never returns empty — it returns trouble. Tool `circles_test(character, npc_power, disposition)` handles dice + Ob + `failure = hostile introduction`.

### 4.4 Resources

Roll `Resources exponent + cash dice + affiliations/property dice` vs Ob by price (trifling Ob1, tools Ob2, arms Ob3, estate Ob4+). Success = acquire without loss. **Failure = Tax** — reduce exponent by `1` (or `cash` lost). Logging Resources failures as `tax: -1B` matters for advancement. Tool `resources_test(character, price_ob, cash_dice?)` returns `tax` field.

### 4.5 Steel

Hesitation vs terror/pain. Roll `Steel exponent` when facing fear, gruesome injury, surprise violence. Hesitation table (condensed — `BWHQ: Steel`):

| Margin vs Hesitation Ob (usually Will/Steel contest) | Effect |
|---|---|
| `0–1` | Hesitate `1 action` (fiction) / `+1 Ob` next test |
| `+2–3` | `Stand and drool` 1 exchange |
| `+4+` | Flee / faint / soil self |

Steel tests themselves log advancement separately. NPC monsters may have `Hesitation` stat directly.

### 4.6 Duel of Wits (DoW)

Structured debate where **beliefs literally collide**. Scripted like Fight! but social. Skirmish in `exchanges` (3 volleys per exchange):

- **Point** = Body of Argument (BoA) = `Will + relevant skill successes` (Oratory, Persuasion, Rhetoric, etc.). Zero BoA → lost.
- Each volley secretly script **Point / Rebuttal / Dismiss / Feint / Obfuscate / Incite / Avoid the Topic** — each maps to a skill test vs opponent's test; margin reduces BoA (like damage). `Incite` is risky (big payoff, big fall).
- First to `0 BoA` loses; then **Compromise** — winner achieves intent but must concede a minor/major compromise proportional to how much BoA they lost (table: `all lost → major compromise`). This is why `4/5`-like regions matter — strongest tension.
- Tool `dow_script(volley=[action, skill])`, `dow_resolve(exchange)` + `compromise_roll`.

### 4.7 Bloody Versus vs Fight! / Range & Cover (Escalation Ladder)

- **Versus** — one roll each, high wins (for single intent).
- **Bloody Versus** (`B!W p.45`) — one roll each for a messy brawl (above). **v1 default** for all physical combat.
- **Fight!** — fully scripted melee (`Strike, Block, Avoid, Counterstrike, Feint, Lock, Push, Charge` per volley, 3 volleys per exchange, positioning, weapon length). **Flag-gated**: `--scripted fight` enables; otherwise tool returns `use Bloody Versus (Say Yes or script full Fight!)`.
- **Range & Cover** — scripted ranged duel (Find cover → Maneuver → Hold). Also flag-gated in v1.

Physical IME: `Sword B4` + `Brawling B3` etc. HIT uses `successes vs defense Ob`; weapon IMS (Incidental/Mark/Superb) decides wound class via PTGS.

### 4.8 Magic & Faith (overview, setting-gated)

- Requires **Gifted** / **Faithful** die traits. Sorcery = `Sorcery skill + Will` to cast, `Ob` by spell, tax (Forte test) on failure. Faith similar but via `Faith B`.
- Spells have `Ob`, `Origin`, `Area`, `Element` etc. v1 keeps spell effects narrative + advantage FoRK `+1D`; full Tax/Ob tables are phase-2.

---

## 5. Advancement

### 5.1 Tests Log (Routine / Difficult / Challenging)

Every Stat/Skill/Attribute exponent advances by **logging tests** categorized by *pre-roll exponent vs Ob*:

| Test class | Condition |
|---|---|
| **Routine** | `Ob ≤ Dice Rolled` (some printings: `Ob ≤ exponent` — use `exponent` for purity; tool uses `Ob <= dice`) |
| **Difficult** | `Ob > Dice Rolled` by `1–2` |
| **Challenging** | `Ob > Dice Rolled` by `3+` (or `Ob >= dice+3`) |

Canonical BW Gold thresholds (total):

| Exponent | Needs (Routine / Difficult / Challenging) to advance |
|---|---|
| `B2` | `2R / — / —` |
| `B3` | `3R / 1D / 1C` |
| `B4` | `4R / 2D / 1C` |
| `B5` | `5R / 2D / 2C` |
| `B6` | `6R / 3D / 2C` (etc., `+1R/+1D every exponent`) |

v1 stores `tests: {routine, difficult, challenging}` per skill/stat. On rolling, tool auto-classifies by `ob vs dice` and appends; when threshold met it increments exponent and resets bucket. **Shades** shift requires a **Deeds** + **Persona** + trait-vote combo, not dice.

### 5.2 Practice, Instruction & Beginner's Luck Progression

- **Practice** = weekly Ob by exponent (time-gated ticks).
- **Instruction** = teacher with `exponent+1` grants `+1 test` of chosen class.
- **Beginner's Luck** successes (at double Ob) log as tests toward *opening* the skill to `B2`; routine successes while lucky eventually flip `exponent=0 → 2`.

### 5.3 Trait & Belief Evolution

- Trait vote at session/arc end: peers may grant/remove/promote traits based on play; promotion chain `Char → Call-on → Die` is the canonical growth path.
- Beliefs rewrite: if resolved/absurd/ignored, player writes a new one and may earn/lose Persona accordingly. Tool `rewrite_belief(pc, old_id, new_text)` validates `I believe ___ and will ___` form.

---

## 6. Example Play (BW Gold–true paraphrase, condensed)

```
GM: The keep is locked-down — the Duke's guard bars the granary. Your Belief is
    "The Duke is starving the town and I will prove it by taking a sack as evidence."
    What is your Intent?

Player (Persuasion B3, Will B4): "Intent: get past the guard without violence.
    Task: call on my Belief about the Duke and persuade him the town will riot."
GM: Say Yes or Roll — stakes are a Belief, so Roll. Ob 3 (guard is Will 3 + stubborn).
    Declare Help/FoRK/Artha before roll.
Player: "My brother helps (+1D, he has Persuasion B2 and narrates backing me),
    I FoRK Oratory-wise (+1D), and I spend 1 Persona (+1D) — my Belief is on the line."
GM: Dice = 3 + 1 (help) + 1 (FoRK) + 1 (Persona) = 6D vs Ob 3. Roll 6D (B) → [4,5,2,6,1,4]
    = 4 successes (≥4 = success, 6 explodes? No Fate declared so no open) → 4≥3 success.
    Log: Difficult test for Persuasion B3 (dice 3 vs Ob3? Actually dice 3 vs Ob3 = Routine;
    but with Persona dice total is 6 vs Ob3 → Routine). Intent succeeds.

Later — Bloody Versus:
GM: The guard draws steel when you grab the sack — Steel test Ob3 for sudden violence?
Player: Rolls Steel B3 → 2 successes <3 → hesitates. Guard acts first.
GM: Bloody Versus — Player Brawling B3 vs Guard Brawling B4. Both roll; margins → wound.
Player: Bloody Versus roll fails by 2, Light wound via PTGS → −1D forward.
GM: Failure narrates: you get the sack but take Light wound and alarm is raised — Belief
    consequence forces your next Belief to confront the Duke. Let It Ride bars another
    persuasion on same guard until you change task (Bribe, Intimidate, or Fight!).
End of session — Belief challenged → 1 Fate; Moldbreaker (ignored Instinct) → 1 Persona;
trait vote: 'Stubborn' promoted to call-on.
```

---

## 7. Implementation with `dnd-tools` + `dnd-campaign` via LLMs

> Goal: keep `packages/dnd-tools` **untouched** for paper-metrics fidelity; build Burning Wheel as a new additive mode on top, with `dnd-campaign` handling multi-session belief arcs. Both packages expose **tool-grounded** LLM loops via `tau-ai` / `tau_agent`.

### 7.1 Architecture

```
packages/dnd-tools/src/dnd_tools/          # paper-faithful, frozen semantics
  models.py   Character, Weapon, SpellDef, Cell, Buff, ResistEntry
  dice.py     seeded RNG, roll_dice("2d20kh1"), roll_with_parts
  state.py    GameState — HP/pos/initiative/LoS/death_log/tool_trace
  tools.py    Tools — 30+ typed tools + OpenAI schemas + dispatch()
  agents.py   Tau provider/harness, run_tau_player_turn_sync(), heuristic fallback
  simulation.py  Scenario generation (27) + Simulation loop
  prompts.py  GM_PROMPT / PLAYER_PROMPT
  mapgen.py   indoor (JSON rooms) / outdoor (procedural)
  cli.py      dnd-tools demo / gen-scenarios / run-scenario / eval

packages/dnd-campaign/src/dnd_campaign/    # long-horizon wrapper, never edits dnd-tools
  state.py    CampaignState — wraps GameState; snapshots/history/save-load/short+long rest/prune
  tools.py    CampaignTools — delegates all Tools + adds campaign tools
  memory.py   summarize_state(), compact_transcript() — bounded LLM context
  session.py  CampaignSession — multi-scene orchestration
  cli.py      dnd-campaign demo

packages/burning-wheel/src/burning_wheel/  # new additive package (or subpackage burning_wheel/ under dnd_tools)
  models_bw.py  BWCharacter, Belief, Instinct, Trait, Artha, Wound, Lifepath
  dice_bw.py    roll_bw(pool, shade), open_ended(fate), classify_test(dice, ob)
  state_bw.py   BWState (characters, beliefs, scenes, wound/steel/circles/resources, test logs)
  tools_bw.py   BWTools — 25+ typed tools (see §7.5) + OpenAI schemas + dispatch()
  prompts_bw.py GM_PROMPT_BW / PLAYER_PROMPT_BW
  agents_bw.py  Tau harness wrappers + heuristic (belief-aware greedy)
  simulation_bw.py Single-session loop (belief → intent → versus/DoW/bloody → wound → artha)
  session_bw.py Multi-session campaign (belief rewrite, trait vote, practice)
  memory_bw.py  summarize_bw_state(), compact_transcript()
  cli_bw.py     bw demo / campaign
```

Alternative if not adding a new workspace member: keep `burning_wheel/` under `packages/dnd-tools/src/dnd_tools/burning_wheel/` with `models_bw.py` etc., imported but never touching existing `models.py`/`tools.py`.

### 7.2 New Models (additive, isolated)

```python
from dataclasses import dataclass, field
from enum import Enum


class Shade(str, Enum):
    B = "B"  # black: ≥4
    G = "G"  # grey: ≥3
    W = "W"  # white: ≥2


THRESHOLD = {"B": 4, "G": 3, "W": 2}

SKILL_ROOTS = {
    "Sword": "Power",
    "Bow": "Agility",
    "Persuasion": "Will",
    "Oratory": "Will",
    "Stealth": "Agility",
    "Observation": "Perception",
    # ... 100+ entries, per BW Gold table
}


@dataclass
class Belief:
    id: str
    text: str  # "I believe ___ and will ___"
    target: str | None = None
    goal: str | None = None
    challenged: bool = False
    resolved: bool = False


@dataclass
class Instinct:
    text: str  # "Always … / Never … / When X, then Y"
    triggered: bool = False


@dataclass
class Trait:
    name: str
    kind: str  # character|call_on|die
    uses: int = 0  # call-on = 1/session max
    effect: str | None = None  # "+1D to …" / "reroll" / "shade shift"


@dataclass
class Artha:
    fate: int = 0
    persona: int = 0
    deeds: int = 0


@dataclass
class Ability:
    name: str  # stat / skill / circles / resources / steel / health
    exponent: int  # 0..10
    shade: Shade = Shade.B
    routine: int = 0
    difficult: int = 0
    challenging: int = 0
    forks_used_session: set[str] = field(default_factory=set)


@dataclass
class Wound:
    kind: str  # superficial|light|midi|severe|traumatic|mortal
    penalty: str  # "+1Ob" | "-1D" | "-2D" | "-4D"
    ptgs_margin: int = 0
    location: str | None = None


@dataclass
class BWCharacter:
    name: str
    stock: str = "Man"  # Man|Dwarf|Elf|Orc
    lifepaths: list[str] = field(default_factory=list)
    age: int = 20
    beliefs: list[Belief] = field(default_factory=list)  # exactly 3
    instincts: list[Instinct] = field(default_factory=list)  # exactly 3
    traits: list[Trait] = field(default_factory=list)  # 5-7
    artha: Artha = field(default_factory=Artha)
    stats: dict[str, Ability] = field(default_factory=dict)  # Will/Perception/…/Forte
    attributes: dict[str, Ability] = field(default_factory=dict)  # Health/Steel/Circles/Resources/Reflexes
    skills: dict[str, Ability] = field(default_factory=dict)
    wounds: list[Wound] = field(default_factory=list)
    hesitation: int = 0  # Steel hesitation stacks
    # advancement bookkeeping
    belief_log: list[dict] = field(default_factory=list)
    trait_vote_pending: bool = False


@dataclass
class BWState:
    characters: dict[str, BWCharacter]
    scene: str | None = None  # current scene id + belief_ref
    let_it_ride: dict[str, dict] = field(default_factory=dict)  # ride_key → {result, round}
    artha_log: list[dict] = field(default_factory=list)
    wound_log: list[dict] = field(default_factory=list)
    tool_trace: list[dict] = field(default_factory=list)
    transcript: list[dict] = field(default_factory=list)
    sessions_complete: int = 0
    seed: int = 0
    round: int = 0
    # mirrors GameState seed/map when mixing with grid
    map: list | None = None


@dataclass
class Opponent:
    name: str
    abilities: dict[str, Ability] = field(default_factory=dict)
    ptgs: dict[str, int] = field(default_factory=dict)
    hesitation: int = 0
    will: int = 3
    steel: int = 3
```

Fate/Persona/Deeds per PC reset only via earned awards, not per rest. `Resources` and `Circles` live as `attributes["Resources"]` / `attributes["Circles"]` so unified advancement logic applies; convenience getters `get_circles(c)` / `get_resources(c)` alias the exponent but failure cost is Tax/Enmity not HP.

### 7.3 Dice Engine Extension (`dice_bw.py`)

Deterministic helpers seeded by `BWState.seed` (re-seeded on `restore`):

```python
import random as _random
from dnd_tools.dice import _rng  # re-exported seeded RNG


def threshold_for(shade: str) -> int:
    return {"B": 4, "G": 3, "W": 2}[shade]


def roll_bw(pool: int, shade: str = "B", fate_open: bool = False) -> dict:
    """Roll pool d6 vs shade. Fate open-ends 6s recursively."""
    th = threshold_for(shade)
    dice = [_rng.randint(1, 6) for _ in range(pool)]
    successes = sum(1 for d in dice if d >= th)
    explosions: list[int] = []
    if fate_open:
        for d in list(dice):
            if d == 6:
                # explode: roll 1 extra, same threshold, recurse on 6
                extra = _rng.randint(1, 6)
                explosions.append(extra)
                if extra >= th:
                    successes += 1
                while extra == 6:
                    extra = _rng.randint(1, 6)
                    explosions.append(extra)
                    if extra >= th:
                        successes += 1
                    if extra != 6:
                        break
    return {
        "pool": pool,
        "shade": shade,
        "dice": dice,
        "explosions": explosions,
        "successes": successes,
        "threshold": th,
    }


def classify_test(dice: int, ob: int) -> str:
    """Stat/skill test class for advancement (BWG p.46)."""
    if ob <= dice:
        return "routine"
    if ob <= dice + 2:
        return "difficult"
    return "challenging"


def wound_for_margin(margin: int, ptgs: dict) -> str:
    # map IMS margin onto Su/Li/Mi/Se/Tr/Mo via PTGS bands
    ...
```

Keep existing `roll_dice("1d20")` etc. untouched for 5e metrics. New helpers clamp `Ob 1..10` and shade validates `B/G/W`. Persona `+1D…+3D` adds to `pool` before `roll_bw`; Deeds doubles `pool` before same call. Tool-level validation enforces `persona ≤3` per test and `fate ≤1` per test.

### 7.4 GameState / CampaignState Additions

- **BWState** shadows `GameState` fields it reuses (`seed`, `round`, `tool_trace`, `transcript`, `map`/`pos` for battles) for trace compatibility; it does not mutate 5e HP/AC semantics.
- **Intent & Task is audited**: `declare_intent(character, intent, task, skill, belief_ref)` must precede any `roll_test`; tool validates belief anchoring (belief text must appear or implicit belief_ref).
- **Let It Ride hash**: `ride_key = hash(character, intent, skill, scene)` — second test with same key unless `override in ("changed_task","changed_intent","session_advanced")` returns `{error: "Let It Ride"}`.
- **Advancement auto-logs**: `roll_test` already classifies `routine/difficult/challenging` via `classify_test(dice, ob)` and appends to `skills[skill]` or `stats[stat]` log; `check_advancement(character, ability)` surfaces `threshold_met`.
- **Artha ledger**: `award_artha(character, type, reason, belief_id)` + `spend_artha(character, type, amount)` gated by pool; trait-vote awards require `voted: bool`.
- **CampaignState** wrapping: `snapshot()` / `restore()` serialize `beliefs/instincts/traits/artha/wounds/tests/let_it_ride/sessions`; re-seed dice on restore; `checkpoint()` + `prune_traces()` unchanged (keep first ~10 + last 200 entries). Between sessions: `advance_session()` sweeps belief rewrite, trait vote flag, practice ticks, `Fork` reset.

### 7.5 Tool Schemas (LLM-visible)

Each method logs to `state.log_tool` and returns JSON; errors are `{error: str}` dicts, never raises. Declaration order is enforced: `declare_intent → set_ob → declare_help/fork/artha → roll`.

| Tool | Purpose | Key params |
|---|---|---|
| `declare_intent(character, intent, task, skill, belief_ref)` | **Authoritative gate**: registers intent+task+belief link; must precede `set_ob`/`roll_test`. Validates 3-belief form. | `character`, `intent`, `task`, `skill`, `belief_ref` |
| `set_ob(character, ob, kind)` | GM sets Obstacle `1–10`; must precede any roll. `kind = simple|versus|circles|resources|steel|dow` | `character`, `ob 1..10`, `kind` |
| `declare_help(leader, helper, skill, narration)` | Registers `+1D` per helper (cap 3, requires helper skill `≥B2` + narration). | `leader`, `helper`, `skill`, `narration` |
| `declare_fork(character, fork_skill)` | Registers FoRK `+1D` (cap 2 per test, unique FoRK per session; must not be the tested skill). | `character`, `fork_skill` |
| `spend_artha(character, type, amount)` | Spend phase: `Fate` (open), `Persona +1..3D`, `Deeds double`. Validates pool; at most 1 Fate open + 1 Persona/Deeds per test. | `character`, `type fate|persona|deeds`, `amount` |
| `roll_test(character, skill, ob, shade?)` | Authoritative `Nd6` vs shade Ob; respects declared help/FoRK/Artha, Fate explosions, wound/steel penalties, hesitation. Returns `dice/successes/ob/success/failure/classification(routine/difficult/challenging)`. | `character`, `skill`, `ob`, `shade B|G|W` |
| `beginners_luck(character, stat, ob)` | Halve root stat `ceil(stat/2)` at `double Ob`; counts toward opening skill. | `character`, `stat Will|Perception|…`, `ob` |
| `versus_test(a, a_skill, b, b_skill, ob_a?, ob_b?)` | Symmetric versus: both `roll_test` independently vs Ob (default `opponent successes`). Returns winner + margin. | `a`, `a_skill`, `b`, `b_skill` |
| `bloody_versus(attacker, atk_skill, defender, def_skill, weapon_ims?)` | Single-exchange brawl: both roll weapon skills; higher margin wounds loser via PTGS. | `attacker`, `defender`, `skills`, `weapon_ims Su|Li|Mi|Se|Tr|Mo` |
| `circles_test(character, npc_power, disposition)` | Roll Circles + affiliations/reps vs Ob by power; failure = hostile/begrudging NPC (never empty). | `character`, `npc_power 1..4`, `disposition friendly|hostile` |
| `resources_test(character, price_ob, cash_dice?)` | Roll Resources + cash/affils vs Ob by price; failure = Tax `−1` exponent (or cash loss). | `character`, `price_ob 1..5`, `cash_dice` |
| `steel_test(character, ob, hesitation_mod?)` | Roll Steel vs hesitation Ob; failure → hesitate/stand-and-drool/flee duration. | `character`, `ob 1..6` |
| `apply_wound(target, kind, margin?)` | Map IMS margin to Su/Li/Mi/Se/Tr/Mo via PTGS (`state.ptgs`), apply stacking penalties `+1Ob/−1D/−2D/−4D`. | `target`, `kind` or `ims_margin` |
| `heal_test(healer, target, wound_kind)` | Health test at Ob by wound class (Su Ob2 … Mo Ob6+); success clears penalty, Mortal needs Persona. | `healer`, `target`, `wound_kind` |
| `dow_script(character, volley, action, skill)` | Script one DoW volley `Point|Rebuttal|Dismiss|Feint|Obfuscate|Incite|Avoid` with skill. | `character`, `volley 1..3`, `action`, `skill` |
| `dow_resolve(exchange)` | Resolve 3 volleys, debit BoA, compute compromise tier (`all retained→no compromise` … `all lost→major`). | `exchange` |
| `declare_wise(character, wise, fact)` | Use `X-wise` to declare a fact anchored in the Wise (FoRK-like, consumes a test). | `character`, `wise`, `fact` |
| `check_skill / check_stat / check_ptgs / check_artha / check_beliefs` | Queries: exponent/shade, PTGS bands, Artha pools, blocked Let It Ride keys. | `character` |
| `rewrite_belief(character, old_id, new_text)` | Between sessions: validate `I believe ___ and will ___` form; log Persona/Fate delta if belief changed via trait vote. | `character`, `old_id`, `new_text` |
| `trait_vote(table, grants, removals, promotions)` | Session-end: peer vote to add/remove/promote traits (`Char→Call-on→Die`). | `table: list[character]` |
| `advance_skill(character, skill)` / `advance_stat` | Flush `tests` bucket → increment exponent if threshold met; shade shifts via Artha+vote only. | `character`, `skill` |
| `get_summary` / `visualize_ptgs` / `print_artha_log` / `check_let_it_ride` | Context/monitor helpers. | — |
| `set_lifepaths`, `check_character`, `list_skills`, `list_wises`, `shade_lookup` | Chargen + lookup queries. | — |

All tools publish `tool_schemas()` OpenAI-compatible and `dispatch(name, args)`.

### 7.6 Agent Prompts & Harness

**GM** is transactional arbiter: never rolls silently, sets Ob via tools, inflicts failure strictly as *belief-targeted complication* (never silent null), enforces Let It Ride, narrates but tools are authoritative. **Player** loop: `sense→declare belief-relevant intent→validate BIT link→declare Help/FoRK/Artha→roll→accept failure cost→log test→communicate`.

Wire via `tau_agent.harness.AgentHarness` with `OpenAICompatibleProvider` (LMStudio `:1234`), same shim as `dnd_tools.agents`:

```python
from dnd_tools.agents import make_tau_provider, _tools_to_agent_tools
from tau_agent.harness import AgentHarness, AgentHarnessConfig

tools = BWTools(state)  # or BWCampaignTools(BWCampaignState(...))
provider = make_tau_provider("http://127.0.0.1:1234/v1", "lm-studio")
harness = AgentHarness(
    AgentHarnessConfig(
        provider=provider,
        model="qwen3.6-35b-a3b-mtp",
        system=GM_PROMPT_BW,
        tools=_tools_to_agent_tools(tools),
        max_turns=8,
    )
)
```

**Prompts** (`prompts_bw.py` — keep `dnd_tools.prompts` shape):

```python
GM_PROMPT_BW = """You are the GM (transactional controller) for Burning Wheel Gold — Hub & Spokes.
Never roll silently; demand Intent & Task + belief_ref before any test; set Ob 1-10 via set_ob;
enforce Help (+1D/helper, cap 3, needs narration), FoRK (+1D/skill, cap 2, once/session),
Artha (Fate open-ended 6s, Persona +1-3D, Deeds double, 1 Fate + 1 Persona/Deeds per test);
resolve via roll_test/bloody_versus/circles_test/resources_test/steel_test/dow_resolve.
On failure narrate a belief-targeted complication — never null or soft — then enforce Let It Ride
(same intent+task+scene cannot be re-rolled; require changed task/intent/session).
Track wounds via PTGS (Su/Li/Mi/Se/Tr/Mo), hesitation via Steel, BoA via Duel of Wits.
Log routine/difficult/challenging per roll. Award Fate/Persona/Deeds only for BIT play.
Close every turn with <End Turn/>."""
PLAYER_PROMPT_BW = """You are a Burning Wheel player. Sense→Plan→Validate→Act→Communicate.
For every action: cite which Belief (of your 3) this intent serves, phrase intent + task
'I believe ___ and will ___ by [task] using [skill]'; call declare_intent with belief_ref,
await GM set_ob, then declare Help/FoRK/Artha BEFORE calling roll_test/versus_test/circles_test.
Never re-roll let-it-ride-blocked intent — change task or intent. On failure accept the
GM's belief-relevant complication and log the test class. Award yourself Fate when you
complicate your own life via a BIT; claim Persona when you break a BIT for drama or
resolve a belief. End with <DM/>."""
```

**Simulation loop** (`simulation_bw.py`/`session_bw.py`): keep `Simulation.run()` structure — `declare_intent` → `set_ob` → `declare_help`/`declare_fork`/`spend_artha` → `roll_test` (or `versus_test`/`bloody_versus`/`circles_test`/`resources_test`/`steel_test`/`dow_script`→`dow_resolve`) → `apply_wound`/`heal_test` on margin → `Let It Ride` fingerprint → trait-vote + `rewrite_belief` sweep between sessions → `<End Turn/>`. For campaign, `CampaignSession.add_scene()` initializes BIT-anchored situation, `run_scene()` delegates to `Simulation`, then `checkpoint()` + `prune_traces()` (`memory_bw.summarize_state`/`compact_transcript`).

### 7.7 Determinism & Evaluation

- **Seeded RNG**: all `Nd6` + explosions + DoW dice via `dice.seed(seed_val)` derived from `BWState.seed` / `BWCampaignState` snapshot; re-seed on `restore()`.
- **Authoritative state**: narration never overrides tool results; tools are isolation boundary (return `error` not raise on misuse — harness catches; `declare_help`/`declare_fork`/`spend_artha` caps, `Let It Ride` block, `Fate once` cap, `Persona ≤3` cap enforced as `{valid: False, reason}`).
- **Traces**: every tool call logs to `state.tool_trace` with `{tool, args, result, round, actor}` — same shape as 5e for `metrics.py` (`tactical_optimality`, `acting_quality`, `function_usage`).
- **Heuristic fallback**: `heuristic_player_turn()` mirrors paper's greedy policy but for BW: pick belief with oldest `challenged=False`, declare intent targeting its `goal`, seek Help if ally has related skill ≥B2, FoRK if any unused relevant Wise, spend Persona if Ob > dice, degrade gracefully if LLM unavailable.

### 7.8 Minimal CLI Wiring

```python
# dnd_tools/cli.py pattern — add burning-wheel subcommand
# dnd-tools bw-demo --seed 42 --turns 10 [--use-llm --model qwen3.6-35b-a3b-mtp]
# dnd-campaign bw-demo --seed 42 --turns 15 --save run.json
# burning-wheel gen-scenarios --seed 42 --out scenarios  # belief-anchored scenarios
# burning-wheel run-scenario scenarios/bw_scenario_01.json --turns 10
```

Reuse `dnd_tools.cli` arg parsing; `llm = LLMClient` alias → `TauLLM(provider, model)`. Map: optional 20×20 for `visualize_map`/`line_of_sight` parity even though BW positioning is abstract (useful for Range & Cover phase-2).

### 7.9 What *Not* to Port (v1 scope)

Defer full **Fight!** (`Strike/Block/Counterstrike/Feint/Lock` script), **Range & Cover** (`Find Cover → Maneuver → Hold`), and detailed **Sorcery Tax / Summoning / Enchanting** Ob tables to later; they are flagged `--scripted fight` / `--sorcery` and fallback-run Bloody Versus + narrative advantage for sorcery. Full **Lifepath integrity validator** and **BWHQ Relationships/Affiliations cost table** are tracked numerically but resolved narratively. Shades beyond `B` start as `G/W` flag per character via deed.

---

## 8. The AI Fix — Rigid Prompt Templates

The repo should ship reusable fragments LLM players/GMs paste when they fear softening. Tools enforce them, but the text prevents hallucination drift.

**Intent & Task + Belief gate** (must be tool-called, not narrated):

```
I am acting on Belief [#2: "I believe the Duke is a traitor and will prove it
by stealing his ledger tonight"] in scene [Granary — guard at door].
My Intent is [get past the guard without violence] and my Task is
[Persuade him the town will riot using Persuasion B3].
I call declare_intent(character, intent, task, skill, belief_ref=2) and await
GM set_ob BEFORE declaring Help/FoRK/Artha. If failure has no interesting
consequence, Say Yes — do not roll.
```

**Artha gate** (max 1 Fate open + 1 Persona/Deeds per test, declared before roll):

```
Before rolling I declare Help (brother Persuasion B2, "backs my plea" → +1D),
FoRK Oratory-wise (+1D, once/session), and spend 1 Persona (+1D, pool B2→1) —
and 1 Fate to open-end 6s (pool F3→2). Pool = 3 +1 +1 +1 =6D (B, ≥4 = success).
I call spend_artha(character, fate=1, persona=1) then roll_test(character, Persuasion, Ob3, shade B).
Show dice, explosions on 6s, successes vs Ob, and classification
routine/difficult/challenging BEFORE narrating failure-as-complication.
```

**Let It Ride gate**:

```
My Stealth B4 failed (Ob 4, 2 successes) to bypass the same guard via the same
crack. That Let It Ride key [character:intent:skill:scene] is BLOCKED until I
change task (bribe vs persuade), change intent (distract vs bypass), or the
session advances. I will not re-declare the same intent — I change task to
[Intimidate via Ugly Truth B2, Ob 3] and call declare_intent anew.
```

**Failure-Complication gate** (anti-softening):

```
I rolled failure (1 < Ob 3). Give me a Belief-targeted complication per Hub
general principle — not null, not HP tax — e.g. guard lets me pass but
confiscates the ledger and now the Duke knows my Belief, or guard raises alarm
and my Resources are taxed. Ask how I mark this on my Belief or whether I
rewrite the Belief before next session. Do not handwave — use the BW failure table verbatim.
```

The tool surface enforces all of the above by **requiring** `declare_intent` → `set_ob` → `declare_help/fork/spend_artha` before any `roll_test`, by capping `Help/FoRK/Artha` in state, by blocking duplicate `ride_key` rolls, and by requiring `apply_wound`/`circles_test`/`resources_test` to account for every failure-as-complication.

---

## 9. References

- Press & text: *Burning Wheel Gold* (Luke Crane, Burning Wheel HQ, 2011) — Hub & Spokes (Intent & Task, Say Yes or Roll, Let It Ride, Help, FoRKs, Artha, BITs, Wounds, Steel, Versus/Bloody Versus), Character Burner (Lifepaths, Stats, Skills, Traits, Circles/Resources), Rim (Duel of Wits, Fight!, Range & Cover, Sorcery). Earlier *Burning Wheel Revised* (2005) and *Burning Wheel Classic* (2002) cited for lineage.
- Teaching synthesis: *The Burning Wheel Codex* and BWHQ forum rulings (Artha wheel, trait vote promotion chain Char→Call-on→Die, routine/difficult/challenging bands) — `burningwheel.com` 2011–2024.
- Community SRD notes used for cross-check (not quoted): public advancement tables (`Ob ≤ dice → Routine; Ob > dice → Difficult/Challenging`), shade thresholds (`B4/G3/W2`), PTGS bands, Hesitation guidance, DoW compromise ladder — `burningwheel.com/pages/beliefs-and-instincts`, RPG.net BWG review, wikidot Systems, Cannibal Halfling In-Depth, TVTropes, rpg.stackexchange Belief/BIT threads (all fetched 2026-09-09).
- Legal: Burning Wheel is closed text — **no CC SRD**; this file is a referential summary. For canonical rules purchase *Burning Wheel Gold* at `burningwheel.com` / DriveThruRPG (`Burning Wheel Gold Revised` + `Character Burner` supplement).
- Paper frame: `ref/31_Setting_the_DC_Synthesis.md` — the tool-grounded audit pattern this implementation extends (function usage / parameter fidelity / state tracking / efficiency / acting quality / tactical optimality).
- Cross-system implementation precedents in this repo: `ref/blades-in-the-dark.md`, `ref/tricube-tales.md`, `ref/tricube-tactics.md`, `ref/sword-and-sorcery.md`, `ref/fate-core.md`, `ref/gumshoe-srd.md` (architecture / prompt / harness / tool-trace patterns reused).

---

## 10. Notes on this Markdown

- Reformatted from BW Gold text layer with section-order retention and `pdftotext -layout -raw`-style verification where the book's two-column layout duplicated marginalia. Tables (Stat → Skill roots, Test class, PTGS, Artha ledger, Lifepath stubs) are normalised from running text for LLM parsing.
- `tools_bw.py` field names (`let_it_ride`, `forks_used_session`, `artha_log`, `belief_ref`, `trait_vote_pending`) are quoted where they are authoritative state, not prose invention.
- No rules were invented for §1–§6; wording is kept paraphrased where the source is closed, with only formatting, table structure, and cross-references added for implementation. Direct quotes are short and attributed. §7–§8 are additive guidance explicitly marked as such and are the only sections that propose new code.

*End of condensed implementation reference.*
