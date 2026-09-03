# Tricube Tactics — Supplement Rules (Implementation Condensed)

> Tricube Tactics v2 © 2024–2026 Richard Woolcock · CC BY 3.0 — condensed from `tricube-tactics.txt`/`.pdf` for LLM + tool-grounded implementation.
> **Supplement, not standalone** — requires Tricube Tales core (`tricube-tales.md`). Adds tactical movement, granular traits/styles, 6 knack types, minions, and crunchy combat. Cherry-pick rules if you keep Tales combat (subtraits/reroll knacks alone are low-cost).

---

## 1. Core Changes vs Tales

| Area | Tales | Tactics |
|---|---|---|
| Difficulty | 4–6 (easy/standard/hard) | **3–7** (3 very easy, 7 very hard; rare, extreme). Karma still only way `3→2`. Beyond 6: need `6` on 2 dice = success, `6` on 3 = exceptional; 1 die cannot succeed. |
| Traits/styles | `agile/brawny/crafty` + `melee/ranged/mental` | Each splits into **3 subtraits/substyles** (see §2); challenges now call a **subtrait or substyle** directly. |
| Difficulty floor | Cannot go below 3 (karma → 2) | Same — edge/knacks never push below 3, karma is sole `3→2` path. |
| Combat | Narrative turn-by-turn | Round-based, 3 action tiers + movement modes + edge modifiers + stunts + minions + knacks |
| Advancement currency | perk/quirk or +1 karma/resolve (every 2nd) | + **knack** and **minion/subtrait/substyle training** options; max 6 of each subtrait/substyle/token |
| Tokens | karma / resolve / effort | + **minion** tokens (companions/familiars/mounts) |

Transition mid-campaign is viable: on adoption each PC gains a free knack *or* 1 minion token.

Alternative trait names in micro-settings (e.g. `athletic/buff/cunning`) → switch to default `agile/brawny/crafty` when using Tactics or design 3 new subtraits each.

---

## 2. Traits, Subtraits & Styles

> Tales archetype logic (3d6 if matching trait, 2d6 if not, −1 die if out-of-scope) still applies; now filtered through subtraits.

### Subtraits
**Agile** → `dexterity` (coordination, sleight, lockpick, crafting, agile stunts), `reflexes` (speed/reactions, initiative, self-powered vehicle steering), `stealth` (sneak/hide, camouflage, ambush planning, cleanup).
**Brawny** → `athletics` (run/swim/jump/climb/ride/pedal), `endurance` (toughness, poison/disease/hazard resistance, physical afflictions), `strength` (lift/break/bend, brawny stunts).
**Crafty** → `charisma` (persuasion/charm, crafty stunts), `intellect` (knowledge, mental affliction resistance), `perception` (search/notice/tracking).

**Auto-grant**: an `agile` thief starts with *all three* agile subtraits for free; similarly for trait/style.

### Substyles
**Melee** → `armed` (melee weapons), `parry` (vs melee, armed or unarmed), `unarmed` (fists/claws).
**Ranged** → `evade` (vs shooting/thrown), `shoot` (projectile), `throw` (thrown).
**Mental** → `direct` (psychic/magic/will), `indirect` (devices/troops/traps), `resist` (vs direct+indirect).

> Mental combat example: `geomancy` stone barrier = heavy cover; `illusionist` invisibility = `concealed` edge — still resolved via direct/indirect vs resist.

---

## 3. Characters — Creation & Advancement

### Creation (Tales + Tactics)
1. `trait` + `combat style` + `concept` + `perk` + `quirk` + `3 karma / 3 resolve` as in Tales.
2. **Plus**: one free **knack** *or* **1 minion token** (choose). Rangers often take minion as animal companion.
3. **Speed 3**, **Size 1** (human/bear/horse). Size table: `0 small` (cat), `1 medium`, `2 large` (rhino/orca), `3 huge` (elephant/T-rex), `4 gargantuan` (whale), `5 colossal` (kaiju/mech).
4. Alternative: start knack examples — `wings` → `movement(terrain)`, unarmed/heavy armor → `edge(negate: unarmed/armored)`, mage → `freeform`.

### Advancement
- **Per advance**: pick **perk *or* quirk *or* knack** (knack name must be novel and thematically fitted).
- **Every second advance**: may *instead* gain `+1 karma` *or* `+1 resolve` *or* `+1 minion` *or* **train one new subtrait or substyle**.
- Caps: **≤6 tokens** of each type; **≤6 subtraits** and **≤6 substyles** total (including free 3).
- XP variant: **100 XP = 1 advance** (1 XP = 1% advance); GM may call advances "levels".

---

## 4. Perks & Magic in Tactics Context

- Any perk effect not already covered by a knack (darkness, growth/shrink, ward door, illusion) → spend **1 karma** via `cast` + freeform knack pattern (§10 Freeform).
- If spell is just narrative flavour for something achievable without magic (light vs lantern, telekinesis vs hands), **0 karma**.
- **Offensive magic**: normally **mental attack** (direct) — but may describe conjured thrown weapon as `ranged/throw` if preferred. Stunts can be re-flavoured magically — `shove` as wind blast, `pin` as vines, `blind` as flash, `intimidate` as fear spell — subtrait stays `dexterity/strength/charisma` regardless.
- Buffs/summonings → **freeform knacks** (§10).

---

## 5. Action Economy

Each **round** a PC may take **one of each**: **standard + simple + swift** (downgrade allowed: `standard→simple→swift`; e.g. 2 simple + 1 swift or 3 swift). **Any number of free actions** on your turn. Some actions declare before moving; otherwise intermix with movement (move 1 → draw axe → move 1 → attack → move 1).

