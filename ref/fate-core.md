# Fate Core / Condensed — Core System Rules (Implementation Condensed)

> Fate Core System © 2013 Evil Hat Productions, LLC — by Leonard Balsera, Brian Engard, Jeremy Keller, Ryan Macklin, Mike Olson, Clark Valentine, Amanda Valentine, Fred Hicks & Rob Donoghue — SRD under CC BY 3.0 (https://fate-srd.com/fate-core, https://www.faterpg.com). Fate Condensed © 2020 PK Sullivan, Lara Turner, Fred Hicks et al. — also CC BY 3.0 and 100% compatible. Condensed below for LLM + tool-grounded implementation. Fate™ is a trademark of Evil Hat Productions.
> Reference sources consulted 2026-09-09: SRD pages for Basics / Ladder / Four Actions & Outcomes, Aspects & Fate Points, Fate Point Economy, Invoking & Compelling, Skills & Stunts, Stress/Consequences & Recovery, Challenges/Contests/Conflicts & Zones, Fate Condensed refinement notes. All mechanics cited to `fate-srd.com` path or Fate Condensed text.

---

## 1. System Overview

### Design Pillars

Fate is a fiction-first, proactive-competent-dramatic engine. You play capable people who drive the story — the GM never says "you can't" without a mechanical reason. There is **no default setting**; same ladder/dice/aspect core powers pulp, space, horror via setting dials.

Key contrast to D&D/Blades/Tricube:

- **Only players need depth**: GM NPCs are lightweight (aspects + 1 peak skill + stress + stunts).
- **Aspects are always true**: `On Fire`, `Without Line of Sight`, `Angry Mob` are narrative facts before they are mechanics. Invocation/compel gates bonus vs. fate point flow.
- **Four actions solve everything**: every `4dF + skill` roll is declared as `overcome | create advantage | attack | defend` — the outcome table is action-specific.
- **Fiction ↔ mechanics is audited via tools**: the LLM cannot handwave "you succeed" — the dice + shifts + aspect economy decides `fail / tie / succeed / succeed with style` and stress/consequence cost.

### Why Aspects + Fate Points ("The AI Fix")

Before any bonus die applies the GM+player must agree:

> "This aspect `___` is **relevant** because `___` in this situation. I **spend 1 fate point** (or use a free invoke from `create advantage`) for `+2 / reroll / +2 to ally / +2 obstacle`."

And in the other direction:

> "You have aspect `___` in `___` situation, so it makes sense you'd **decide to ___**. This goes wrong when `___` happens — **accept 1 fate point** or **pay 1 to refuse**."

- Single `4dF` (bell curve, median 0, range −4…+4) enforces swingy but bounded variance — skill + aspects decide, not luck alone.
- Free invokes **stack** with paid invokes and with each other (Condensed clarification) — so LLMs can't forget a `create advantage` they just earned.
- Compels are **negotiated**: if the table agrees the trait doesn't fit, drop it — but if accepted the fate point *must* flow (`player→GM infinite pool→player` for GM compels; `compeller→infinite→target` for PvP compels). No silent softening.
- GM fate pool is **capped** (`1 per PC per scene`, +1 per conceded/failed NPC compel carried to next scene) — the prompt enforces scarcity, so the LLM must budget NPC invokes.

### Core Loop

```
Scene framing (aspects/zones) → Player declares Action (4 types) → GM sets opposition (passive = ladder value, active = skill roll) → Roll 4dF
  → Shifts → Outcome per Action Table → Shifts→ stress/consequence/boost → fate point flow (invoke/compel/concede) → narration → next exchange
```

Longer structures stack exchanges: **Challenge** (one overcome per obstacle, cost on fail/tie), **Contest** (first to 3 victories, roll per exchange, tie=no victor, twist), **Conflict** (zones + stress + taken out / concession per exchange until one side concedes/falls).

This repo implements the **scene/conflict** loop plus lightweight challenge/contest wrappers. Full campaign milestones/extras/campaign dials are referenced but not fully simulated in v1.

---

## 2. Characters

### 2.1 Aspects (5 canonical)

Every PC has **5 permanent aspects** (Fate Core §Character Creation; Condensed §Aspects):

| Slot | Purpose | Example |
|---|---|---|
| **High Concept** | Who you are + what you do | `Disgraced Starship Captain` |
| **Trouble** | Flaw the GM will compel; primary fate income | `Debt to the Syndicate` |
| **Relationship / Phase 1** | How you crossed the next PC's story | `Owe My Life to Layla` |
| **Adventure 1 / Phase 2** | Guest-star in another PC's story | `Failed Heist on Red Station` |
| **Adventure 2 / Phase 3** | Second guest-star | `Saved the Village from Ashen Wyrm` |

Additional aspect slots: **game aspects** (permanent, set at table creation), **situation aspects** (scene-only, from `create advantage` or GM framing), **boosts** (one-use, `succeed with style` on defence or tie on attack, **vanish** after first free invoke), **consequences** (sticky aspects with free invoke for attacker).

> Best aspects are double-edged, say >1 thing, stay concise — e.g. `Wizard for Hire, Wanted by the White Council`.

### 2.2 Skills & The Ladder

**Default skill list (18)** — Fate Core §Skills: `Athletics`, `Burglary`, `Contacts`, `Crafts`, `Deceive`, `Drive`, `Empathy`, `Fight`, `Investigate`, `Lore`, `Notice`, `Physique`, `Provoke`, `Rapport`, `Resources`, `Shoot`, `Stealth`, `Will`. Toolkit swaps allowed; `Fate Accelerated` collapses to 6 approaches (`Careful, Clever, Flashy, Forceful, Quick, Sneaky` — keep mapping layer if using FAE).

**Ladder** (Fate Core §The Ladder; Fate Condensed §Adjectives):

```
+8 Legendary   +4 Great    0 Mediocre   -2 Terrible
+7 Epic        +3 Good    -1 Poor
+6 Fantastic   +2 Fair
+5 Superb      +1 Average
```

Numeric values are authoritative for the tool — adjectives are labels. Ladder sets both **skill rating** and **passive opposition** (`Mediocre 0` = everyday, `Fair +2` = professional, `Great +4` = exceptional, `Superb +5` = mastery).

**Skill pyramid** (default chargen; column variant = `20 skill points`, max `+4 Great`):

```
1 × Great   (+4)
2 × Good    (+3)
3 × Fair    (+2)
4 × Average (+1)
```

Columns variant (`fate-srd.com/fate-core/character-creation` sidebar): distribute 20 points, cap at `+5 Superb` only with GM permission; skill column reserved for advancement.

### 2.3 Stunts & Refresh

- **Refresh** = fate points at session/scenario start. Default **3**. At end of mid-scenario session: if below refresh → reset to refresh; if above → keep extra. At **scenario end → reset to refresh regardless**.
- **Stunts** — break-the-rules special moves (permission, +2 in narrow niche, swap skill, add action). **First 3 stunts free** when `Refresh = 3`. Each extra stunt **−1 Refresh** (so `5 stunts → Refresh 1`). Pay `1 fate point` to activate potent stunts that say so. Keep stunt text auditable (`invoke +2 to Shoot when aiming`, `use Burglary to detect traps`, etc.).

### 2.4 Stress, Consequences & Recovery

**Stress** — hit-point pools, not HP:

| Track | Boxes | Grants extra box when |
|---|---|---|
| **Physical** | `1` (1-shift), `2` (2-shift) | `Physique +1 Average → 3-box`, `+3 Good → 4-box` (Fate Core §Physique extras) |
| **Mental** | `1`, `2` | `Will +1 Average → 3-box`, `+3 Good → 4-box` |

On a **hit** of `N` shifts (attack shifts minus defense), defender must **absorb N** by checking **one** box + optionally stacking consequences. Each box/consequence absorbs exact value; **single box per hit** max. Unused shifts after max absorption ⇒ **Taken Out** (victor decides fate). Stress **clears at end of scene** automatically.

**Consequences** — sticky aspects with free invoke for whoever caused them:

| Severity | Value | Recovery (Fate Core §Recovery) |
|---|---|---|
| **Mild** (`2`) | absorbs 2 | Clear after **one scene** (or end of scenario if scene was the finale) |
| **Moderate** (`4`) | absorbs 4 | Clear after **next session** |
| **Severe** (`6`) | absorbs 6 | Clear after **scenario** (major milestone) |
| **Extreme** (`8`, optional) | absorbs 8 + rewrite one of your aspects (permanent) | Clear after **major milestone** |

You have **one of each** (Mild, Moderate, Severe); extras granted by Physique/Will at high ranks map to same table. Consequences linger as aspects (can be invoked against you, compelled for fate points) until recovery roll succeeds.

**Concession**: before taken out, defender may **concede** — exit conflict, receive `1 fate point + 1 per consequence taken this conflict` (from GM infinite pool), but victor narrates a cost short of death.

---

## 3. Core Rolls

### 3.1 The Dice

`4dF` — four Fate dice each `[-1, 0, +1]` (often rendered as `− / blank / +`). Sum ∈ `[-4, +4]` (approx. `~19% at 0, ~23% at ±1, ~15% at ±2, ~6% at ±3, ~1.2% at ±4`). Roll is `4dF + skill rating`.

```
result = sum(4dF) + skill
shifts = result - opposition
opp    = passive ladder value OR active defense roll (also 4dF+skill)
```

**Seeded RNG**: all `4dF` go through `dice._rng` seeded from `GameState.seed`; re-seed on restore.

### 3.2 Four Actions — Outcome Tables (Fate Core §Four Actions, §Actions & Outcomes)

Declare one of four **before** rolling:

| Action | Goal | Oppo. | Fail (`result < opp`) | Tie (`=`) | Succeed (`+1..+2 shifts`) | Succeed with Style (`≥3 shifts`) |
|---|---|---|---|---|---|---|
| **Overcome** | Pass a static obstacle | Passive or active (defend) | Fail, or succeed at **major cost** (GM picks: minor twist / stress) | **Success at minor cost** (lesser goal, or cost) | Succeed at no cost | Succeed **+ boost** (one-use aspect) |
| **Create Advantage** | New aspect or leverage existing | Passive or active | Fail = no aspect (or unopposed aspect at cost) | Gain aspect **but** opponent gets free invoke **or** you keep it without free invoke | Place aspect + **1 free invoke** | Place aspect + **2 free invokes** |
| **Attack** | Inflict harm | Active defend | No harm (defender may get boost on style) | No harm, gain **boost** | Hit = **shifts** stress/consequence to absorb | Hit + **option: −1 shift for a boost** |
| **Defend** | Avoid attack/advantage | — | Attacker succeeds per its table | Tie = attacker gets boost / minor effect | Attack fails | Attack fails + you gain **boost** |

**Notes codified from SRD verbatim tables**:

- `Create advantage` targeting a character → defender rolls **defend**.
- `Attack` shifts = `attack result − defense result`, never double-dipped with skill damage — damage is shifts.
- Free invokes from `create advantage` **stack** with paid invokes and with earlier free invokes on same aspect (Fate Condensed clarification; Core FAQ errata).
- If you aren't seeking a free invoke and the table agrees an aspect *should* exist, just **write it** — no roll needed (Fate Core §Advantages: "just suggest them").

### 3.3 Challenges, Contests, Conflicts

**Challenge** (Fate Core §Challenges, p147): sequence of distinct `overcome` rolls, one per obstacle/goal. Interpret failure/cost/success together — some obstacles may require advantage-created aspects before overcome is plausible. Each failed overcome inflicts cost (stress, complication aspect, clock-like progress).

**Contest** (Fate Core §Contests, p150): head-to-head race, `first to 3 victories`. Per exchange: all participants roll appropriate skill. **Highest wins 1 victory**; `succeed with style (≥3 over next)` and **no one else styled → 2 victories**. **Tie for highest → no victory, unexpected twist**. Advantage creation is legal but consumes your victory attempt that exchange.

**Conflict** (Fate Core §Conflicts, p154; Condensed §Conflicts): zone-based tactical combat.

- **Set the scene**: describe environment, **create situation aspects + zones**, place combatants.
- **Determine turn order**: `Notice` or `Investigate` etc. for initiative (or `Empathy/Provoke` for social) — higher = earlier, or popcorn per table; GM tracks `initiative_order`.
- **Per exchange**: each side takes **one action** on their turn; others **defend/respond** as needed. At end of exchange, restart. Conflict ends when **one side concedes or is taken out**.
- **Other actions in a conflict**: modified challenge — must **defend successfully** before non-attack action counts; otherwise action lost.

### 3.4 Zones & Movement

Zones are abstract areas (rooms, rooftops, courtyard). Moving **within** zone or to **adjacent** zone = free with action. Extra movement / obstacles may require `Athletics overcome`. Situation aspects (`Barricade`, `On Fire`) can be **invoked for passive opposition +2** if tagged as barrier. Fate leaves distances narrative; tool stores `zone graph` + `pos[character]=zone_id`.

---

## 4. Aspects in Play — Invoke, Compel, Declare, Hostile

### 4.1 Invoke (spend to help)

Explain relevance + **spend 1 fate point** → choose one (Fate Core §Invoking, Cheat Sheet p68):

1. `+2` to your `4dF + skill` result **after** rolling (or before);
2. **Reroll** all four dice (keep new, pay new modifiers);
3. **Teamwork**: `+2` to **ally's** roll vs relevant passive/active opposition;
4. **Obstacle**: `+2` to **passive opposition** against an opponent (make their overcome harder).

Free invokes from `create advantage` do the same without cost. Mark used (`boost` → consumed on first use, remove aspect; situation aspect free invokes → decrement counter).

### 4.2 Hostile Invoke

Invoking an aspect **attached to your opponent** (character or consequence) → the spent fate point **goes to them at end of scene** (not GM pool). In PvP, if you invoke another PC's aspect, **they** get it end-of-scene (Fate Core §Earning Fate Points: "Have Your Aspects Invoked Against You").

### 4.3 Compel (earn by leaning into trouble)

Two flavors (Fate Core §Compelling Aspects, Cheat Sheet):

- **Event-based**: "You have `___` aspect in `___` situation, so it makes sense that, unfortunately, `___` would happen to you. Damn your luck." (GM narrates complication).
- **Decision-based**: "You have `___` in `___`, so it makes sense you'd **decide to ___**. This goes wrong when `___` happens." (Player declares; GM frames fallout.)

Anyone may **propose** a compel. Flow (`fate-srd.com/fate-core/invoking-compelling-aspects`, `fate-point-economy`):

1. Proposer narrates.
2. **GM has final say** whether valid.
3. If accepted → **target gains 1 fate point** (from GM infinite pool — not from NPC limited pool).
4. If **refused** → target **pays 1 fate point** to the infinite pool (GM's NPC pool unaffected). If target cannot pay, they must accept.
5. **Player-vs-player compel proposal**: proposer pays 1 to infinite, then on accept the target gets 1 from infinite (so proposer can't spam to drain — net neutral). On reject, target's payment also goes to infinite.

GM may offer karma-like compel complications tied to quirks without charging — tool logs either way.

### 4.4 Declare a Story Detail

Spend **1 fate point** to add an important/unlikely detail anchored in one of **your aspects** (not rewriting an existing aspect, but adding one where none exists). E.g. `I've Read About This → declare the library has a secret exit`. Tool validates: must cite aspect + narrative justification.

---

## 5. Running the Game

### 5.1 Opposition Setting

| Oppositon | Ladder Value | Example |
|---|---|---|
| Passive | `0 Mediocre` to `+8 Legendary` | Pick lock (`Average +1`), decipher ancient text (`Great +4`) |
| Active | `4dF + skill` | Guard's `Notice +2` vs your `Stealth +3` |
| Advantage barrier | `+2` per invoked aspect on obstacle | `Locked Door + Reinforced` invoked → +2 |

### 5.2 Teamwork & Assists

`Invoke` teamwork (`+2`) is the formal assist. Free-form `help` without aspect still gates via `create advantage` (create `Covering Fire` with 1 free invoke, hand it to ally next turn). Stack multiple teamwork invokes if fiction allows.

### 5.3 Advancement / Milestones (summary, v1 non-enforced)

- **Minor milestone** (end of session): swap two skills, rename an aspect, pick new stunt, rename extra.
- **Significant milestone** (end of scenario): as above + gain `1 skill point` (new Average or raise one), clear `Severe` consequence.
- **Major milestone** (end of arc): as above + `+1 refresh`, add `Extreme` recovery/power.

Tools expose `advance` but do not auto-enforce pyramid integrity in v1.

---

## 6. Example Play (Fate Core flow, condensed paraphrase)

```
GM: The vault door is Reinforced Steel (Great +4 obstacle). Cynere wants to open it. Zird is pouring over blueprints nearby.

Cynere (Burglary Good +3): "I Create Advantage — I study the blueprints with Zird to find a weak point, calling on my aspect Keen Eye for Weakness."
GM: Roll Investigate vs Mediocre +0 (no active defender). 
Cynere: *4dF [+, blank, +, -] = +1 → total 1+3=4? Actually Investigate +2 → 3 → Succeed → place aspect Exposed Hinge (1 free invoke).

Zird: "I overcome the lock itself — Burglary +3, +2 from Exposed Hinge free invoke."
GM: Opposition Great +4. 
Zird rolls 4dF [-, -, blank, +] = -1 → 2 before invoke → +2 → 4 → Tie vs Great → Success at minor cost.
GM: The door shudders open but the Alarm aspect appears with 1 free invoke for the guards — you have a complication clock now.
Zird: "Worth it."

Later — Conflict:
Guard (Shoot Fair +2) attacks Cynere (Athletics Good +3). Guard rolls 4dF 0+2=2; Cynere defends 4dF +1 +3=4 → Fail for attacker → no stress.
Cynere invokes On Fire (spend 1 FP) for +2 on Fight attack vs guard's Physique. Rolls 4dF 0+3+2=5 vs guard defend 1+1=2 → 3 shifts → Hit 3 → guard must absorb 3 (checks 2-box, remaining 1 must be consequence Mild "Sprained Wrist" or be Taken Out).
Guard concedes: gains 1 FP (+1 for Mild already taken this conflict =2 total from GM infinite), exits scene with cost.
```

---

## 7. Implementation with `dnd-tools` + `dnd-campaign` via LLMs

Goal: keep `packages/dnd-tools` **frozen**; build Fate as additive implementation mirroring `tricube`/`blades`/`sword-and-sorcery`.

### 7.1 Architecture

```
packages/fate-core/src/fate_core/
  models.py     FateCharacter (aspects 5, skills dict, stunts, stress[physical/mental], consequences, refresh/fate_points, zones), Aspect, Consequence, Zone, Contest
  dice.py       seeded RNG, roll_fate(skill) → 4dF distribution + ladder lookup
  state.py      FateState (characters, zones, aspects registry, fate pools, stress/consequence, initiative, clocks) + FateCampaignState (checkpoint/save/prune)
  tools.py      FateTools — 20+ typed tools (roll_fate, invoke_aspect, compel_aspect, create_advantage, overcome, attack, defend, concede, declare_story_detail, etc.)
  prompts.py    GM_PROMPT / PLAYER_PROMPT — rigid recipe: declare action → set opposition → roll 4dF → compute shifts → apply outcome table → fate point flow → stress/consequence
  agents.py     Tau harness wrappers + heuristic (greedy closest advantage then overcome)
  simulation.py Single scene/conflict simulation (framing → challenge/contest/conflict loop → recovery)
  session.py    Multi-scene campaign (milestones/refresh/between-scenes)
  memory.py     summarize_state, compact_transcript
  cli.py        fate demo / campaign
```

### 7.2 New Models (additive, isolated)

```python
from dataclasses import dataclass, field


@dataclass
class Aspect:
    name: str
    kind: str  # high_concept|trouble|relationship|adventure|game|situation|boost|consequence
    free_invokes: int = 0
    owner: str | None = None  # character or "scene:zone"
    expires: str = "scene"  # scene|session|scenario|permanent|one_use


@dataclass
class Consequence:
    name: str
    severity: str  # mild|moderate|severe|extreme
    value: int  # 2|4|6|8
    recovery: str  # scene|session|scenario|milestone
    free_invoke: bool = True  # attacker gets one free


@dataclass
class FateCharacter:
    name: str
    aspects: list[Aspect] = field(default_factory=list)  # exactly 5 permanent + dynamic
    skills: dict[str, int] = field(default_factory=dict)  # 18 keys -2..+8, pyramid validated
    stunts: list[dict] = field(default_factory=list)  # {name, skill, bonus, trigger}
    refresh: int = 3
    fate_points: int = 3
    stress_physical: dict[int, bool] = field(default_factory=lambda: {1: False, 2: False, 3: False, 4: False})
    stress_mental: dict[int, bool] = field(default_factory=lambda: {1: False, 2: False, 3: False, 4: False})
    consequences: list[Consequence] = field(default_factory=list)  # max 3 (4 with Physique/Will)
    zone: str | None = None
    taken_out: bool = False
    conceded: bool = False


@dataclass
class FateNPC:
    name: str
    aspects: list[Aspect] = field(default_factory=list)
    peak_skill: int = 2  # +1..+5 ladder
    stress: dict[int, bool] = field(default_factory=lambda: {1: False, 2: False})
    consequences: list[Consequence] = field(default_factory=list)
    fate_pool_share: int = 0  # slice of GM scene pool


@dataclass
class Zone:
    name: str
    aspects: list[Aspect] = field(default_factory=list)
    connections: list[str] = field(default_factory=list)
    occupants: list[str] = field(default_factory=list)
```

`fate_points` per PC reset to `refresh` at session/scenario per §4 economy; `GM pool = 1 per PC in scene` + carried compels/concedes (see `FateState.gm_fate`).

### 7.3 Dice Extension (`dice.py`)

Add helpers seeded by `FateState.seed`:

```python
def roll_fate(skill: int) -> dict:
    dice = [_rng.choice([-1, 0, 1]) for _ in range(4)]  # 4dF
    total = sum(dice) + skill
    return {
        "dice": dice,          # e.g. [1,0,-1,1]
        "sum": sum(dice),      # -4..+4
        "skill": skill,
        "total": total,
        "ladder": ladder_name(total),  # Legendary..Terrible
        "shifts": None,        # filled after vs opposition
    }


def ladder_name(n: int) -> str:
    table = {8:"Legendary",7:"Epic",6:"Fantastic",5:"Superb",4:"Great",
             3:"Good",2:"Fair",1:"Average",0:"Mediocre",-1:"Poor",-2:"Terrible"}
    if n > 8: return f"Legendary+{n-8}"
    if n < -2: return f"Terrible{n+2}"
    return table[n]


def evaluate(outcome_shifts: int, action: str) -> dict:
    # maps shifts → {fail, tie, succeed, succeed_with_style} per Four Actions table §3.2
    ...
```

Keep `dnd_tools.dice` untouched.

### 7.4 GameState / CampaignState Additions

- Replace HP-centric `update_hp` with `mark_stress(character, track, box)`, `add_consequence(character, severity, name)`, `clear_stress(character)` (end-of-scene), `recover_consequence(character, name)` on milestone.
- Add `aspects: dict[str, Aspect]`, `zones: dict[str, Zone]`, `gm_fate: int`, `contest_state: {victories: dict, needed:3}`.
- `FateCampaignState.snapshot/restore` mirrors `dnd_campaign` pattern; re-seeds dice on restore; serializes stress/consequence/aspects/pools.
- Between scenes: `clear_stress_all()`, check `mild` recovery; between sessions: `refresh_fate()` and `moderate` recovery; between scenarios: `severe` recovery + reset to refresh.

### 7.5 Tool Schemas (LLM-visible)

| Tool | Purpose | Key params |
|---|---|---|
| `set_opposition(character, action, skill, opposition, passive_value)` | Gate: must precede `roll_fate`; declares which of 4 actions and passive ladder vs active. | `action overcome/create_advantage/attack/defend`, `skill`, `opposition passive|active`, `value` |
| `roll_fate(character, skill, action, difficulty)` | Authoritative `4dF+skill` vs opposition; returns dice/sum/total/shifts/outcome + outcome-specific payload (free invokes, boost, hit shifts). | `character`, `skill`, `action`, `difficulty` or `defender` |
| `invoke_aspect(character, aspect, benefit)` | Spend fate point (or consume free invoke) → `+2 / reroll / +2 teamwork / +2 obstacle`. Validates relevance + cost. | `character`, `aspect`, `benefit`, `free` bool |
| `compel_aspect(target, aspect, kind)` | Propose event/decision compel; on accept → +1 fate to target from GM infinite; on refuse → −1 from target. GM final say. | `target`, `aspect`, `kind event|decision`, `accept` |
| `create_advantage(character, skill, aspect_name, target)` | Wrapped `roll_fate` for advantage action; places `Aspect(free_invokes=1 or 2)` on target/zone. | `character`, `skill`, `aspect_name`, `target zone|character` |
| `overcome(character, skill, obstacle)` | Wrapped `roll_fate` for overcome; returns succeed/cost/boost per table. | `character`, `skill`, `obstacle_id` |
| `attack(attacker, defender, skill)` | Bundles attack→defend→shifts→stress/consequence proposal. | `attacker`, `defender`, `skill Fight/Shoot/Provoke...` |
| `defend(defender, skill, vs_attack_id)` | Active defense `4dF+skill`; ties grant boost to attacker. | `defender`, `skill` |
| `apply_stress(target, shifts)` | Absorb hits: checks boxes + consequence suggestion; returns `taken_out` if impossible. | `target`, `shifts` |
| `add_consequence(target, severity, name)` | Create sticky aspect with free invoke for attacker. | `target`, `severity mild|moderate|severe|extreme`, `name` |
| `concede(character)` | Exit conflict with `1 + #consequences_this_conflict` fate points from GM infinite; narrates cost. | `character` |
| `declare_story_detail(character, aspect, detail)` | Spend fate point to add canon detail anchored in aspect. | `character`, `aspect`, `detail` |
| `hostile_invoke(invoker, target_aspect)` | Paid invoke on opponent aspect; fate point to defender end-of-scene. | `invoker`, `aspect` |
| `set_zone(name, aspects, connections)` / `move_zone(character, zone)` | Zone graph management; abstract distance. | `name`, `aspects` |
| `check_stress`, `check_consequences`, `check_fate_points`, `check_aspects`, `list_skills`, `ladder_lookup` | Queries | |
| `challenge_progress`, `contest_roll`, `visualize_zones` | Structure helpers | |

All tools log to `state.log_tool` and expose `tool_schemas()` → OpenAI-compatible + `dispatch()`. Error dict on misuse (fate-point shortfall, no free invoke, pyramid violation) — never raise.

### 7.6 Agent Prompts & Harness

**GM** is transactional controller: never rolls silently, sets opposition via tools, inflicts outcome strictly by action table, narrates but tools are authoritative. **Player** loop: `sense→declare action→validate aspect relevance→roll→apply invoke/compel gates→resolve stress/consequence→communicate`.

Wire via `tau_agent.harness.AgentHarness` with `OpenAICompatibleProvider` (LMStudio `:1234`), same shim as `dnd_tools.agents`:

```python
from dnd_tools.agents import make_tau_provider, _tools_to_agent_tools
from tau_agent.harness import AgentHarness, AgentHarnessConfig

tools = FateTools(state)  # or CampaignTools(FateCampaignState(...))
provider = make_tau_provider("http://127.0.0.1:1234/v1", "lm-studio")
harness = AgentHarness(AgentHarnessConfig(
    provider=provider,
    model="qwen3.6-35b-a3b-mtp",
    system=GM_PROMPT_FATE,
    tools=_tools_to_agent_tools(tools),
    max_turns=8,
))
```

**Simulation loop** (`simulation.py` / `session.py`): keep `Simulation.run()` structure — `set_scene (zones+aspects+gm_fate)` → `roll_initiative` (Notice/Investigate) → per-exchange `check_side` → `set_opposition` → `roll_fate` → optional `invoke_aspect`/`compel_aspect` → `create_advantage/overcome/attack/defend` → `apply_stress/add_consequence` → `concede` fork → `clear_stress` / `recover` / `refresh_fate` between scenes → `<End Turn/>`. For campaign, `CampaignSession.add_scene()` initializes `gm_fate = n_pcs` + aspect registry, `run_scene()` delegates to `Simulation`, then `checkpoint()` + `prune_traces()`.

### 7.7 Determinism & Evaluation

- **Seeded RNG**: all `4dF` via `dice.seed(seed_val)` derived from `GameState.seed` / `CampaignState` snapshot; re-seed on `restore()`.
- **Authoritative state**: narration never overrides tool results; tools are isolation boundary.
- **Traces**: every tool call logs to `state.tool_trace` with `{tool, args, result, round, actor}` — same shape as 5e for `metrics.py` (`tactical_optimality`, `acting_quality`, `function_usage`, etc.).
- **Heuristic fallback**: `heuristic_player_turn()` mirrors paper's greedy policy but for Fate: pick lowest `Fair→Good` overcome reachable, `create advantage` if no free invokes, `attack` otherwise, degrade gracefully if LLM unavailable.

### 7.8 Minimal CLI Wiring

```python
# dnd_tools/cli.py pattern — add fate subcommand
# dnd-tools fate-demo --seed 42 --turns 10 [--use-llm --model qwen3.6-35b-a3b-mtp]
# dnd-campaign fate-demo --seed 42 --turns 15 --save run.json
```

### 7.9 What *Not* to Port (v1 scope)

Defer full milestone advancement (skill pyramid rebalance, phase-trio rewriting), detailed stunt builder/extras, and `Fate System Toolkit` dials (magic, vehicles, horror stress) to later; milestone-ops are tracked numerically but resolved narratively. `Fate Accelerated` approaches layer is a flag (`--mode fae|core`) share-model.

---

## 8. The AI Fix — Rigid Prompt Templates

The repo should ship reusable prompt fragments LLM players/GMs paste when they fear softening:

**Invoke gate**:

```
I am attempting [action: create advantage / overcome / attack / defend, skill: Fight +3, goal: disarm guard] using aspect [Aspect: Angry Mob in zone Courtyard] because [relevance: mob blocks guard's retreat, I shove him into them].
I rolled 4dF [+, -, blank, +] = +1 → total 4 (+1 shifts vs Fair +2? compute). I spend 1 fate point (or consume 1 free invoke from Exposed Hinge) for +2 / reroll / +2 teamwork / +2 obstacle as per fate-srd.com/fate-core/four-actions and fate-srd.com/fate-core/invoking-compelling-aspects.
Show the updated total, free invoke consumption, fate point flow (hostile → recipient end-of-scene), and outcome per the Four Actions table (fail/tie/succeed/style) BEFORE narrating.
Do not soften — use the SRD outcome table verbatim.
```

**Compel gate**:

```
You have aspect [Trouble: Debt to the Syndicate] in situation [Negotiating with Loan Shark in zone Market].
I propose a [decision/event] compel: it makes sense you'd [decide to accept his terrible deal / have your contact recognize you], which goes wrong when [he adds a tracking aspect / you lose leverage].
Per fate-srd.com/fate-core/invoking-compelling-aspects and fate-point-economy: if you accept, gain 1 fate point from GM infinite pool; if you refuse, pay 1 fate point to infinite pool. I (GM) have final say but you may negotiate the complication.
Show the fate point delta explicitly, then narrate the compel cost.
```

The tool surface enforces both by **requiring** `set_opposition` before any `roll_fate`, by requiring `invoke_aspect`/`compel_aspect` flows to spend/earn fate points through validated pools, and by requiring `apply_stress`/`add_consequence` to absorb shifts exactly — zero handwave.

---

## 9. References

- SRD HTML source: https://fate-srd.com/fate-core (all subpages above) — CC BY 3.0; mirrors Fate Core System text. Fetched 2026-09-09 for this note.
- SRD HTML source: https://fate-srd.com/fate-condensed — condensed refinements (free invoke stacking, aspect "always true," stress recovery wording), CC BY 3.0.
- Fate Condensed canonical PDF/free text: https://www.faterpg.com / https://evilhat.com/product/fate-condensed/ — by PK Sullivan, Lara Turner, Fred Hicks, Richard Bellingham, Robert Hanz, Sophie Lagacé.
- Fate Core PDF/print: https://evilhat.com/product/fate-core-system/ ; DriveThruRPG https://www.drivethrurpg.com/product/114903/Fate-Core-System
- Official licensing page: https://fate-srd.com/about-site / https://evilhat.com — Fate™ trademark Evil Hat Productions; Powered by Fate logo used with permission.
- Paper frame: `ref/31_Setting_the_DC_Synthesis.md` — the tool-grounded audit pattern this implementation extends.
- Cross-system implementation precedents in this repo: `ref/blades-in-the-dark.md`, `ref/tricube-tales.md`, `ref/tricube-tactics.md`, `ref/sword-and-sorcery.md` (architecture/prompt/harness patterns reused).

*End of condensed implementation reference.*
