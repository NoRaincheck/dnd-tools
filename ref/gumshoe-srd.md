# GUMSHOE SRD — Core System Rules (Implementation Condensed)

> GUMSHOE System © 2007 Robin D. Laws / Pelgrane Press — designed for investigative roleplaying. SRD released under **OGL and CC BY** via the Hillfolk Kickstarter ([Wikipedia](https://en.wikipedia.org/wiki/Gumshoe_System), [SRD Legal](https://gumshoesrd.opengamingnetwork.com/legal/)). Condensed below for LLM + tool-grounded implementation from the Open Gaming Network SRD (`gumshoesrd.opengamingnetwork.com/rules` + `/your-character` + `/legal`) and Pelgrane Press Rules Summary (2017-09-29).
> Reference sources consulted 2026-09-09: SRD pages for Why This Game Exists / Mystery Structure / Gathering Clues (Core/Special Benefits/Inconspicuous/Simple Searches), Die Rolls, Tests (Simple/Piggybacking/Cooperation/Continuing Challenges), Zero Sum Contests, General Spends, Contests (Fighting/Health/Stability/Armor/Cover), Regaining Pools, Improving Character, Opponent Statistics, Hazards, and Designing/Running Scenarios (Clue Types/Scene Types). Pelgrane Press summary at `pelgranepress.com/2017/09/29/gumshoe-rules-summary` for high-level cross-check. GUMSHOE™ is a trademark of Pelgrane Press; SRD text is open content.

---

## 1. System Overview

### Why GUMSHOE Exists ("The Clue Fix")

Traditional investigative RPGs ask *Will the heroes get the information they need?* and gate core clues behind a die roll — a single failed `Spot Hidden` stalls the entire story. GUMSHOE inverts this (SRD §Why This Game Exists):

> *Investigative scenarios are not about finding clues, they're about interpreting the clues you do find.*

The central question becomes *What will the heroes do with the information once they've got it?* — new information opens choices; withheld information is a null result that produces the 5–20 minute workaround GMs invent on the fly. GUMSHOE cuts the workaround and makes clue-finding **all but automatic** provided you are in the right place, have the right ability, and say you use it.

Key contrast to D&D / Fate / Blades / Tricube:

- **No roll for investigative abilities** — if the ability matches a clue in the scene, you get it. The ability's rating/pool never determines *whether* you get a core clue, only what *extra* you can buy.
- **Pool vs. Rating split** — `rating` is permanent capability; `pool` is spendable spotlight that refreshes between cases. Investigative pools refresh only between cases; most general pools refresh between cases, physical pools (Athletics/Driving/Scuffling/Shooting) refresh every 24h game time, Health 2/day, Stability between cases.
- **General abilities carry uncertainty** — single `1d6 + spend` vs. hidden Difficulty (usually 4, range 2–8). Spend represents exceptional concentration you can only muster a few times per case.
- **Stability/Health can go negative to −12** — past 0 you track graduated Hurt / Seriously Wounded / Dead (or Shaken / Mentally Ill / Incurably Insane), per SRD §Exhaustion/Injury and §Losing It.
- **Scenario structure is load-bearing** — trail of clues, scene types (Intro/Core/Alternate/Antagonist Reaction/Hazard/Sub-Plot/Conclusion), and five clue sub-types (Floating/Leveraged/Pipe/Restricted/Timed) matter more than raw rules.

### Design Pillars

- **Player-facing** — the GM never rolls for NPCs when a PC alternative exists; supporting characters don't test unobserved actions (§Tests and Supporting Characters).
- **Elastic participation** — for groups >2, assume everyone is *kind-of* present in every scene; don't audit presence logically (§Being in the Right Place).
- **Spend = spotlight** — pool points are a literary abstraction: exhausting your Architecture pool means you've used your Architecture spotlight for this case, not that your character forgot architecture.

### Core Loop

```
Scene framing (location + supporting cast) → Players declare ability use → GM checks clue registry
  → Investigative match = automatic core clue (no roll) + optional 1–2 point spend for special benefit
  → Otherwise: General Test/Contest required (declare spend → roll 1d6 blind to Difficulty → resolve)
  → Consequences: Health/Stability loss, contest loss, or 0/1/2 benefit ticks
  → Log spend/pool deltas → narration → next scene (SCENE card when core + secondaries exhausted)
```

Longer structures: **Challenge** analogues are **Continuing Challenges** (accumulate successes vs. pool Difficulty at fixed Difficulty 4 per test) and **Contests** (alternating tests until first failure, Difficulty usually 4 per side, possibly asymmetric).

This repo implements the **scene → clue → test/contest → Health/Stability** loop plus minimal downtime (pool refresh, improvement, psychological triage). Full campaign hazard/vehicle/creature breadth is referenced but not fully simulated in v1.

---

## 2. Characters

### 2.1 Ratings vs. Pools (SRD §Ratings and Pools, §What Do Pool Points Represent?)

| Term | Meaning | Lifetime |
|---|---|---|
| **Rating** | Permanent max bought with build points at chargen; only grows via Improvement (2 pts/session). | Static within a case |
| **Pool** | Spendable points, starts equal to rating at start of case; fluctuates wildly within a case. | Volatile |

> The distinction between ratings and pools is a crucial one. — SRD §Ratings and Pools

If you have rating `0` in a General ability you normally cannot test it at all (Unforgiving) or can at bare die with no spend (Forgiving — see §3.5). If you have rating `1` in an Investigative ability you are already highly competent.

### 2.2 Step One — Concept (SRD §Step One: Concept)

Freeform character concept + optional setting packages:

- **Stereotype** (narrative only, e.g. Good Girl from *Fear Itself*) — guide.
- **Package** (e.g. Ashen Stars *Hailer*) — minimum Investigative + General requirements before you spend elsewhere.
- **Occupation** (Trail of Cthulhu variant) — two rating points per one build point spent on occupational abilities; leftover half-points lost; may grant Special (e.g. Private Investigator spends *after* rolling).

Implementation stores `concept: str`, `stereotype/package/occupation: str|None`.

### 2.3 Step Two — Investigative Abilities (SRD §Step Two: Assign Investigative Abilities)

Build-point pool scales with player count:

| # regularly attending PCs | Investigative Build Points |
|---|---|
| 2 | 80% of `x` (where `x` = count of Investigative abilities in your game) |
| 3 | 60% of `x` |
| 4 | 55% of `x` |
| 5+ | 50% of `x` |

Irregulars don't count toward the denominator but get the same personal total as regulars.

- **Free rating**: setting may grant +1 free in one assumed ability (e.g. Cop Talk if everyone is police).
- **Benchmarks**: better to spread thin — many abilities at 1–2 than one at 6. Even 1 point is worth having. Rarely go above 3–4. You need rating ≥1 to get useful info from that ability.
- **Deferred spend**: after covering the group's checklist (GM's Investigative Ability Checklist + Investigator Roster), you may *hold back* unspent points and assign them mid-play as if you'd had them all along.

### 2.4 Investigative Ability List (SRD §Investigative Abilities; ~50 canonical)

Categories are for lookup only; each may overlap.

| Category | Abilities (canonical SRD) |
|---|---|
| **Academic** | Anthropology, Archaeology, Architecture, Art History, Botany, Comparative Religion, Forensic Accounting, Forensic Psychology, Geology, History, Languages, Law, Linguistics, Natural History, Occult Studies, Pathology, Research, Textual Analysis, Trivia, + Astronomy* |
| **Interpersonal** | Bullshit Detector, Bureaucracy, Cop Talk, Flattery, Flirting, High Society, Inspiration, Interrogation, Intimidation, Negotiation, Oral History, Reassurance, Respect, Streetwise, Tradecraft, Impersonate |
| **Technical** | Astronomy, Ballistics, Camping, Chemistry, Craft, Cryptography, Data Retrieval, Document Analysis, Electronic Surveillance, Evidence Collection, Explosive Devices, Fingerprinting, Forensic Anthropology, Forensic Entomology, Languages*, Locksmith, Photography, Traffic Analysis, + Astronomy/others flagged with * cross categories per setting |

*\*Assignments vary by setting; keep canonical 50 and let setting rename/prune. E.g. Astronomy is Technical here; in Ashen Stars it may be Academic.*

Exotic Investigative abilities (setting-dependent): `Analytic Taste` (taste as chemical lab), `Aura Reading` (2 pts to read emotion, 4 pts to detect spirit/health). Treat as Technical/Academic with special costs.

Each description in SRD lists 2–5 bullet uses (e.g. Evidence Collection: spot objects of interest; reconstruct sequence; bag without contamination). Store those as tool flavor, not mechanics.

### 2.5 Step Three — General Abilities (SRD §Step 3: Assign General Abilities)

Each player gets **60 build points** regardless of group size (assumes ~12 broadly useful abilities; specialized settings add a second pool).

- Everyone starts with **1 Health** and **1 Stability** (plus any other ablative ability the setting requires) *before* spending.
- No hard cap, but **second-highest rating must be at least half the highest** (so if you have a 16, your next best must be ≥8) — enforces breadth.
- **Benchmarks**: 1–3 = sideline, 4–7 = solid, 8+ = dedicated bad-ass + unlocks **Cherry** (persistent benefit even at pool 0) + Hit Threshold 4 if Athletics ≥8.

### 2.6 General Ability List (canonical SRD ~25 + Exotics)

| Ability | Cherry at 8+ (SRD §General Abilities) |
|---|---|
| **Athletics** | Hit Threshold 4 (otherwise 3) |
| **Business Affairs** | — (setting-specific) |
| **Conceal** | — |
| **Disguise** | — |
| **Driving** | +1 vehicle type per point (motorcycle/truck/helo/plane/hovercraft/tank) |
| **Explosives** | Doubles as Investigative for bomb reconstruction / maker profiling |
| **Filch** | — |
| **Fleeing** | — |
| **Gambling** | — |
| **Health** | Pool may go to −12; injury rules apply |
| **Hypnosis** | — |
| **Infiltration** | — |
| **Mechanics** | — |
| **Medic** | Grants Pathology 1 free at rating 8+; 1 Medic → 2 Health (self → 1 Health); 2 Medic stabilizes Seriously Wounded |
| **Piloting** | — |
| **Preparedness** | Narrate having retroactively packed the needed item |
| **Public Relations** | — |
| **Riding** | — |
| **Scuffling** | Also Investigative to infiltrate dojo / gather fighter gossip (if permissive setting) |
| **Sense Trouble** | May act first in contests at higher pooled rating |
| **Shrink** | 1 Shrink → 2 Stability; 2 Shrink → temporary lucidity or suppress mental illness for remainder of scene; 3× Difficulty 4 tests + 3 stable scenarios cures mental illness |
| **Shooting** | Also Investigative for ballistics gossip / range culture |
| **Stability** | Pool may go to −12; Stability loss table applies |
| **Surveillance** | — |
| **Exotic General** | Mutant Power: Blood Spray, Pathway Amplification, Viroware: Dominator, plus per-setting Cherries (e.g. Crackers' Crypto) |

General abilities may double as Investigative when gathering gossip or accessing a subculture tied to the skill (permissive settings like *Night's Black Agents*) — restrictive settings (*Ashen Stars*) keep them separate. Implementation flags `permissive: bool`.

### 2.7 Drives

Per SRD §Drives (e.g. Altruism) — narrative motivation that the GM invokes to break speculation stalls ("which choice most suits your Drive?"). No mechanical cost; used for prompting. Store `drive: str`.

---

## 3. Core Mechanics

### 3.1 The Die

**Every roll uses one ordinary six-sided die** (SRD §Die Rolls). Lineage (`1d6`, `2d6`, `d20`) is irrelevant — keep the `dnd_tools.dice` pattern but add a GUMSHOE-specific `1d6+spend`.

```
result = roll_1d6() + spend   (spend = 0..pool, any amount you wish before seeing Difficulty)
success if result >= Difficulty
```

The GM **never reveals Difficulty before you commit spend** (SRD §Simple Tests — emotional dissonance is intentional). Exception: Toll Tests (§3.8) do reveal it.

### 3.2 Difficulty Scale (SRD §Difficulty Numbers and Story Pacing)

| Difficulty | Label | When to use |
|---|---|---|
| 2 | Very Easy | Near-automatic; pacing filler only |
| 3 | Easy | Grant real advantage but not load-bearing; lowered Stability test when inured |
| 4 | Standard | **Default** — essential momentum obstacles, chases, Stability tests, Surprise avoidance |
| 5 | Hard | Flagged advantage; susceptible Stability test |
| 6 | Very Hard | Interesting but nonessential benefit |
| 7–8 | Extreme | Cap for GUMSHOE; reserve for 4-point spends or highly penalized Called Shots |

Rule: **essential narrative momentum = ≤4**; justify ease fictionally (passed-out patrol) rather than raising Difficulty. If an essential General obstacle must be passed, allow success regardless of roll but inflict a non-HP/Stability cost (injury, complication) instead of blocking.

### 3.3 Simple Tests (SRD §Simple Tests)

One character, no active opposition (driving, jumping, sneaking, shooting a target, disconnecting alarms, Stability).

1. Player states goal + ability.
2. Player commits `spend` from that ability's pool (any 0..current pool, before seeing Difficulty).
3. GM has secretly set Difficulty (2–8, default 4).
4. Roll `1d6 + spend` vs. Difficulty → `success | fail`.
5. On `fail` you cannot retry unless you do a *credible supporting action* that improves odds, and then you must spend **more than you spent on the failed attempt** (if you can't afford it, no retry). Failure otherwise has consequences (Harm, cost, missed opportunity) — if no interesting consequence exists, don't call for a test at all (grant automatic success, optionally charge a General Spend).

**No double-spend gate**: the test is your best shot; theatrics of retry spam are prohibited.

### 3.4 Piggybacking & Cooperation (SRD §Piggybacking, §Cooperation)

**Piggybacking** — group acts *together* as one effort (e.g. sneaking as a unit, lifting together):

- Elect a **leader** who makes the Simple Test with any spend.
- Each helper pays **1 point** from the same ability pool *not added to the leader's roll* — the cost of tagging along.
- For each helper who cannot/will not pay, **Difficulty +2**.

Not every task qualifies (only one can drive).

**Cooperation** — two characters assisting one goal but distinct roles (leader + assistant):

- Leader may spend any amount, added to the roll.
- Assistant may pay any number from their pool; **all but 1 point is added to the roll** (`assistant_contribution = max(0, spend-1)`).
- Elect leader / assistant before committing.

**Continuing Challenges** (§Continuing Challenges) — when repeated effort feels right (battering a door, penetrating a firewall):

- Assign obstacle `pool = Difficulty if done at once unaided` (typically 8+, often much higher).
- Run individual Simple Tests at **Difficulty 4** each, with any legal cooperation/piggybacking.
- Accumulate `roll+spend` successes; when sum ≥ obstacle pool, task done.
- **Failed tests contribute 0** and do not accumulate.
- Cannot make an impossible task possible merely via continuing challenges.

### 3.5 Tests Without Ability & Lucky Shots (SRD §Making General Tests Without Abilities, §Lucky Shots)

Two campaign switches:

- **Forgiving** (heroic): you can test *any* General ability even with rating 0 or pool 0.
- **Unforgiving** (grim/horror): you can test a General ability only if rating ≥1 (pool may be 0); rating 0 = cannot test.

**Lucky Shot** (Forgiving only): once per episode, per *entire cast* (not per player), a rating-0 character may attempt a task desperate to the plot. Requires **unanimous permission** from all other players (they forfeit their own future Lucky Shot). Spend up to 4 points from your *highest current* General pool, add to roll. On success must describe outcome as fluky/embarrassing *or* credit the PC with highest rating in that ability (even if not present).

### 3.6 General Spends (SRD §General Spends)

For tasks with no reasonable chance of failure but where effort matters: charge **1–2 points** per contributing character from the relevant General pool, no roll. Multiple can chip in. Used for toll-like tasks and automatic successes that should still cost spotlight.

### 3.7 Toll Tests (SRD §Toll Tests, from Ashen Stars)

Success is assured *if* you want it enough, but cost is uncertain:

1. GM **reveals Difficulty** (base 6, modifiable upward).
2. Roll `1d6` with **no declared spend**.
3. Compare `roll` to Difficulty; you then choose to spend `Difficulty - roll` (if positive) to succeed, or to fail and keep your points.
4. No blind commit; pure cost-benefit analysis.

Use for building things, crafting, or other engineering where question is *how much* effort, not *whether* it's possible.

### 3.8 Zero-Sum Contests (SRD §Zero Sum Contests)

When *something* will happen to *someone* and you need to know *who* (positive = best wins a benefit, negative = worst takes the hit):

- GM announces `open Difficulty` + `positive | negative`.
- Each player **secretly** writes down spend from the relevant pool.
- All roll `1d6 + spend`, reveal simultaneously.
- Highest gets benefit / lowest takes hit.
- **Tie-break**: tied players may spend additional points to break tie; if still tied GM decides on story grounds. GM may cap max spend.

Use sparingly for negative contests; ensure consequence is distressing but not permanently harmful unless players had a fair avoidance chance.

### 3.9 Contests — General (SRD §Contests)

When two characters actively thwart each other (chase is prototypical):

- GM decides who acts first: chaser flees first; otherwise **lowest rating in the contested ability acts first** (so underdog gets a chance); ties: supporting character before PC; PC-vs-PC ties: last-arriver goes first.
- Turns alternate: actor tests at **Difficulty 4** (or asymmetric if one side advantaged — GM gives favored side lower Difficulty).
- **First to fail loses; the other wins.** Flavor each result narratively, don't just recite arithmetic.
- Contest does not end on a successful roll — it ends on the first failure.

### 3.10 Fighting — Contests with Damage (SRD §Fighting)

Fights are Contests using `Scuffling` (close) or `Shooting` (ranged). Range is hand-waved (handguns 50m, rifles 100m; dramatic reload).

**Initiative** (player-facing):

- **Scuffling**: PC goes first if `PC Scuffling rating >= opponent Scuffling`.
- **Shooting**: PC goes first if `PC Shooting rating > opponent Shooting`.
- Otherwise opponent goes first.
- PC vs. PC: higher rating goes first; rating tie → higher pool; still tie → die odd/even.

**Hit Threshold** (the Difficulty the *attacker* must meet):

- `3` normally; `4` if defender's `Athletics >= 8`; creatures may be 4+ regardless; weak mooks may be 1–2.
- Cover modifies: Exposed −1, Partial 0, Full Cover +1 (SRD §Cover).
- A target with Athletics 8+ is meaningfully harder to hit.

**How an attack resolves**: on your turn you make a Simple Test of Scuffling/Shooting vs. the defender's Hit Threshold (spend any amount from that combat ability). If `1d6 + spend >= Hit Threshold` you **may deal damage**.

**Damage table** (SRD §Dealing Damage):

| Weapon | Damage Modifier |
|---|---|
| Fist / kick | −2 |
| Small improvised / baton / knife | −1 |
| Machete / heavy club / light firearm | 0 |
| Sword / heavy firearm | +1 |
| Firearm at **point-blank** | **+2** additional |

Supernatural creatures may have +4 to +16. **Never spend combat pool points to boost damage** — only to hit. Roll `1d6 + modifier` (with point-blank bonus if applicable) and subtract from defender's **Health pool**.

### 3.11 Fighting Without Ability, Armor, Called Shots, Combat Options, Running Away — condensed

- **Without ability** (rating 0): −2 damage, declare action early (cannot change), go last, and on `natural 1` with a firearm you hit self/ally (§Fighting Without Abilities).
- **Armor**: light vest −2 vs bullets / −1 vs blades; military vest −3 vs bullets; heavy/double drawbacks; creature armor may be higher and typed.
- **One Gun, Two Combatants**: charging a ready gun >5ft = auto-hit, damage tripled; pistol scramble = Scuffling contest for the gun; rifle scramble = heavy club Scuffling.
- **Ammo**: dramatic reload by default; if tracking, Difficulty 3 Shooting test to quick-reload or lose round's attack.
- **Cover**: Exposed (−1 Hit Thresh), Partial (±0), Full (+1).
- **Non-lethal**: never more effective than lethal (tasers intentionally underperform to prevent exploit).
- **Called Shots** (optional, combat-oriented games): +1 to +4 Hit Threshold for precision, with extra damage (+2 head/throat/chest, +3 heart/eye/joint-lock) and optional 6-point spend to drop Hurt→Seriously Wounded or Seriously Wounded→kill.
- **Combat Options** (e.g. Mook Shield: rating 8+ + 3+ Scuffling spend to use a mook as −4 Armor + full cover; Martial Arts: Scuffling 8, 1/fight 4-pt refresh for evocative description) — prerequisites + point costs, vetted by GM.
- **Running Away**: Athletics test Difficulty `3 + #foes`; success → melee ends, you lead the chase; failure → highest-damage foe auto-deals one instance, melee still ends but you roll first in the chase (foe may forgo damage to spend 3 Athletics and block your exit).

### 3.12 Exhaustion, Injury & Death — Health (SRD §Exhaustion, Injury and Death)

Unlike most pools, **Health can go negative**, to −12.

| Health pool | State | Effects |
|---|---|---|
| **0 to −5** | **Hurt** | Cannot spend Investigative points; +1 to all Test/Contest Difficulties (including opponents' Hit Thresholds vs you). Recovers via Medic: 1 Medic → 2 Health (self → 1 Health), capped at pre-incident max; requires Medic's full attention. |
| **−6 to −11** | **Seriously Wounded** | Must make **Consciousness Roll** (see below); cannot fight regardless of consciousness; lose 1 Health / 30 min without first aid; first aid costs **2 Medic** (stabilizes, no restore); then hospital `|Health_min|` days; discharge → Health = ½ max; next day → full. |
| **−12 or below** | **Dead** | New character (improvement points only counted for sessions with current character). |

**Consciousness Roll**: Difficulty = `abs(Health)` before any voluntary strain. You may voluntarily lower Health further by `N` to add `+N` to the roll. If you fail, you lose consciousness.

**Bigger Fights** (§Bigger Fights): when groups engage, suprising side goes first; otherwise if any PC's Scuffling/Shooting rating ≥ any enemy's, PCs go first. Combat proceeds in **rounds** (each side's wave). PCs in left-to-right seating order; opponents in left-to-right target order (or GM convenience). Creatures may attack multiple times per round.

**Surprise** (§Surprise): avoid being surprised = Surveillance test Difficulty 4 + opponent Stealth Mod; surprise others = Infiltration/Surveillance Difficulty 4 + Stealth Mod. Surprised → +2 to all General Difficulties first subsequent action / first fight round.

### 3.13 Stability, Losing It & Mental Illness (SRD §Stability Tests, §Losing It, §Mental Illness)

Stability mirrors Health but for the mind. Trigger = incident (being attacked, seeing creature/grisly scene, friend dies, supernatural attack).

**Test**: Stability at Difficulty 4 (GM may shift 3 if inured, 5 if susceptible). Spend from Stability pool to add to roll. On failure lose Stability per incident table; worst incident in scene caps loss (spent bonus points are still lost even if capped).

| Incident | Stability Loss |
|---|---|
| Human opponent attacks (intent to harm) | 2 |
| Vehicle accident with injury risk | 2 |
| Human opponent attacks (intent to kill) | 3 |
| See supernatural creature (distance) | 3 |
| See supernatural creature (close) | 4 |
| See grisly murder/accident scene | 4 |
| Learn friend/loved one violently killed | 4 |
| Discover corpse of friend/loved one | 6 |
| Attacked by supernatural creature | 7 |
| See friend/loved one killed | 7 |
| See friend/loved one killed gruesomely | 8 |
| (Higher for overwhelming entities at GM discretion) | 8+ |

**Losing It** — Stability can also go to −12:

| Stability | State |
|---|---|
| **0 to −5** | **Shaken** — +1 to all General Difficulties; Investigative spends require a test vs Difficulty = `abs(Stability)` (may voluntarily lower Stability to add +N as with Consciousness; fail → still spend but must roleplay impairment). |
| **−6 to −11** | **Mentally Ill** — also Shaken plus acquire **mental illness** (see below) and permanently lose **1 Stability rating** (must be repurchased). |
| **−12 or below** | **Incurably Insane** — one last self-destructive heroic/destructive act or gibber, then shipped to psych facility; new character. |

Mental Illness (SRD §Mental Illness, tailored by setting):

- If mundane trigger → **PTSD**: freeze up on reminder, Stability Difficulty 4 to resist, 15 min paralysis + 24h Shaken.
- If supernatural trigger → roll/choose: `1 Delusion` (other players conspire that one world-detail was never true), `2 Homicidal Mania` (secretly told a PC is a monster), `3 Megalomania` (GM lies about success until player leaves room), `4 Multiple Personality` (another player controls character under stress), `5 Paranoia` (players act as if conspiring with GM), `6 Selective Amnesia` (group picks a forgotten fact like being married / a killer / a bestselling author).

**Psychological Triage** (§Psychological Triage, §Head Games):

- `1 Shrink → 2 Stability` to recipient; `2 Shrink → temporary lucidity` (remainder of scene).
- Mental illness cure: Shrink-administered **Stability 4 test** at start of each scenario; after **three consecutive successes** *and* three consecutive scenarios where patient never drops ≤0 Stability, illness goes away — but if the character ever relapses they regain the *same* old illness and can never be cured again.
- During a scenario a successful Shrink test suppresses symptoms until the next Stability loss.

### 3.14 Other Supporting Systems

- **Piggybacking/Cooperation/Continuing Challenges**: §3.4.
- **Surprise/Armor/Cover/Ammo/Range/Called Shots/Combat Options/Running Away**: §3.11.
- **Hazards** (SRD §Hazards — Electricity/Mild 1 Health, Moderate 2 + lose 4 actions @3 Athletics/action, Extreme `1d6+4` — with alien fungal/ion storm/temporal shock variants; Fire −2/0/+2 by exposure; Suffocation 2 min free then 1 Athletics/10s then 1 Health/5s; Toxins −2 to +16 by lethality): implement as typed hazard descriptors yielding Health/Stability/pool damage, not a separate dice system.
- **Scenario Design** (§Designing Scenarios, §Running Scenarios): see §5 for implementable clue/scene registry.

---

## 4. Gathering Clues (Investigation Subsystem)

### 4.1 The Three Preconditions (SRD §Gathering Clues, §Giving Out Clues)

You get a clue **iff** you satisfy all three — and then you **cannot fail** (no die roll):

1. **Be in the right place** (the scene where the clue lives; elastic participation forgives most presence nitpicks).
2. **Have the right ability** (any rating ≥1 in the listed Investigative ability; GM designation is one *possibility*, not a straightjacket — credit any plausible alternative).
3. **Say you use it** (active phrasing `"I use Evidence Collection to search the scene"` *or* general fishing `"I search the crime scene"` interpreted by GM via loose matching; passive clues may be volunteered by GM without prompting when players are hot, or volunteered earlier when bogging down).

An ordinary person wouldn't need an ability (bloody footprint, envelope taped under table) → **Simple Search** (§Simple Searches) — no ability required, auto-clue via call-and-response or direct narration. Assign to thematically suited / spotlight-starved / highest Evidence Collection PC.

### 4.2 Core vs. Non-Core (SRD §Core Clues, §Clues)

- **Core clue**: the one clue per scene you *absolutely need* to advance to the next scene / to the end. **Cost 0**, always available. GMs avoid gating core clues behind obscure abilities, and the build-point table guarantees group coverage. Extra flavor beyond the core may be gated as spends.
- **Non-core 0-point info**: consequential but free minor tidbit, available with trigger ability at no cost.

### 4.3 Special Benefits / Investigative Spends (SRD §Special Benefits, §What Good Are Investigative Ratings?)

Beyond the core, scenario notes may list **special benefits** purchasable for **1 or 2 points** from the relevant Investigative pool:

- The GM tells the player the cost (1 vs 2) before they decide.
- Benefits are never required for forward momentum; they provide flavor, spotlight, future leverage (impressing an NPC), or a **forward leap** (a clue that would otherwise only appear later).
- Players may *propose* their own benefit — if persuasive/entertaining, GM may grant even if not in notes, or let the player specify details (narrative control).
- If the GM has no applicable benefit and cannot improvise one, the proposed spend **costs 0** (pool unchanged).
- Whether a core clue is floating or not, any additional info tied to the same ability test is a spend for that ability.

Cost is 1 or 2 only; never 3 (unlike General spends). The SRD caps benefit spend proposals at 1–2 per clue offer.

### 4.4 Inconspicuous Clues (SRD §Inconspicuous Clues)

Things you'd notice *without* actively looking (concealed door, blood droplet in immaculate lobby, bomb under vehicle, suspicious demeanor). Don't ask players to checklist their abilities in transitional scenes.

Instead ask: *who has highest current pool in the ability?* (default `Evidence Collection` for generic search). Ties: highest **rating** wins; still tied: both notice simultaneously. This is the sole place where *current pool* — not rating — decides who finds a clue.

### 4.5 Clue Sub-Types (SRD §Clue Types, §Timed Results)

Scenarios use five special clue types (beyond simple core/alternate):

| Type | When to use | Mechanic |
|---|---|---|
| **Floating Core** | Control pacing; prevent premature leap *or* skip filler | Not anchored to one scene — GM decides *during play* which of several candidate scenes delivers it, guided by whether players are having fun (hold) vs. bored/frustrated (release early). |
| **Leveraged** | Reward synthesis: `prior clue + interpersonal ability` convinces a resistant witness | Interpersonal ability *plus* citation of prerequisite core clue → new core clue. Prerequisite is itself a core clue by definition. |
| **Pipe** | Lay exposition that pays off much later ("laying pipe") | Early clue whose significance only lands when combined with a later component; GM may need to prompt memory across sessions. |
| **Restricted** | Preserve esoterica — secret not everyone with the ability would know | Only *one* PC knows it; first eligible actor to trigger gets it; GM picks by highest pool / least spotlight / background fit if no clear actor. Even others with same ability remain ignorant. |
| **Timed Result** | Lab / forensic delay as pacer or rescuer | Evidence submitted, results arrive after GM-chosen interval (phone call from lab) — either a delayed core clue *or* a reinterpretation prompt for old clues. Useful to cut a dead scene or redirect a bored one. |

Implementation stores each clue as `{id, scene, type: core|alternate|floating|leveraged|pipe|restricted|timed, abilities: [names], cost: 0|1|2, prerequisite: clue_id|None, timing: {delay_scenes|interval}, benefit: str|None}`.

---

## 5. Running the Game — GM Guidance (Implementable)

### 5.1 Mystery Structure (SRD §Mystery Structure, §Designing Scenarios)

Every case needs:

- **Investigation trigger** (ritual murder, supernatural sightings — the hook).
- **Sinister conspiracy** (who, what done, what trying to do, how trigger fits, victory condition = what stops them).
- **Trail of clues** (reverse-engineered from conspiracy back to trigger).
- Optionally **Antagonist reactions** — conditions → actions (destroy evidence, plant false lead, intimidate/attack PCs including pre-emptive strikes).

Authors write structure notes, not story — story emerges from player-driven scene traversal.

### 5.2 Scene Types (SRD §Scene Types)

| Type | Role | Core clue? |
|---|---|---|
| **Introductory** | Premise; Mr Verity briefing or direct emergency rendezvous | May have one |
| **Core** | At least one core clue; typically points to another Core scene; avoid single hard-sequenced chain — allow branching / improvised reordering | **Yes** (≥1) |
| **Alternate** | Context / redundant path / exculpatory red-herring removal — useful but not load-bearing | No (but may mirror a Core's info differently) |
| **Antagonist Reaction** | Danger/trouble pushed by villains; can float to kick pace | Optional |
| **Hazard** | Impersonal danger requiring tests/contests | No (but may gate info as Hybrid) |
| **Sub-Plot** | Wheel/deal/explore free of main plot — flavor, long arcs | No |
| **Conclusion** | Final hazard or antagonist reaction; may be player-initiated bust-in; often big fight but clever avoidance is valid | Resolution |
| **Hybrid** | General challenge *plus* information. Only grant a *core* clue as a reward for overcoming obstacle if that same core is also available elsewhere (otherwise you violate "core never fails"). | Conditional |

Add `lead_ins: [scene_id]` and `lead_outs: [scene_id]` per scene header; validate via scene diagram (arrows must allow ≥2 valid orders for core+alternate chain).

### 5.3 GM Principles to Encode

- **Err on giving, not withholding** (§Having the Right Ability, §Being in the Right Place).
- **Any plausible ability works** — don't gate on the exact label you wrote.
- **Passive vs Active is a pacing dial**: volunteer passive clues when players are cooking; otherwise let them ask; interpolate hints like *"He seems smitten"* (Flattery) or *"Wannabe cop on scanner"* (Cop Talk) when they stall (§Using the Right Ability).
- **Elastic participation**: assume everyone is there; don't punish split-party pedantry.
- **GUMSHOE vs Traditional style is one step**: Traditional *Player → Roll → Success → GM gives info*; GUMSHOE *Player → GM checks sheet → GM gives info* (no die) — otherwise identical (§Rolling for Clues and the GUMSHOE Style).
- **Avoid Negation / Leading & Following** — embrace player suggestions (half-right + twist) rather than swatting them; follow when players are creative, lead when they're stuck (§Avoid Negation, §Leading and Following).
- **Ending Scenes**: when core + most secondaries are gone and action drags, hold up a card / play a musical sting that means SCENE — players learn to self-cut (§Ending Scenes).
- **Tip to bake into player prompt**: *If more than one explanation fits your current clues, you need more clues — get out and gather information* (§Tip For Players: Containing Speculation).

### 5.4 Records the Tool Must Keep (SRD §Records are your Friend)

Two checklists updated at chargen and between sessions:

- **Investigative Ability Checklist** (scenario authoring): which abilities appear as clue gates; aim for wide coverage.
- **Investigator Roster** (GM's view): each PC's investigative choices; consulted for inconspicuous ties, spotlight balancing, and improv prompts ("you have 3 in Art History → add forged artwork").

---

## 6. Regaining, Improvement & Opposition

### 6.1 Regaining Pool Points (SRD §Regaining Pool Points)

| Pool | When it refreshes |
|---|---|
| **Investigative** | End of each **case** (not session). Long globe-hopping cases may designate mid-case breakpoints where all investigative pools refresh. |
| **Health** | `2 / day` of restful activity (hospitalization uses wounded timeline instead). Medic can patch mid-session: `1 Medic → 2 Health` (self → 1), cap = pre-incident value. |
| **Stability** | Calm undisturbed time with uninvolved friends/loved ones **between cases** (automatic if personal lives are background; if soap-opera campaign, requires intact support network — no network → no refresh). Shrink can restore mid-episode: `1 Shrink → 2 Stability`. |
| **Athletics, Driving, Scuffling, Shooting** | `24h` game-time since last expenditure (physical fatigue model). |
| **All other General** | End of each case (like Investigative). |

Wounded characters do **not** use the 2/day rule — they use the Seriously Wounded hospitalization arc (§3.12).

### 6.2 Improving Your Character (SRD §Improving Your Character)

At the **end of each investigation**, each player gets **2 build points per session they attended with their *current* character** (dead characters don't earn for sessions they missed; short-burst play may scale). Spend to raise any Investigative or General ability, or acquire new ones. Narrate new abilities as "*always had it, now revealing it*" if needed.

### 6.3 Opponent Statistics (SRD §Opponent Statistics, §Sample Creature Stat Blocks)

You only stat opponents who must be **overcome via General abilities**. Witnesses/suspects need only a text description + which interpersonal abilities they respond to.

Per opponent store:

- `Abilities: {General: rating}` (e.g. Lipovore: Athletics 6, Health 18, Scuffling 12, Shooting 8, plus two shipboard 8/4; Cattle Herbivore: Ath 8/Health 8/Scuffling 8 + gore +2).
- `HitThreshold, WeaponDamage, Armor` (typed: bullet vs blade; −2/−3 for light/military vests; creature armor 0–3+).
- `AttackPattern: [spend/round hints]` — fallback only; prefer story logic; increase spend after each miss until hits or pool empty.
- `Alertness Modifier` (applied to Infiltration/Surveillance Difficulty vs that foe; second value after slash = gear-neutralized).
- `Stealth Modifier` (applied to Surveillance to spot *them*).
- Animal benchmarks provided in SRD (Aggressive Herbivore cattle/rhino/triceratops/sauropod; Apex Predator lion/megafauna/monster; Pack Predator dog/wolf — see stat table in §3.12 for canonical values).

---

## 7. Example Play (SRD-true paraphrase, condensed)

```
GM: The warehouse office is dusty; a faint metallic tang hangs in the air.
    [Scene: Core; Lead-Out: Follow the Residue, The Foreman]

Player (Evidence Collection 2): "I sweep the floor and desk for trace."
GM: [Core clue, Investigative; ability Evidence Collection; cost 0]
    You find a smear of pale fungal residue under the desk and a torn shipping
    manifest — core clues, no roll. What do you do?

Player: "Can I get more from the residue?"
GM: [Special benefit, cost 1 Forensic Entomology] "Spend 1 and you can
    tell this is a lab-grown strain, not a natural bloom — would have shown up
    only later as a pipe clue, but you get it now as a forward leap."
Player: *spends 1 Forensic Entomology (pool 2→1)* → learns strain is
    engineered for cold storage — tags victim to a specific cryo-lab.

Later — Contest / Fighting:

GM: The foreman bolts for the back door.
Player: "I chase!"
GM: Contest of Athletics. You act first (your 6 vs his 4? No — lowest rating
    acts first, so he goes; ties: supporting before PC). Difficulty 4 each.
Foreman rolls 1d6+1=4 → success; Player rolls 1d6+0=3 → fail → foreman escapes.
But the shot — Player draws pistol.
GM: Scuffling? No — Shooting vs Hit Threshold 3 (your victim's threshold is 3).
Player spends 2 Shooting (pool 8→6), rolls 1d6=2 → total 4 ≥ 3 → hit.
Damage: roll 1d6=5 +0 (light firearm) =5 → victim Health 7→2 (Hurt: +1 to all
    Difficulties next tests).

Stability trigger: another PC discovers the friend's body in the freezer.
GM: "Stability test Difficulty 4." Player spends 1 Stability (4→3), rolls 3 →
    total 4 → success, no loss. Had they failed they'd lose 6 Stability per table.
```

---

## 8. Implementation with `dnd-tools` + `dnd-campaign` via LLMs

> Goal: keep `packages/dnd-tools` **untouched** for paper-metrics fidelity; build GUMSHOE as a new additive mode on top, with `dnd-campaign` handling multi-case horizons. Both packages expose **tool-grounded** LLM loops via `tau-ai` / `tau_agent`.

### 8.1 Architecture

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

packages/gumshoe/src/gumshoe/              # new additive package (or subpackage gumshoe/ under dnd_tools)
  models_gumshoe.py  GumshoeCharacter, Clue, Scene, Hazard, Opponent
  dice_gumshoe.py    roll_1d6_plus_spend(), consciousness_roll(), stability_roll()
  state_gumshoe.py   GumshoeState (pools, scenes, clue registry, Health/Stability, contest state)
  tools_gumshoe.py   GumshoeTools — 20+ typed tools (see §8.5) + OpenAI schemas + dispatch()
  prompts_gumshoe.py GM_PROMPT_GUMSHOE / PLAYER_PROMPT_GUMSHOE
  agents_gumshoe.py  Tau harness wrappers + heuristic (spend-aware greedy)
  simulation_gumshoe.py  Single-case loop (scene → clue → test/contest → Health/Stability)
  session_gumshoe.py Multi-case campaign (refresh/improvement/Timed Results)
  memory_gumshoe.py  summarize_gumshoe_state(), compact_transcript()
  cli_gumshoe.py     gumshoe demo / campaign
```

Alternative if not adding a new workspace member: keep `gumshoe/` under `packages/dnd-tools/src/dnd_tools/gumshoe/` with `models_gumshoe.py` etc., imported but never touching existing `models.py`/`tools.py`.

### 8.2 New Models (additive, isolated)

```python
from dataclasses import dataclass, field


@dataclass
class Clue:
    id: str                          # "warehouse_residue"
    scene: str                       # "warehouse_office"
    kind: str                        # core|alternate|floating|leveraged|pipe|restricted|timed
    abilities: list[str]             # ["Evidence Collection", "Forensic Entomology"]
    cost: int = 0                    # 0 for core, 1|2 for special benefits
    benefit: str | None = None       # "lab-grown strain → forward leap to cryo-lab"
    prerequisite: str | None = None  # for leveraged: clue id whose citation unlocks this
    timing: dict | None = None       # for Timed: {"delay_scenes": 1, "trigger": "lab_callback"}
    passive: bool = False            # auto-give on entry if True, pacing-dependent otherwise
    simple_search: bool = False      # no ability needed if True


@dataclass
class Scene:
    name: str
    kind: str                        # introductory|core|alternate|antagonist_reaction|hazard|sub_plot|conclusion|hybrid
    lead_ins: list[str] = field(default_factory=list)
    lead_outs: list[str] = field(default_factory=list)
    clues: list[Clue] = field(default_factory=list)
    hazard: dict | None = None       # {type, health_cost, stability_cost}
    antagonist: dict | None = None   # stat block ref if fighting/contest here


@dataclass
class InvestigativeRating:
    ability: str
    rating: int                      # ≥0; ≥1 to use; 1-2 is workhorse, 3-4 is specialist
    pool: int                        # starts == rating, refreshed end-of-case


@dataclass
class GeneralAbilityState:
    ability: str
    rating: int                      # 0..N; cherry triggers at 8; Health/Stability may go negative
    pool: int                        # starts == rating, 24h refresh for physical subset
    cherry_unlocked: bool = False    # rating >= 8


@dataclass
class GumshoeCharacter:
    name: str
    concept: str
    drive: str                       # "Altruism", "Curiosity", etc.
    investigative: dict[str, InvestigativeRating] = field(default_factory=dict)
    general: dict[str, GeneralAbilityState] = field(default_factory=dict)
    # Health/Stability are just general abilities but surfaced for convenience
    mental_illness: str | None = None   # PTSD|Delusion|Homicidal Mania|...
    shaken: bool = False
    hurt: bool = False                # Health 0..-5
    seriously_wounded: bool = False   # Health -6..-11
    hospital_days: int = 0
    # roster/bookkeeping
    build_points_earned: int = 0      # +2 per attended session with this incarnation
    last_refresh_case_id: str | None = None


@dataclass
class GumshoeState:
    characters: dict[str, GumshoeCharacter]
    scenes: dict[str, Scene]
    current_scene: str | None = None
    collected: set[str] = field(default_factory=set)   # clue ids already given
    pool_history: list[dict] = field(default_factory=list)
    tool_trace: list[dict] = field(default_factory=list)  # {tool, args, result, actor, round}
    transcript: list[dict] = field(default_factory=list)
    cases_complete: int = 0
    forgiving: bool = False            # campaign switch for rating-0 tests
    lucky_shot_used: bool = False      # once per episode, entire cast
    # mirrors GameState seed/map when mixing with grid
    seed: int = 0
    round: int = 0


@dataclass
class Opponent:
    name: str
    abilities: dict[str, int] = field(default_factory=dict)  # Health/Scuffling/Shooting etc.
    hit_threshold: int = 3
    armor: dict[str, int] = field(default_factory=lambda: {"bullets": 0, "blades": 0})
    weapon_mod: dict[str, int] = field(default_factory=dict) # "pistol": 0, "sword": +1
    alertness_mod: int = 0
    stealth_mod: int = 0
    attack_pattern: list[int] = field(default_factory=list)  # fallback per-round spends
```

`Health` and `Stability` live as `general["Health"]` / `general["Stability"]` so unified spend logic applies; convenience getters `get_health(c)` / `get_stability(c)` alias the pool (which may be negative, unlike other generals).

### 8.3 Dice Engine Extension (`dice_gumshoe.py`)

Add deterministic helpers seeded by `GumshoeState.seed` (re-seeded on restore):

```python
def roll_1d6() -> int:
    return _rng.randint(1, 6)

def roll_test(spend: int) -> dict:
    die = roll_1d6()
    return {"die": die, "spend": spend, "total": die + spend}

def consciousness_roll(current_health: int) -> dict:
    """Difficulty = abs(current_health); may voluntarily lower health to add +N."""
    difficulty = abs(current_health)
    # caller handles optional voluntary lowering before roll
    die = roll_1d6()
    return {"die": die, "difficulty": difficulty, "needs_voluntary": False}

def stability_test_total(spend: int) -> dict:
    die = roll_1d6()
    return {"die": die, "spend": spend, "total": die + spend}
```

Keep existing `roll_dice("1d20")` etc. untouched for 5e metrics.

### 8.4 GameState / CampaignState Additions

- **GumshoeState** shadows `GameState` fields it reuses (`seed`, `round`, `tool_trace`, `transcript`, `map`/`pos` for battles) for trace compatibility; it does not mutate 5e HP/AC semantics.
- **Investigative core = no roll**: the tool `gather_clue` (below) never rolls; it validates ability coverage, consumes pool only for 1–2 point benefits, and returns `automatic: true` vs `spend` payload. LLM narration may not contradict.
- **Pool refresh** mirrors SRD exactly: call `refresh_between_cases(case_complete=True)` to reset Investigative + other-General to rating, and Health +2/day helper; Stability refreshed only if `has_support_network` / soap-opera check passes; physical generals refreshed after 24h via `tick_clock(hours)`.
- **Consciousness / Shaken / Mental Illness** are applied atomically after Health/Stability drops below thresholds via `apply_health_effects` / `apply_stability_effects` (increase Difficulties +1, block Investigative spends behind Shaken test, appoint mental illness).
- **CampaignState** wrapping: `snapshot()` / `restore()` serialize characters + pools + illnesses + collected clues + scene graph + forgiving flag + lucky_shot_used + hospital timers; re-seed dice on restore; `checkpoint()` + `prune_traces()` unchanged (keep first ~10 + last 200 entries).

### 8.5 Tool Schemas (LLM-visible)

Each method logs to `state.log_tool` and returns JSON; errors are `{error: str}` dicts, never raises.

| Tool | Purpose | Key params |
|---|---|---|
| `gather_clue(character, scene, ability)` | **Authoritative investigative gate**: tests the three preconditions; returns core clue if ability ∈ scene's clue abilities (or any plausible alias), flags passive/simple-search, records benefit offers. No die. | `character`, `scene`, `ability` — `ability` may be omitted for simple searches |
| `spend_investigative(character, ability, cost, benefit_id)` | Spend 1–2 from Investigative pool for special benefit; validates benefit exists and cost matches; if no benefit available, costs 0 (pool unchanged). | `character`, `ability`, `cost 1|2`, `benefit_id` |
| `inconspicuous_check(scene, ability)` | Resolve inconspicuous clue: picks highest-current-pool (default Evidence Collection), tie → highest rating, still tie → both. | `scene`, `ability` |
| `simple_search(character, scene, detail)` | Resolve simple search (no ability needed): auto-clue + assignment heuristic (thematic / spotlight / highest Evidence Collection). | `character`, `scene`, `detail` |
| `set_difficulty(gm, ability, difficulty, hidden)` | GM sets Difficulty 2–8 for next test/contest (hidden=True by default; Toll reveals). Must precede any General test. | `gm`, `ability`, `difficulty 2..8`, `hidden bool` |
| `general_test(character, ability, spend, difficulty?)` | Authoritative `1d6+spend` vs hidden/revealed Difficulty; validates spend ≤ pool, forgiving vs unforgiving rating-0 check, lucky-shot gating, retry-must-spend-more rule. | `character`, `ability`, `spend`, optional `difficulty` override |
| `toll_test(character, ability, difficulty)` | Revealed-Difficulty toll: rolls 1d6 first, then prompt `spend = max(0, diff-roll)` or fail voluntarily. | `character`, `ability`, `difficulty 6+` |
| `general_spend(character, abilities_points: dict)` | Debit 1–2 per character from relevant General pools for auto-success tasks; validates multi-contributor map. | `character(s)`, `{ability: points}` |
| `cooperate(leader, assistant, ability, leader_spend, assistant_spend)` | Cooperation: `total = 1d6 + leader_spend + max(0, assistant_spend-1)`. | `leader`, `assistant`, `ability`, `spends` |
| `piggyback(leader, followers, ability, leader_spend)` | Piggyback: leader tests at `Difficulty+2*(unpaid followers)`, followers each pay 1 if able. | `leader`, `followers[]`, `ability`, `spend` |
| `contest_initiate(char_a, char_b, ability, difficulty_a, difficulty_b)` | Starts a Contest (including alternating-turn ordering: lowest rating first, supports before PCs, seating tie-breaks); stores contest state. | `char_a`, `char_b`, `ability`, `difficulties` |
| `contest_roll(character, spend)` | One step of a Contest; returns success/fail; if fail the contest ends and winner is the other side. | `character`, `spend` |
| `fight_initiate(attacker, defender, style: scuffling|shooting, point_blank)` | Determines initiative per §3.10; sets defender Hit Threshold (including cover/exposed). | `attacker`, `defender`, `style`, `point_blank`, `cover` |
| `fight_attack(attacker, defender, spend)` | Test vs Hit Threshold; on hit rolls `1d6+weapon_mod(+2 if point_blank)` → subtract from defender Health; applies Hurt/Shaken gates. | `attacker`, `defender`, `spend` |
| `consciousness_roll(character, voluntary_lower)` | At Health 0..−11: rolls vs `abs(Health)` with optional voluntary lowering; on fail → unconscious. | `character`, `voluntary_lower 0..N` |
| `stability_test(character, incident, spend)` | Stability Difficulty 4 (3 inured, 5 susceptible); on failure deducts per-incident loss (capped at worst-in-scene); applies Shaken/Mentally Ill gates. | `character`, `incident`, `spend`, `susceptibility` |
| `psychological_triage(healer, patient, spend)` | Shrink spend → Stability: 1→2, plus suppression/lucidity branches. | `healer`, `patient`, `spend` |
| `check_health`, `check_stability`, `check_pools`, `list_abilities`, `stability_loss_lookup` | Queries | `character` |
| `set_scene(name, kind, clues[])`, `advance_scene(next_scene)` | Scene graph authoring/traversal; floating clue selection via `select_floating_clue(scene_poll)` | `name`, `kind`, `clues` |
| `check_scene(character)` / `collected_clues(scene)` / `investigator_roster()` | Campaign inspection (ability checklist, spotlight) | |
| `leverage_clue(character, interpersonal_ability, prerequisite_clue)` | Leveraged clue unlock: prerequisite + interpersonal ability mention. | `character`, `ability`, `prerequisite` |
| `apply_hazard(character, hazard_id)` | Apply typed hazard (mild/moderate/extreme electric/fire/suffocation/toxin) → Health/ability damage. | `character`, `hazard` |
| `refresh_case()`, `heal_tick(days)`, `improve(character, ability, points)` | Between-case refresh, daily Health, spend 2/session build points. | |

**Retained 5e tools** where useful without edit: `check_valid_attack_line`, `move`/`move_player`, `visualize_map`, `get_names_of_all_players/monsters`, `check_side`, `roll_initiative` (or reuse contest ordering for fights).

**Campaign tools** delegate unchanged: `long_rest` (for mixing), `checkpoint`, `save_checkpoint`, `load_checkpoint`, `get_summary` (compact for prompt), `prune_traces`.

All expose `tool_schemas()` → OpenAI-compatible + `dispatch(name, args)` for the harness.

### 8.6 Agent Prompts & Harnesses

Reuse `agents.py` pattern verbatim — never subprocess, never raw LLM strings as truth.

```python
# prompts_gumshoe.py
GM_PROMPT_GUMSHOE = """You are the GM (transactional controller). Use tools for every
mechanical effect. For each scene: check clue registry via gather_clue / inconspicuous_check /
simple_search; Investigative uses are automatic when ability matches — never roll for them;
offer/execute 1–2 point special benefits only when scenario lists them (if none, cost 0).
For General tasks: set Difficulty blind (default 4, range 2–8, keep hidden except Toll at 6+),
call general_test / cooperate / piggyback / toll_test, enforce retry-must-spend-more,
and for chases/fights use contest_initiate → contest_roll. Track Health/Stability pools;
apply Hurt/Shaken gates, Consciousness rolls, mental illness, and psychological triage
strictly via tools. Narrate only from tool results. Say <End Turn/> ..."""

PLAYER_PROMPT_GUMSHOE = """You are a GUMSHOE player. Sense→plan→validate→act→communicate.
For clues: declare which ability you use and how it applies — call gather_clue; propose
specific spends for extra benefits; cite prerequisite clues for leveraged clues.
For uncertain actions: commit spend blind before seeing Difficulty, then general_test;
for help decide Cooperation vs Piggybacking, and for build/craft use toll_test.
In chases/fights: respect initiative (lowest rating first, support before PC), roll via
contest_roll / fight_attack. End with <DM/>; coordinate via <Call/>Name, msg<Call/>."""
```

Wire via `agents.py:_tools_to_agent_tools()` + `AgentHarness` (provider = `OpenAICompatibleProvider` for LMStudio at `:1234`):

```python
from dnd_tools.agents import make_tau_provider, _tools_to_agent_tools
from tau_agent.harness import AgentHarness, AgentHarnessConfig

tools = GumshoeTools(state)  # or CampaignTools(GumshoeCampaignState(...))
provider = make_tau_provider("http://127.0.0.1:1234/v1", "lm-studio")
harness = AgentHarness(
    AgentHarnessConfig(
        provider=provider,
        model="qwen3.6-35b-a3b-mtp",
        system=GM_PROMPT_GUMSHOE,
        tools=_tools_to_agent_tools(tools),
        max_turns=8,
    )
)
```

**Simulation loop** (`simulation_gumshoe.py` / `session_gumshoe.py`): keep `Simulation.run()` structure — `set_scene` → `gather_clue` (core + inconspicuous + simple searches) → optional `spend_investigative` gate → `set_difficulty` (blind) → `general_test`/`cooperate`/`piggyback`/`toll_test` → on success `apply_hazard`/`fight_attack`/`contest_initiate` forks → `consciousness_roll`/`stability_test` at thresholds → `psychological_triage` → `<End Turn/>`. For campaign, `CampaignSession.add_case()` initializes scene graph + floating clue pool + forgiving flag, `run_case()` delegates to Simulation, then `refresh_case()` / `heal_tick` / `improve` between cases, then `checkpoint()` + `prune_traces()`.

### 8.7 Determinism & Evaluation

- **Seeded RNG**: all `1d6` via `_rng` seeded from `GumshoeState.seed` / `CampaignState` snapshot; re-seed on `restore()`.
- **Authoritative state**: narration never overrides tool results; clue/pool/damage state is tool-true; tools are isolation boundary (return `error` not raise on misuse — harness catches).
- **Traces**: every tool call logs to `state.tool_trace` with `{tool, args, result, round, actor}` — same shape as 5e for `metrics.py` (`tactical_optimality`, `acting_quality`, `function_usage`, etc.).
- **Heuristic fallback**: `heuristic_player_turn()` mirrors paper's greedy policy but for GUMSHOE: drain 0-cost core clues first, spend 1-point benefits when pool≥3, otherwise general_test with spend = `max(0, 4 - median_die)` capped by pool, chase = lowest feasible spend, fights = combat-pool-aware.
- **Scene checks**: track `collected` coverage per case; flag if a core clue was gated behind a roll (violation) vs automatic.

### 8.8 Minimal CLI Wiring

```python
# dnd_tools/cli.py pattern — add gumshoe subcommand
# dnd-tools gumshoe-demo --seed 42 --turns 10 [--forgiving --timed] [--use-llm --model qwen3.6-35b-a3b-mtp]
# dnd-campaign gumshoe-demo --seed 42 --turns 15 --save run.json
# Both reuse existing arg parsing; llm = LLMClient alias → TauLLM(provider, model)
```

### 8.9 What *Not* to Port (v1 scope)

- Do not port exhaustive Ashen Stars / Fear Itself / Trail of Cthulhu setting content (balloon-tier tech, sanity cherries, expanded creature catalog) — keep the ~50 Investigative + ~25 General canonical core; flag setting extensions behind a data toggle.
- Defer soap-opera Stability refresh (support-network integrity) to a prompt-only check; default to automatic between-case refresh.
- Defer detailed hit-location called-shot tables and vehicle desirability tiers; map them to the ±1–4 Hit Threshold mod and typed Armor.
- Keep Timed Results as a delayed-core registry rather than a real-time lab simulation; resolution is a scene-triggered `collect_timed` tool.

---

## 9. Clue Resolution Flow (pseudocode, deterministic)

```python
# Investigative — always automatic if present
def gather_clue(character: GumshoeCharacter, scene: Scene, ability: str | None):
    if ability is None:
        # simple search path
        clue = scene.simple_search_clue(detail)
        if clue:
            mark_collected(clue); return {"automatic": True, "clue": clue.text, "cost": 0}
        return {"error": "no simple-search clue at this detail"}

    # inconspicuous path when moving through transitional area
    if scene.inconspicuous and ability in scene.inconspicuous.abilities:
        winner = max_characters_by_pool(ability)  # pools, then ratings, then ties
        if character.name != winner and not tied_with_winner:
            return {"error": f"inconspicuous: {winner} notices it instead"}

    # normal investigative gate
    matches = [c for c in scene.clues if ability in c.abilities and c.id not in collected]
    if not matches:
        return {"error": f"no clue here for {ability}; try another ability or a simple search"}

    core = next((c for c in matches if c.kind == "core" and c.cost == 0), None)
    if core:
        collected.add(core.id); return {"automatic": True, "clue": core.text, "cost": 0, "offers": benefit_offers(matches)}

    # only non-core or restricted remains
    benefit = next((c for c in matches if c.cost in (1, 2)), None)
    if benefit:
        return {"automatic": True, "clue": benefit.text, "cost": benefit.cost, "requires_spend": benefit.cost}
    return {"error": "clue type requires spend_investigative"}

def spend_investigative(character, ability, cost, benefit_id):
    if not (1 <= cost <= 2): return {"error": "benefit cost must be 1 or 2"}
    benefit = get_benefit(benefit_id)
    if benefit is None:      # no benefit to buy — cost is 0 per SRD
        return {"automatic": True, "cost": 0, "note": "no benefit available; pool unchanged"}
    if character.investigative[ability].pool < cost:
        return {"error": "insufficient pool"}
    character.investigative[ability].pool -= cost
    collected.add(benefit.id)
    return {"spent": cost, "clue": benefit.text, "pool": character.investigative[ability].pool}


# General — blind Difficulty, spend committed before seeing it
difficulty = 4  # GM sets blind via set_difficulty; 2..8 range

def general_test(character, ability, spend, difficulty_hidden=True):
    if character.general[ability].rating == 0 and not forgiving and spend != 0:
        # Unforgiving: rating 0 cannot test at all
        return {"error": "rating 0 cannot test (unforgiving mode)"}
    # lucky-shot gate
    if character.general[ability].rating == 0 and not forgiving:
        return {"error": "rating 0 cannot test; lucky shot requires unanimous permission"}
    if lucky_shot and not lucky_shot_granted:
        return {"error": "lucky shot: requires unanimous permission, once per episode for entire cast"}
    if character.general[ability].pool < spend:
        return {"error": "spend exceeds pool"}
    if is_retry and spend <= previous_spend:
        return {"error": "retry must spend more than previous attempt"}
    difficulty = get_hidden_difficulty(ability) if difficulty_hidden else get_revealed_difficulty(ability)
    die = roll_1d6()
    total = die + spend
    character.general[ability].pool -= spend  # spend is consumed regardless of outcome
    success = total >= difficulty
    return {"die": die, "spend": spend, "total": total, "difficulty": difficulty, "success": success}


def toll_test(character, ability, difficulty=6):
    if character.general[ability].pool < 0:
        return {"error": "pool check"}
    die = roll_1d6()  # rolled BEFORE spend is known
    needed = max(0, difficulty - die)
    # player then chooses to spend needed or to fail
    return {"die": die, "difficulty": difficulty, "needed": needed, "prompt": f"spend {needed} to succeed, or fail and keep pool"}
```

```
# Stability-tied Investigative spend (when Shaken, 0..-5)
if character.stability <= -1 and character.stability >= -5:
    test = general_test(character, ability="Stability", spend=strain, difficulty=abs(character.stability))
    # voluntary strain: lower Stability further to add +N, same pattern as consciousness
    # fail → spend still occurs but must roleplay impairment (tool records it)
```

---

## 10. References

- SRD HTML — **Rules**: `https://gumshoesrd.opengamingnetwork.com/rules/` — §§ Why This Game Exists, Mystery Structure, Gathering Clues (Core/Special Benefits/Inconspicuous/Simple Searches), Die Rolls, Tests (Simple/Piggybacking/Cooperation/Continuing Challenges), Zero Sum Contests, General Spends, Contests (Fighting/Health/Armor/Cover/Ammo/Range/Fighting Without Abilities/Called Shots/Combat Options/Running Away), Stability/Losing It/Mental Illness/Psychological Triage/Head Games, Regaining Pool Points, Improving Your Character, Opponent Statistics, Hazards, Designing Scenarios (Clue Types: Floating/Leveraged/Pipe/Restricted/Timed), Scene Types, Running Scenarios (Giving Out Clues/Elastic Participation/SCENE card). Fetched 2026-09-09 for this note.
- SRD HTML — **Your Character**: `https://gumshoesrd.opengamingnetwork.com/your-character/` — §§ Ratings and Pools, Concept/Stereotypes/Packages/Occupations, Assign Investigative (build-point table, free rating, benchmarks), Assign General (60 points, second-highest half-rule, 1 Health/Stability starter, 1–3/4–7/8 benchmark, cherries), Investigative Abilities (~50 with Academic/Interpersonal/Technical descriptions), General Abilities (~25 with cherries and checks), Drives.
- SRD HTML — **Legal**: `https://gumshoesrd.opengamingnetwork.com/legal/` — OGL v1.0a + CC BY dual licensing of SRD text (released via Hillfolk Kickstarter).
- Rules Summary — `https://pelgranepress.com/2017/09/29/gumshoe-rules-summary/` — Pelgrane-authorized prose summary: core vs Investigative pool spends, General tests 1d6 vs 2–8 with any spend adding to roll, Mystery Structure triad (trigger/conspiracy/trail), pools refresh between scenarios. Posted 2017-09-29 by Cat Tobin.
- Pelgrane SRD PDF — `https://pelgranepress.com/gumshoe/files/GUMSHOE%20SRD%20OGL%20version.pdf` — Evidence Collection / Explosive Devices / Leveraged & Pipe clue excerpts used to validate clue-type wording.
- Wikipedia — `https://en.wikipedia.org/wiki/Gumshoe_System` — publication history (2007 Robin Laws, Pelgrane Press) and dual-license note; Health/Stability to −12 death/insanity rule cross-check.
- System antecedents — `ref/31_Setting_the_DC_Synthesis.md` — the tool-grounded audit pattern this implementation extends.
- Cross-system implementation precedents in this repo: `ref/fate-core.md`, `ref/tricube-tales.md`, `ref/tricube-tactics.md`, `ref/blades-in-the-dark.md`, `ref/sword-and-sorcery.md` — architecture/prompt/harness patterns reused for GUMSHOE.

*End of condensed implementation reference.*