### Standard (require roll, on your turn)
| Action | Subtrait/substyle | Effect |
|---|---|---|
| **Attack** | armed/unarmed / shoot/throw / direct/indirect | 1 effort per die ≥ difficulty |
| **Escape** | `strength` (brute) or `dexterity` (wriggle) | Break pin/restrained; vs foe's `strength` or `dexterity` if pinned |
| **Retrieve** | `perception` (PCs roll; NPCs auto) | Pull from bag; diff easy if top, hard if buried |
| **Stunt** | `dexterity`/`strength`/`charisma` | Pick one effect per success (see §9) |

### Simple (on your turn, no roll unless noted; downgradable to swift when starred)
`aim`* (next ranged/mental + edge, but − to evade/resist; swift if you didn't move), `cast` (PC-only, freeform knacks), `dash` (before move; doubles speed; stackable: 3→6→12→24), `frenzy`* (next melee bonus but − to parry; swift if large weapon 2H; exclusive with guard), `guard`* (bonus to parry, − to melee; swift if small shield; exclusive with frenzy), `mount`/`dismount`, `prepare` (downgrade standard→simple; then one **swift strike** as swift at any time before next turn, even interrupting enemies; PC-only), `protect` (PC-only; defend nearby allies till next turn; swift variant may retroactively protect after ally fails), `quaff`, `ready`* (draw/conjure; swift for one small, free for throwing), `recover` (remove `stunned`), `reload`* (powerful weapons; swift if one small; 3 for black powder; free if not powerful), `retreat` (no swift strikes when disengaging this round; swift via knack may be used off-turn), `stand`* (from prone; swift if unarmored/unencumbered).

### Swift (interrupts, trigger-gated; even off-turn)
`charge` (double-dash + 3 straight strides → melee attack; ends move), `rush` (PC-only; slow→fast for one round; declare in fast phase), `sprint` (requires double-dash; doubles speed this turn), `swift strike` (see §6, §10 Strike knacks & weapons).

### Free (on your turn, no roll, still declare)
`drop`, `fall` (prone; may dismount riskily), `release` (release pin), `sheathe`, `talk` (few sentences / command). GM may add new standard/simple/swift/free actions (avoid bloating simple, it devalues knacks).

---

## 6. Movement

### Units & Speed
- **Stride** ≈ 2 yards/meters (scale shifts for kaiju/insect settings).
- Default **speed 3** strides/round; alligator 2, horse 4, etc. `dash×1→6`, `dash×2→12`, `sprint→24` (6-sec round). Movement knacks can raise (§10).
- **Encumbered** (excess loot/fallen ally) → speed −1. **Heavily armored** → speed −1 (−2 if both).

### Terrain
- **Difficult** (climb/crawl/swim, rough ground): **2× cost** (4× when sprinting); grid: only leaving square counts as crossing. **Movement(terrain) knack** ignores.
- **Hazardous** → one `athletics` check/turn at `4 easy` ( `5 standard` if dash, `6 hard` if sprint). Failure: choose **fall prone OR lose 1 resolve**; **critical failure: both**. NPCs: auto lose 1 effort *or* fall prone.

### Three Resolution Modes
1. **Battle maps** (default): figurines on gridded/hex or ruler. `1 stride = 1 square/hex or 1" (2.5 cm)`. Range = same as movement. **Figurine size**: size 1 → 1" (1 sq), size 2 → 2" (2×2), quadrupeds > human double length (horse 1×2). **LoS**: uninterrupted line from any point on attacker to any part of target. **No facing**. Two creatures cannot end in same square (exception: mount+rider, size 0 share). May pass through if occupant permits or prone.
2. **Abstract zones** (cards or drawn regions): free engage/disengage within zone; melee without engage only if reach > foe's. Move to adjacent zone = `dash`; each extra dash/sprint doubles zones (dash+dash+sprint = 4 zones). Ranged: within zone = range 3, adjacent = 6, +6 per extra zone.
3. **Range bands** (abstract, no map): `immediate` (≤3 strides; free engage/disengage), `near` (≤6; free→immediate else dash to engage), `far` (≤12; dash→near, double-dash→immediate, charge engages), `distant N` (×24 strides; sprint steps one closer; distant1→far=double-dash or sprint→near/immediate). Withdrawing mirrors approach; speed 2 needs 2 turns/distant step, speed 1 needs 3. Abstract distances: speed 1 = dash costs 2 simple max 1/turn; speed 2 = max 1 dash/turn; speed 4 = dash as swift; speed 5 = dash as free; speed 6 = dash free + second dash swift.

---

## 7. Initiative & Turn Order

- Each **round** = ~6 sec (or longer for naval/starship).
- At combat start each PC rolls `reflexes` at **standard** (easy if PCs surprise/ambush unseen; hard if surprised). **Success → fast** (before NPCs) every round; **failure → slow** (after NPCs). **Exceptional → also act in surprise round** (extra pre-combat round). **Critical failure → lose standard action in round 1** (may still move + simple/swift). Fast may **delay** → act slow this round; slow may **rush** (swift) → act fast this round. NPCs: some act in surprise round, some lose standard first turn if slow.
- **Phases per round**: **Fast (PCs) → Medium (all NPCs) → Slow (PCs)**. Same-phase PCs may resolve simultaneously (e.g. co-engage to gain `distracted`). Disputes → **opposed reflexes** (Tales rule: highest die wins). Minions only move on owner's turn.
- NPCs all act in medium; each targeted PC makes **one defense roll** at end of medium (see §11).

---

## 8. Attacking

- **Melee reach = size** (size 1 threatens adjacent/1"). **Engaged** = within each other's reach.
- **All attacks remove 1 effort per die ≥ difficulty** (Tales rule).
- **Reach vs range**: large ranged cannot shoot within target's melee reach; small ranged can but loses `short range` bonus. Mental = ranged. Stunts at narrative range.
- **Disengaging** = moving from engaged to non-threatening (even if foe still threatens) or any action that drops your threatening (sheathe large weapon, forced via stunt). Triggers **swift strike** (resolved *before* move) from each previously engaged foe. Moving without disengaging but ending non-engaged → cease engaged at end of turn, no swift strike.
- **Valid targets**: on exceptional, extra successes may hit additional foes who were **valid targets** (could have been hit had roll targeted them; highest die stays on primary). Single-shot ranged needs narrative justification. Moving can expand valid targets (hit, stride, hit).

### Edge Modifiers (±1 difficulty each; defence flips sign)
Bonuses lower difficulty; penalties raise. `frenzy/guard/armored` count **twice** if both attacker and defender qualify.

**Melee bonuses**: `distracted` (defender distracted or threatened by other beyond attacker), `frenzy` (either uses frenzy), `grappling` (defender pinner/pinned), `prone` (defender prone), `unarmed` (defender unarmed).
**Melee penalties**: `armored` (either heavily armored), `concealed` (attacker can't see), `guard` (either uses guard), `off-hand`, `unarmed` (attacker unarmed).

**Ranged/mental bonuses**: `aim`, `distracted`, `no cover` (target not shield/prone/cover), `short range` (within first range value and outside melee), `vulnerable` (target immobile/pinned/unaware or just used `aim`).
**Ranged/mental penalties**: `armored`, `concealed`, `heavy cover` (large shield/substantial cover), `long range` (beyond medium), `off-hand`.

**Cover**: `heavy` (≥⅔ obscured → penalty), `light` (≥⅓ → neutral), `<⅓ → no cover` (bonus). Large shield = heavy, small shield/prone = light, ballistic armor = light vs firearms, anyone engaged and not vulnerable = ≥light. **Concealment** (smoke/fog/darkness/camo) = `concealed` penalty.

---

## 9. Stunts (standard or swift strike; chosen trait sets stunt group)

Pick **one effect per success** (extras may spill to other valid targets).

**Agile** (`dexterity`): `disarm`, `blind`, `trip`, `stun`.
**Brawny** (`strength`): `pin`, `shove`, `trip`, `stun`.
**Crafty** (`charisma`): `taunt`, `intimidate`, `distract`, `stun`.

| Stunt | Effect |
|---|---|
| **Blind** | Victim suffers `concealed` vs attacks till end of its next turn |
| **Disarm** | Knock one held item → place within your `melee reach`; repeat pick for more items or 2× distance |
| **Distract** | `distracted` penalty till end of target's next turn |
| **Intimidate** | Target attempts to move away next turn (dash if possible; sprint if you applied 2×); overrides `taunt`. Scary monsters may do this at +1 difficulty (e.g. Ettin). |
| **Taunt** | Target attempts to attack you next turn (move/charge into melee; GM may allow ranged/sprint if unreachable); overrides `intimidate` |
| **Pin** | Grappled: neither may move unless agreeing to co-move, releaser frees, or victim escapes; shove moves both; size gap: larger moves normally, smaller auto-moved |
| **Shove** | Push 1 stride to unoccupied square (× uses = extra strides). vs size +1/+2 needs 2/3 picks per stride. Smaller victim: +1 stride per size diff (human→rat = 2 strides/shove). |
| **Stun** | `stunned` — must use `recover` before any further roll actions |
| **Trip** | Fall prone (mounted → auto dismount, see §12); `stand` next turn (swift if unarmored/unencumbered) |

---

## 10. Weapons

Assumed gear fits concept/perk; appearance is narrative. A glowing conjured blade = same as steel.

| Type | Ready / Hands | Range | Notes |
|---|---|---|---|
| **Small melee** | 1H | reach = size | — |
| **Large melee** | 2H | reach = size (2× with 2H) | `frenzy` as swift; doubled reach |
| **Thrown melee** | 1H | `3/6` (shoot/throw hybrid) | Uses `throw`; doubling: see throwing weapons below |
| **Small ranged** | 1H | `6/12` | `reload` free if not `powerful` |
| **Large ranged** | 2H | `12/24` | Cannot use in melee; `reload` simple (swift if one small) |
| **Natural** | — | `3/6` if throwable | No ready; suffers `unarmed` penalty |

**Shields & combos**: small shield → `guard` as swift, ignore `unarmed` + `no cover` penalties. Large shield → `heavy cover` + same ignores. Dual small melee (no guard this turn): exceptional standard attack → immediate swift strike with off-hand (one suffers `off-hand`). No benefit stacking for multi-limb aliens (narrative only).

### Ranged attributes (halves/double ranges, stack)
**Firearm** = range ×2 (small 12/24, large 24/48); ballistic armor = light cover vs it.
**Powerful** = range ×2 but **reload after every attack roll**; swift-strike reload timing: must reload before swift attack unless stunt (stunt needs no reload). If also multishot, one reload covers both.
**Multishot** = range ÷2 but exceptional standard attack → immediate swift strike with same weapon.
**Heavy** = large/2H only; **+1 damage** (total, not per die, on successful standard attack), ignores vs-armored penalty, but **cannot move + attack same turn**, and carrying = `encumbered` unless mounted.
**Collateral** (p142): if highest die ≤ `1 + #attributes`, GM may add collateral complication (structural/bystander) — bow 0 attrs → only on 1 (crit fail); arbalest `powerful+heavy` → ≤3; all four → ≤5. Success still hits.
**Range bands**: `≤first = short` (bonus), `≤second = medium` (neutral), `>second = long` (penalty); effective max ≥2×medium at GM discretion.

**Throwing** variants: `throwing` weapon → `6/12` and `ready` = free but becomes `improvised` in melee. `Incendiary` (grenade 6/12, Molotov 3/6 improvised) → exceptional → swift strike; collateral ≤5.

**Mental weapons**: as ranged (same edge/attributes except `heavy`), must `ready` (unless natural), declare small/large, stays readied; uses `direct`/`indirect`/`resist`. Pyromancer: one hand = small fireball, two = large.

**Weapon modes**: switch via `ready` (bastard sword 1H↔2H, assault rifle single↔burst, boomerang catch).

**Improvised**: falls outside most concepts → **lose one die** (not cumulative; fencer throwing maul one-hand horseback still −1 die; may opt to defend `unarmed` instead). NPCs: adjust difficulty +1 instead (they don't roll).

---

## 11. Minions

A third token type (see Tales). Figurines may double as tokens on map. No attack/defense rolls of their own; all through controller.

- **Direct damage via owner**: on attack, owner may divert any excess successes to foes within minion's reach/LoS (e.g. 3 successes, 2 needed at owner → 3rd kills beside minion).
- **Absorb hits**: on failed defense where minion is also threatened, owner may **sacrifice one minion** → lose −1 resolve less (overwhelming: failed = 2→1). Only one minion per defense roll. If **only minions threatened**, each damage point kills one minion; owner takes none.
- **Melee reach & swift strikes**: minions count for `distracted` and may trigger/provide swift strikes (disengaging from minion = owner makes defense; damage goes to minion). Owner may swift-strike *through* minion's location.
- **Movement**: move as far as owner, modified by owner's dash/sprint; `retreat` applies to all minions; difficult slows, hazardous ignored.
- **Ranged fighters**: declare per turn — no longer threaten in melee nor melee swift-strike, but may attack via own LoS.
- **Troop commander**: `ready` mental weapon + use `indirect` → attacks originate from minions, not owner. If owner eliminated but minions remain, continue commanding; damage to eliminated owner routes to minions. Minions can drag owner to map edge.
- **Critical failures**: shared — one minion auto-eliminated + owner takes remainder (1 normally, 2 if overwhelming). If only minions threatened, all damage to minions. Choose which minion.
- **Powerful minion**: assign multiple tokens to one entity (2 dogs → 1 warhorse with 2 tokens).
- **Recovery**: usually next session; GM may allow mid-session for **1 karma/minion**.

---

## 12. Other Combat Rules

**Mounted** → use mount's speed (typically 4). Falling prone = fell off mount → `athletics` `standard` or lose **1 resolve** (2 on crit); exceptional → land standing. Difficulty easy if you didn't move last turn, hard if you dashed. Concept check: most riders lose a die (knights/cowboys not). Dismount via `mount` or `fall` (free but risky).

**Off-hand**: attacking with off-hand → penalty (not for unarmed/stunts/defense).

**Weapons vs armor**: heavily armored → `armored` edge + speed −1; lightly armored → roll wound severity with advantage (see §13) + unencumbered stand; unarmored → swift `stand`.

---

## 13. Afflictions (Tactics elaboration)

On **0 resolve** → restore to full + gain one affliction → then **endurance** (physical) or **intellect** (mental) challenge:

| Afflictions incl. new | Permanent? | Difficulty |
|---|---|---|
| 1 | no | 4 easy |
| 2 | no | 5 standard |
| 3 | no | 6 hard |
| any | yes | 6 hard |

Result: **success → stunned** (need `recover` before further rolls); **exceptional → not even stunned**; **fail → out of fight** (unconscious/incap/flee); **critical fail vs permanent → fatal/instant death/retirement** (perks like `troll heritage` or `divine magic` may still cure, costing **permanent karma**).

**Retirement**: >3 afflictions *or* fatal permanent you cannot cure → new character starts with **one fewer advance** than prior.

**Natural recovery**: karma + suitable perk may cure (see Tales); otherwise time-based via severity + optional hit location (descriptive, skippable for mental).

- **Severity** `d6` (armored victims roll `2d6 keep lowest`): `1 Minutes`, `2 Hours`, `3 Days`, `4 Weeks`, `5 Months`, `6 Years`. Lightly/heavily armored advantage reduces severity.
- **Hit location** `2d6` (region A–F then precise): `A head` (forehead/eyes/nose/mouth/cheek), `B body` (neck/chest/abdomen/side/groin), `C left arm`, `D right arm`, `E left leg`, `F right leg`, second die A–F splits further (see txt p84 table). GM chooses or rolls for inspiration.

---

## 14. Defending

- **Single defense per medium phase** vs **most dangerous** (highest difficulty; tie-break by substyle).
- **Standard defense costs**: `exceptional→0`, `success→1?` Actually Tales `fail→1`, `crit→2`; **overwhelming** (3+ simultaneous attackers, including swift strikes grouped): `exceptional 0 / success 1 / fail 2 / crit 3`. Swift strikes resolved separately, but multiple disengagements = one defense (overwhelming applies). Protect retroactive etc.
- **vs Stunts** (same subtrait): `fail → 1 effect`, `crit → 2 effects`; vs overwhelming: `success 1 / fail 2 / crit 3`.
- **Protecting allies**: on exceptional defense while using `protect`, grant one ally within your reach **+1 step** (crit→fail→success→exceptional). Not vs swift strikes. If using `protect` but not targeted, may roll to protect anyway.

---

## 15. Knacks (6 types; ≤1 per type per roll except noted)

> Names are flavour: `longbowman (reroll: shoot)`, `quick draw (action: ready)`, `counterattack (strike: melee defense)` — record as `name (type: spec)`.

### Action Knacks
One simple→swift. `quick draw` (ready), `intuitive aim` (aim), `natural runner` (dash), `shield mastery` (guard) etc. **Once/round** per knack; no stacking same action. But if base rules already make it swift (small shield guard), then knack makes it **free**.

### Edge Knacks
`melee` or `ranged` or `negate`. **Max one melee *and* one ranged per roll**, but **any number of negate** per roll. `melee`/`ranged` → **double one bonus** (2 instead of 1; e.g. `berserker` doubles `frenzy` bonus, `point blank` doubles `short range`). `negate` → **eliminate one penalty entirely** (e.g. `sixth sense` negates `distracted` even if foe doubled it). Edge knacks only double edge modifiers (§8) and do not stack on frenzy/guard/armored applied by *opponent* (only own penalty). Example: `aggressive warrior` negates your `frenzy` penalty but not defender's frenzy penalty against you.

### Freeform Knacks
Tied to a magical perk; `cast` + **1 karma** → grant **one temporary knack *or* one temporary minion** for scene. Cannot grant target more temps than you have freeform knacks of that name; target *or* caster may pay. If perk can aid others, one `cast` can mass-grant same knack to multiple targets at **1 karma/target**. Duplicates with same name stack — double `necromancy` → 2 minions for 2 karma in one cast, so long as no other necromancy spells active. Later `free action` may dismiss. Temporary minion above `max minions`: vanishes end-of-scene if still over; otherwise may keep as regular.

### Movement Knacks
**Combat** — after any successful attack/stunt/defense: move `1 stride` (normal) or `up to 2` (exceptional) immediately; declare spec `trait/style` at take, one use/round/style, doesn't provoke disengage, but cannot dash more than once that round (e.g. `nimble (melee)`).

**Speed** — `+1 speed` for one locomotion form ( `fleet-footed` → 4 on foot). Multi-form knacks don't stack unless setting allows (speedsters/vampires).

**Terrain** — ignore difficult/hazardous, pass through occupied squares, enter reach without provoking nor becoming engaged until you attack or end turn there. Needs fitting concept/perk (mermaid `aquatic` OK, wood elf `alert` not).

### Reroll Knacks
Reroll **one die** after challenge for a **narrow** use of one subtrait/substyle (`professional swimmer: athletics (swim)`, `ace driver: reflexes (drive)`). Rules: cannot reroll `1`, must keep new result, **reroll never counts as critical failure**, multiple applicable knacks may reroll multiple dice but never a reroll; so max knacks used = dice rolled (2d6 → ≤2 knacks).

### Strike Knacks
Perform a **swift strike** (swift action) on trigger, one per trigger/round. Must pick trigger at take:

1. **Exceptional on attack/stunt as standard** — specify trait (`agile`) *or* style (`melee`). Other valid targets may be hit.
2. **Exceptional when defending vs attack/stunt** — specify trait/style; co-attackers are valid targets.
3. **Foe enters your melee reach** (from outside, without terrain knack) — melee attack or any justifiable stunt; all enterers that round are valid targets.

Max one swift strike per condition/round even if trait differs or bonus from weapon multishot.

**Examples** `p100`: `ace driver (reroll: reflexes)`, `ambidextrous (negate: off-hand)`, `armored tank (negate: armored)`, `berserker (melee edge: frenzy)`, `blind fighting (negate: concealed)`, `bodyguard (action: protect)`, `combat reflexes (action: recover)`, `counterattack (strike: melee defense)`, `first strike (strike: enter melee)`, `fleet-footed (speed)`, `marksman (ranged edge: aim)`, `martial artist (negate: unarmed)`, `nimble (combat: melee)`, `rapid shot (strike: ranged attack)`...

---

## 16. Enemies

### Rating → Effort & Difficulty (relative to setting, not PCs; swap ratios: 1 avg = 3 weak; 3 avg = 1 strong; 3 strong = 1 elite; so 3–6 average per PC is a hard fight)
| Rating | Effort | Difficulty |
|---|---|---|
| Weak | 1 | 4 |
| Average | 2 | 5 |
| Strong | 3 | 6 |
| Elite | 4 | 7 |

Modifiers: add effort to toughen; adjust difficulty ±1 for what foe is good/bad at (ogre brawny might be 6). Give per-trait/style diffs if desired (also optional `athletics/stealth/perception`; zombie `perception` may be high despite `stupid`).

### Speed / Size
**Speed** = movement speed (see §6). **Size** 0 small (shares square, no reach unless same square), 1 medium 1" (1 sq), 2 large 2" (2×2), 3 huge, 4 gargantuan, 5 colossal; quadrupeds > human double length. **Reach = size** (inches/squares).

### Abilities (knack-equivalents)
`action` (simple→swift), `edge` (as §15), `immune` (no damage from types), `movement` (`speed`/`terrain` as knacks; **combat**: enemy moves 1 stride on PC fail, 2 on crit fail — *inverse* of PC combat move), `strike` (offensive triggered by PC defense fail, defensive triggered by PC attack miss), `special` (bespoke simple; e.g. `fanatic: cannot be intimidated`). Keep specials short.

### Tactics (optional d6, inspiration)
Roll one die on foe's turn (`agents.py`-style harness may sample). Apply logically — if tactic impossible (melee while far, `pin` while pinned), **move (dash if needed) then use next entry**; don't ranged while engaged. Bestiary tactics examples:
- Battle Robot `A shove / B melee / C–D aim+shoot / E–F shoot`
- Cultist `A monologue / B dagger / C–D dark magic (mental) / E distract/stun / F intimidate`
- Death Lord `A intimidate / B–C necromantic blast / D–F sword`; **Bone shield**: redirect 1 damage/attack to adjacent skeleton; `lifesense` negates `concealed`
- Dragon (size 4, effort 9, speed 4, brawny 9): `A roar(intimidate) / B tail(shove/trip) / C fiery breath(ranged) / D–E claws(melee) / F bite(overwhelming)`; `flight` terrain speed 12
- More in `tactics.pdf` pp108–114. No detailed stat blocks beyond tables; GM uses common sense (slime through cracks, skeletons see via magic). **Underlings**: NPCs have no minions; boss redirect explicitly listed.

---

## 17. Example (Tactics)

```
GM: You ambush (easy reflexes). Elf DEB exceptional → surprise round + fast.
Elf (surprise): aim (simple) → shoot ogre DCC. Bonuses aim+short+no cover = 3 successes → 3/4 effort gone, arrow in back.
Elf (round 1 fast): aim+fire EDB → ogre dead, spare D wounds orc.
Dwarf: C A fail → slow.
GM: GM may roll tactics for orcs: attack? Dwarf may rush (swift) to act fast but saves swift.
Orcs: dash to engage → dwarves' defense vs standard parry.
Elf: bow = improvised in melee → unarmed penalty → hard, CB fail → −1 resolve.
Dwarf: CEE exceptional → block + counterattack (strike knack, swift) CBE kills hurt orc.
Slow phase: Dwarf frenzy + axe FBD kills last orc.
```

---

## 18. Implementation with `dnd-tools` + `dnd-campaign` via LLMs

> Same non-invasiveness as Tales: paper code in `packages/dnd-tools/src/dnd_tools/` stays frozen; Tactics is an additive mode; `dnd-campaign` handles horizon, persistence, context pruning. Use `tau-ai`/`tau_agent` (Python library, no subprocess) as in `agents.py:1`, `simulation.py:1`.

### 18.1 Architecture (reuse from Tales §7.1)

```
dnd-tools/  models.py / dice.py / state.py (HP/pos/LoS/tool_trace) / tools.py (30+ schemas)
            agents.py (make_tau_provider, AgentHarness, heuristic) / simulation.py (Simulation.run) / prompts.py / mapgen.py / cli.py
dnd-campaign/  state.py (CampaignState wrapping GameState, snapshot/restore, rests, prune)
               tools.py (CampaignTools delegating + long_rest/checkpoint/get_summary)
               memory.py (summarize_state, compact_transcript) / session.py (CampaignSession) / cli.py
```

Tactics adds `models_tactics.py` / `tools_tactics.py` / `state_tactics.py` / `prompts_tactics.py` alongside `*_tricube.py` from Tales — do not fork `GameState`.

### 18.2 New Models (additive)

```python
@dataclass
class TacticsCharacter(TricubeCharacter):  # extends Tales §7.2
    speed: int = 3
    size: int = 1
    subtraits: set[str] = field(default_factory=lambda: {"dexterity", "reflexes", "stealth"})  # per trait
    substyles: set[str] = field(default_factory=lambda: {"armed", "parry", "unarmed"})
    knacks: list[Knack] = field(default_factory=list)  # name, kind, spec
    minions: int = 0
    minion_max: int = 6  # cap
    heavy_armor: bool = False
    light_armor: bool = False


@dataclass
class Knack:
    name: str
    kind: str  # action / edge_melee / edge_ranged / edge_negate / freeform / combat / speed / terrain / reroll / strike
    spec: str  # "ready", "frenzy", "frenzy→negate", "necromancy", "melee", "reflexes"
    trigger: str | None = None  # for strike: "exceptional_attack:melee" / "exceptional_defense:crafty" / "enter_reach"


@dataclass
class EnemyProfile:
    rating: str  # weak/average/strong/elite
    effort: int  # 1/2/3/4 base
    difficulty: dict[str, int]  # per subtrait/substyle overrides; fallback 4/5/6/7
    speed: int
    size: int
    abilities: list[str]
    tactics: list[str]  # d6 table entries A–F


@dataclass
class WeaponState:
    name: str
    hands: int  # 1 small, 2 large
    range_short: int
    range_medium: int
    attrs: set[str]  # firearm/powerful/multishot/heavy/throwing/incendiary
```

### 18.3 Dice & Difficulty Helpers

```python
def roll_challenge_tactics(dice_count: int, difficulty: int, rerolls: list[Knack]) -> dict:
    # base Tales roll (1-3d6 vs 3-7)
    rolls = [_rng.randint(1, 6) for _ in range(dice_count)]
    # apply reroll knacks: one die per knack, never on 1, keep new, reroll≠crit
    for k, q in zip(rerolls, ...):  # narrow-scope check via tag
        ...
    successes = sum(1 for r in rolls if r >= difficulty)  # diff>6: need 6 on 2→success, 6 on 3→exceptional
    if difficulty > 6:
        successes = (1 if rolls.count(6) >= 2 else 0) if dice_count >= 2 else 0
        exceptional = rolls.count(6) == 3
    else:
        exceptional = successes >= 2
    return {
        "rolls": rolls,
        "successes": successes,
        "exceptional": exceptional,
        "critical_failure": all(v == 1 for v in rolls) and not rerolls,
        "effort_removed": successes,
    }
```

Edge calc: sum bonuses/penalties from §8 (count `armored/frenzy/guard` twice if both sides), apply knack doubles/negates (melee/ranged double one named bonus; negate removes one named penalty fully). Clamp difficulty floor 3 (only karma may make 2).

### 18.4 State Extensions

**`state_tactics.py : TacticsGameState(GameState)`** — keep `map/pos/tool_trace/transcript/round/initiative_order` for compatibility:
- Add `speed/size/subtraits/knacks/minions/affliction_log(effort_pools)` to snapshot; reuse `hp` as `resolve` proxy or add parallel fields but serialize both for Tales compatibility.
- **Terrain**: reuse `Cell.valid/z` plus `Cell.terrain ∈ {normal,difficult,hazardous,blocked}`; grid cost logic in `move_player`.
- **Wound severity & hit location**: roll `d6` (advantaged via `light/heavy armor` → 2d6 lowest) and `2d6` location at affliction time; store in `Affliction.severity/location` for narrative.

**`CampaignState` (already wrapping)**: extend `snapshot/restore` to carry knacks/minions/speed/size; `long_rest` still full resolve + clear non-permanent; `checkpoint/prune` unchanged (keep first ~10 + last 200 traces for LLM window).

### 18.5 Tool Schemas (LLM-visible; each logs to `state.log_tool` and returns JSON; mirrors `tools.py:779`)

| Tool | Purpose | Key params |
|---|---|---|
| `roll_challenge_tactics(chr, subtrait/substyle, difficulty, dice_count)` | 1–3d6 (+reroll knacks) vs 3–7; evaluate exceptional/crit per §18.3 | `character`, `subspec`, `difficulty`, `dice_count` |
| `apply_edge(chr, target, context)` | Compute net difficulty delta from §8 edge modifiers; return breakdown for narration | `chr`, `target`, `melee/ranged/mental + flags` |
| `use_reroll(chr, knack, die_index)` | Reroll one die (scope-checked; cannot reroll 1; keep new) | `character`, `knack`, `die_index` |
| `perform_stunt(attacker, target, stunt, successes)` | Apply stunt effects per success to valid targets (§9) | `attacker`, `target`, `stunt` |
| `weapon_action(chr, action)` | `aim/frenzy/guard/ready/reload` with swift/free downgrade logic (§5) | `character`, `action`, `weapon` |
| `move_tactics(chr, x,y, mode)` | Stride-cost movement; check difficult×2 (×4 sprint), hazardous check, minion follow, terrain knack bypass | `character`, `x`, `y`, `speed_remaining` |
| `disengage(chr, foe)` | Trigger swift-strike window before move (§8) | `mover`, `enemy` |
| `swift_strike(chr, target, trigger)` | Resolve swift action attack/stunt on trigger (enter-reach, exceptional, defense) with valid-target logic | `character`, `target`, `trigger` |
| `defense_roll(chr, difficulty, overwhelming)` | Single medium-phase roll vs most dangerous; 0/1/2/3 losses, stunt effects on fail | `character`, `difficulty`, `attackers_count` |
| `grant_knack(caster, target, freeform_knack)` | `cast` + 1 karma → temp knack/minion for scene (§15 freeform) | `caster`, `target`, `knack` |
| `sacrifice_minion(chr)` | Absorb 1 damage point from failed defense (§11) | `character` |
| `attack_tactics(attacker, defender, substyle, weapon)` | Bundles edge + range/cover + weapon attrs (firearm×2, powerful reload, multishot swift, heavy +1, collateral) | `attacker`, `defender`, `substyle` |
| `affliction_check(chr, type="endurance"/"intellect")` | Roll at easy/standard/hard by affliction count; map to stunned/out/fatal (§13) | `character` |
| `roll_severity(chr)` / `roll_hit_location(chr)` | d6 severity (advantaged if armored), 2d6 location | `character` |
| `set_enemy_profile(name, rating, difficulty, speed, size)` | Init NPC from Tales rank → Tactics rating; auto-effort | `name`, `rating` |

**Retained base tools** (no edit): `check_valid_attack_line`, `move`/`move_player`, `dash`/`sprint`/`charge`, `visualize_map`, `get_names_of_all_players/monsters`, `check_side`, `roll_initiative` (or `reflexes` challenge), `update_resolve` (aliased from `update_hp`), `add_buff/remove_a_buff` (for `stunned`), `check_resist` (if mixing 5e metrics), `apply_affliction/check_afflictions/recover_affliction` from Tales.

**Campaign tools** delegate unchanged: `long_rest/short_rest/checkpoint/save_checkpoint/load_checkpoint/get_summary/prune_traces` (`dnd_campaign/tools.py:52`).

All publish `tool_schemas()` OpenAI-compatible and `dispatch(name, args)` as `tools.py:1310`.

### 18.6 Agent Prompts & Harness (reuse `agents.py:51` verbatim)

```python
GM_PROMPT_TACTICS = """You are the GM (transactional). Use tools for all mechanics.
Challenges: assign subtrait/substyle + difficulty 3-7 + edge breakdown + effort;
gate declaration of quirks/aim/frenzy/guard before roll, resolve roll_challenge_tactics
(apply rerolls), apply edge/knack modifiers, remove effort per success, narrate relative
outcome + valid extra targets on exceptional, apply stunt/minion/affliction costs,
bookkeep, say <End Turn/>."""
PLAYER_PROMPT_TACTICS = """You are a Tricube Tactics player. Sense→plan→validate→act→communicate.
Downgrade actions legally; intermix move + actions; call edge/minion checks before rolling;
declare quirk/aim/frenzy/guard BEFORE roll, spend karma AFTER once/challenge;
use knacks only within narrow scope; coordinate via <Call/>Name, msg<Call/>; end with <DM/>."""
```

Wire:

```python
from dnd_tools.agents import make_tau_provider, _tools_to_agent_tools
from tau_agent.harness import AgentHarness, AgentHarnessConfig

tools = TacticsTools(campaign_state)  # wrapping TacticsGameState
provider = make_tau_provider("http://127.0.0.1:1234/v1", "lm-studio")
harness = AgentHarness(
    AgentHarnessConfig(
        provider=provider,
        model="qwen3.6-35b-a3b-mtp",
        system=GM_PROMPT_TACTICS,
        tools=_tools_to_agent_tools(tools),
        max_turns=8,
    )
)
```

**Simulation loop** keep `simulation.py:214` shape: `roll_initiative/reflexes` → per-turn `check_side` → `move_tactics` (abstract zones/range bands as virtual coords if not gridded) → `apply_edge` → `roll_challenge_tactics` → optional `use_reroll`/`spend_karma` → `attack_tactics/perform_stunt` → `defense_roll` in medium phase (one/PC, overwhelming scaled) → `sacrifice_minion` fork → `affliction_check` at 0 → `reset_resources/reset_speed` + buff/minion temp expiry → `<End Turn/>`. `CampaignSession` orchestrates multi-encounter + `checkpoint`/`prune_traces` via `memory.py:10` `summarize_state`/`compact_transcript`.

### 18.7 Determinism & Eval

- Seeded `_rng` only; every `1d6/d6 hit/severity/tactics-d6` via `dice.seed(seed_val)` restored in `snapshot/restore`.
- Authoritative state: narration never overrides tool `success/crit/effort_resolve` fields; harness catches tool `error` dicts.
- Traces bounded same shape as `state.py:193` for `metrics.py` if keeping 5e metrics; add Tactics-specific metric: edge/knack legality, valid-target overflow, collateral correctness.

### 18.8 CLI

```python
# dnd-tools  dnd-tools tactics-demo --seed 42 --turns 12 --map outdoor --abstract zones
# dnd-campaign  dnd-campaign tactics-demo --seed 42 --turns 15 --save run.json
# add --mode tales|tactics flag to share code; default Tales for paper fidelity.
```

### 18.9 What *Not* to Port First

- Skip firearm `powerful/multishot/heavy` reload state machine and `incendiary` area splash until core loop green — gate behind feature flag.
- Postpone hit-location narrative table beyond descriptive string; severity→recovery time mapping is enough for LLM.

---

## 19. Pseudocode — Attack → Defense → Affliction

```python
# declare simple actions BEFORE move/attack
if player_wants("aim" | "frenzy" | "guard" | "dash"):
    weapon_action(chr, action)  # tracks swift vs simple
# move
remaining = chr.speed + (3 if used("dash") else 0)
for step in path:
    cost = 2 if terrain == "difficult" else 1  # ×2 sprint if sprinting
    if cost > remaining and wants("dash"):
        weapon_action(chr, "dash")
    move_tactics(chr, nx, ny)
# declare quirk BEFORE roll
if player_declares_quirk:
    difficulty += 1
# roll + edge + reroll + karma gates
rolls = roll_challenge_tactics(dice_count, difficulty + apply_edge(...), rerolls)
if rolls.successes == 0 and chr.karma > 0 and player_spends:
    difficulty -= 1
    rolls = reevaluate(rolls.rolls, difficulty)
    chr.karma -= 1
if rolls.exceptional:
    extra_successes_may_hit(valid_targets)
effort_pool[foe] -= rolls.successes
if rolls.critical_failure:
    victim = choose_pin_or_shove_stunt_if_applicable()
# medium phase defense (one per PC)
successes_needed = 1  # 0 vs overwhelming handled in tool
r = defense_roll(defender, difficulty=max_attack_difficulty, overwhelming=len(attackers) >= 3)
resolve_cost = (
    {"exceptional": 0, "success": 1, "fail": 2, "crit": 3}[r.outcome]
    if overwhelming
    else {"exceptional": 0, "success": 0, "fail": 1, "crit": 2}[r.outcome]
)
if r.outcome in ("fail", "crit") and minion_threatened:
    sacrifice_minion(defender)
    resolve_cost -= 1  # only once
defender.resolve -= resolve_cost
if defender.resolve == 0:
    apply_affliction(defender)
    defender.resolve = defender.resolve_max
    check = affliction_check(defender, "endurance" if physical else "intellect")
    # success→stunned, exceptional→fine, fail→out, crit+permanent→fatal
```

---

## 20. References

- Full text: `ref/tricube-tactics.txt` / `tricube-tactics.pdf` (supplement, DriveThruRPG).
- Core rules: `ref/tricube-tales.txt` / `tricube-tales.md` — Tales condensed.
- Paper frame: `ref/31_Setting_the_DC_Synthesis.md`.

*End of Tactics condensed implementation reference.*
