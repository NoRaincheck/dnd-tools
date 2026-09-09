# Tricube Tales — Core System Rules (Implementation Condensed)

> Tricube Tales v5 © 2019–2026 Richard Woolcock · **CC BY 3.0** — condensed from `tricube-tales.txt` / `tricube-tales.pdf` (print & phone PDF, DriveThruRPG) and the live implementation in `packages/tricube/` (`src/tricube/models.py:1`, `dice.py:1`, `state.py:1`, `tools.py:1`, `prompts.py:1`, `simulation.py:1`) for LLM + tool-grounded use.
> A minimalist, narrative-driven TTRPG: players roll 1–3d6 vs. difficulty 4–6; GM never rolls.
> Reference sources consulted 2026-09-09: TXT/PDF text layer for Traits/Perks/Quirks/Advancement/Rank/Power Levels/Challenges/Effort/Opposed/Fear/Magic/Superheroes/Vehicles/Mounts/Supernaturals/Combat; `packages/tricube` for authoritative tool schemas and deterministic dice. Tricube Tales™ © Richard Woolcock, CC BY 3.0.

---

## 1. System Overview

### Why Tricube Tales — And the AI Fix

D&D-style systems burden LLMs with d20+mod arithmetic, 30+ modifiers, and GM-rolled opposition — exactly where narration drifts from mechanics. Tricube Tales removes all three:

- **Only players roll** (GM never rolls; §4 *GM role*). The GM is a transactional controller that assigns `trait + difficulty + effort` and narrates; the player-facing `roll_challenge` / `defense_roll` tools are the single source of truth.
- **Bounded difficulty, counted successes**: `4` Easy / `5` Standard / `6` Hard, `1–3d6` each `≥ difficulty = 1 success`, `2–3 successes = exceptional`, `all 1s = critical failure` (`dice.py:19` `roll_tricube`). No sums, no explosion — the LLM cannot mis-add.
- **Token audit**: **Karma** and **Resolve** (`3→6` via advancement) are explicit pools with a `max 1 per challenge` gate (`tools.py:327` `_karma_spent_this_challenge`, `invoke_quirk` pending). **Effort** pools group foes (`state.py:87` `effort_pools`) so the LLM must debit effort per success, not narrate victory early.
- **Relative outcomes**: exceptional success is a *player-narrated* benefit, critical failure is a *GM-narrated* severe complication. The tool does not decide flavour, only `success / exceptional / critical`, which breaks the "LLM softening" failure mode seen in Blades/Fate at `4/5`-like regions.

### Core Loop (Authoritative Flow)

- **Players** roll **1–3d6** vs. difficulty **4–6** (GM-assigned; `3/7` only in Tactics, rare). Only players roll.
- **Success**: ≥1 die ≥ difficulty → eliminate `successes` effort tokens from `effort_target`.
- **Exceptional success**: 2–3 dice succeed → player narrates a benefit / cool outcome (`tools.py:169` → `exceptional` flag).
- **Critical failure**: all dice show `1` → very bad complication (GM narrates; `2` Resolve on defense, permanent affliction candidate).
- **GM role**: assign `trait + difficulty + effort` (rank-derived), describe challenges/NPC actions; never rolls. GM validates `out_of_scope → −1 die` and `rank diff → ±1 difficulty` inside `roll_challenge`.

### Token Economy

| Token | Represents | Start | Max | Who holds | Refresh |
|---|---|---|---|---|---|
| **Karma** | Luck / providence | 3 | 6 (every 2nd advance) | Player, spendable | `+1` on quirk/complication; spent before/after roll (max 1/challenge) |
| **Resolve** | Health / stamina / determination | 3 | 6 (every 2nd advance) | Player, lost on failed defense | Recovered on affliction or `long_rest` (full) |
| **Effort** | NPC resilience / challenge length | varies | — | GM pool per challenge/foe | Debited per success; `0 → defeated` |

### Perks & Quirks

- **Perks** — narrow talents/items/magic/superpowers. Spend **karma** (max 1/challenge) to activate mechanical benefits: reduce difficulty by 1 (retroactively after roll), bypass a challenge without rolling (decide *before* roll), or achieve impossible feats.
- **Quirks** — hindrances declared ***before* rolling**: `+1 difficulty`; recover **1 karma** (or **1 resolve** if the challenge succeeds). Max 1 quirk/affliction per challenge (`tools.py:261` `invoke_quirk` gating, `choose_quirk_reward` on success). GM may also offer karma for a complication tied to a quirk.

---

## 2. Characters

### 2.1 Creation Checklist

1. **Name + archetype** = `trait` (`agile` / `brawny` / `crafty`) + `concept` (profession/race/descriptor, e.g. `agile elven ranger`, `brawny draconic knight`, `crafty inventor`).
2. One **perk** (e.g. `necromancy`, `cybernetic arms`, `fearless commander`).
3. One **quirk** (e.g. `arrogant`, `peg leg`, `vindictive`).
4. **3 karma + 3 resolve**; gear is narrative unless taken as perk (`models.py:55` `TricubeCharacter` defaults `karma=3`, `resolve=3`).

`models.py:82` freezes `combat_style` at creation to `TRAIT_DEFAULT_STYLE` (`agile→ranged`, `brawny→melee`, `crafty→mental`) if not overridden, lowercases `trait`/`combat_style`, and stores `pos` / `initiative` / `alive` / `is_player` for grid compat plus `_pending_quirk` / `_karma_spent_this_challenge` runtime flags.

### 2.2 Archetype → Dice Count (`models.py:88` `dice_count_for`)

| Trait | Rolls **3d6** for | Rolls **2d6** when lacking | Combat style default |
|---|---|---|---|
| **Agile** | Quickness, dexterity, reflexes, stealth, **ranged** combat | any non-agile challenge | ranged |
| **Brawny** | Strength, toughness, athletics, **melee** combat | any non-brawny challenge | melee |
| **Crafty** | Charisma, intellect, willpower, perception, **mental** combat | any non-crafty challenge | mental |

**Out-of-scope penalty**: if challenge requires knowledge outside concept + perks → **−1 die** (so 2d6→1d6, 3d6→2d6). Minimum 1d6 (`models.py:88`, `tools.py:188`).

**Combat style** (`melee/ranged/mental`) defaults to trait but can be overridden at creation and never changes; used for both attack and defense (same `roll_challenge` with `trait` set to the called subtrait/style in Tactics).

### 2.3 Karma & Resolve Detail

- Tokens recover during play but never exceed quota for the session (quota grows via advancement, `models.py:64` `karma_max/resolve_max →6`).
- **Karma spend timing**: retroactive `−1 difficulty` after roll (`tools.py:327` `spend_karma(rolls,difficulty)` → `reevaluate_with_difficulty`), or pre-roll bypass cost for auto-success vs. accessible challenge (`tools.py:358` `bypass_challenge`), or enabling impossible feat.
- **Quirk timing**: declare before roll via `invoke_quirk` (`tools.py:261`), describe quirk in narration, `+1 difficulty` on the *next* `roll_challenge` (can push above 6), then `+1 karma` auto-recovered inside `roll_challenge` with `can_swap_to_resolve` flag if that roll succeeded (`tools.py:228`).

### 2.4 Perks — Four Usage Modes (GM discretion, deterministic for tools)

1. **Impossible → possible** (no karma): perk lets you *attempt* what others cannot (e.g. lift bus with super-strength) → still roll.
2. **Story impact** (1 karma *before* roll): bypass challenge entirely (`bypass_challenge`) or conjure spirit for questioning.
3. **Retroactive edge** (1 karma *after* roll): `−1 difficulty`, narrate perk help (`spend_karma`).
4. **Flavour only** (0 karma): describe magic/tech vs mundane alternative that solves same challenge (telekinesis to push door) → no cost.
5. **Assist allies**: `divine healer` etc. may spend karma to cure ally affliction (`tools.py:433` `recover_affliction` with `perk` check); either helper or target may pay, still max 1/challenge.
- Broadly-defined perks = wider scope but weaker per-instance; narrowly-defined perks = stronger when triggered. Multiple perks can be narrated together but still only 1 karma/challenge.

### 2.5 Quirks & Complications

- `invoke_quirk(character, quirk)` → valid only if quirk name appears in `quirks` or `afflictions` list (`tools.py:270`), not already pending. On the next `roll_challenge` the difficulty is `+1`.
- On resolution: failure → `+1 karma`; success → player chooses `+1 karma` *or* `+1 resolve` via `choose_quirk_reward(reward="karma"|"resolve")` (`tools.py:310`).
- GM may offer karma for a complication (missed clue, insulted NPC) — tie to quirk when possible (`check_karma_resolve` audit).

### 2.6 Advancement & Rank (`models.py:105` `rank_from_advances`)

- Every **1–3 sessions** (or **100 XP**; 1 XP = 1% of an advance): add **one** of: new perk, new quirk, or convert an affliction → quirk.
- **Every second advance**: instead of perk/quirk, may **+1 karma *or* +1 resolve quota** (max 6 each).
- **Rank** (Hack-and-Slash): PCs start **rank 1**, `+1` every **4th advance** (at 4,8,12,16,20 → max 6, `models.py:105`). NPC rank = GM-chosen (`BESTIARY:18` canonical Bear 2 / Dragon 5 / Goblin 1 / Golem 3 / Lich 4 / Ogre 2 / Kobold-Skeleton 1 / Troll 2 / Vampire 3 / Zombie 1). Higher-rank foe → `+1 difficulty`; lower-rank → `−1 difficulty` (handled in `tools.py:191` when `effort_target` is a ranked character). For 3+ rank gap use **Power Levels** (narrative resolution; collateral resolve loss even if invulnerable).

---

## 3. Challenges

### 3.1 Basic Resolution (authoritative flow, `tools.py:169` `roll_challenge`)

1. GM assigns `trait` (`agile/brawny/crafty`), `difficulty` 4–6 (3/7 only in Tactics, rare), and `effort` tokens if extended (`set_effort` / `set_effort_from_rank` with `effort_for_rank:15` → `rank` or `2×rank` for boss).
2. Determine `dice_count` from archetype + scope (3/2/1; `models.py:88`).
3. Player rolls `dice_count × d6` (individual dice matter, not sum; `dice.py:19`).
4. Count `successes = #{die ≥ difficulty}`. `0` = failure; `≥1` = success; `≥2` = exceptional; `all==1` = critical failure.
5. Each success eliminates **1 effort token** (`state.py:87` `effort_pools[target] -= min(pool, successes)`); group of similar foes = one challenge with `N` tokens.
6. Narrate outcome relative to character competence (see §3.3); on failure apply cost (`defense_roll` → `−1 resolve`, `−2` on critical via `state.py:197` `update_resolve`).

### 3.2 Difficulty Scale

| Die ≥ | Label | Typical use |
|---|---|---|
| 4 | Easy | Crude lock, weak foe |
| 5 | Standard | Most challenges / enemies |
| 6 | Hard | Elite foe, complex task |

Tactics extends to `3` Very Easy / `7` Very Hard (requires `6` on 2 dice = success, `6` on all 3 = exceptional); `3→2` only via karma, never via edge/knacks.

### 3.3 Success & Failure Are Relative

- Neither best nor worst outcome should break believability. Master thief fails simple lock → takes longer/complication, not impossible. Unarmed scholar vs dozen soldiers → best is clean escape, not slaughter. Scholar translating magic text: even exceptional success may yield less than wizard's normal failure.
- There is **always** a cost for failure; otherwise no roll.

### 3.4 Exceptional Success Benefits

- Player narrates extra benefit. If no effort tokens, GM may grant mechanical benefit such as **−1 difficulty** for another roll (ally or self) — **cannot reduce below 3** (only karma can push 3→2, enforced in `tools.py:348` `max(2, ...)`).

### 3.5 Price of Failure

- Normal failure: spotted sneaking, missed attack, failed climb; may **lose 1 resolve** (via `defense_roll` or `update_resolve`), or `+1 difficulty` on next roll, or introduce complication.
- Critical failure (`1,1` or `1,1,1`): very bad, often bad luck; if normal failure `= 1` resolve, critical `= 2` resolve (`tools.py:389` `defense_roll`). Always narrate interesting complication (tool snaps in lock, foe slams jaw).

### 3.6 Defeat & Afflictions (`state.py:197` `update_resolve`, `models.py:42` `Affliction`)

- **Defeated** = out of **resolve** (PC) or out of **effort** (challenge/NPC). Victor decides victim's fate.
- At **0 resolve**: gain an **affliction** (`broken arm`, `phobia`, `bruised ego`, `lycanthropy`, etc.), **recover all resolve** (`resolve → resolve_max`), but **cannot participate for remainder of scene** (unconscious/fleeing/too hurt). Resume next scene. `state.py:208` auto-appends `affliction_r{round}` if caller hasn't chosen one.
- **>3 afflictions → retired** from play (`models.py:96` `retired`, `state.py:218` `alive=False`). Return only if afflictions cured.
- Afflictions act like GM-triggered quirks (GM decides when they apply); quirks are player-triggered. Death is narrative; GM must warn if failure = death.

### 3.7 Recovery

- Fleeting afflictions (e.g. `fleeing in fear`) removed end-of-scene automatically (`state.py:412` `long_rest` filters `recovery in ("scene","minutes","hours")`).
- Others last hours/days/weeks at GM discretion (`models.py:42` `recovery: scene|hours|days|weeks|months|years|permanent`).
- PC with suitable **perk** may spend **karma** to cure an affliction (`tools.py:433` `recover_affliction`; narrative `+1 karma` check, structural cost gated). **Permanent** afflictions (from critical failure) cost **permanent karma** (`karma_max−=1`) to remove *unless* converted to a quirk via an advance.

### 3.8 Effort Challenges

- Each die ≥ difficulty removes 1 token; challenge defeated when pool → 0.
- PCs may cooperate (multiple rolls required); **each failed roll has consequences** (resolve loss, complication).
- Group similar enemies: e.g. 6 goblins = one challenge with 6 effort vs. 6 individual 1-effort checks — GM's call (tool `effort_target` is freeform; the state does not mandate one-pool-per-entity).

### 3.9 Opposed Challenges (`dice.py:63` `opposed_result`, `tools.py:502` `opposed_challenge`)

- Both sides roll as normal (per their archetype, `2–3d6` + scope).
- Each treats **other's highest die** as their difficulty (highest roll wins).
- Tie-break: most dice matching difficulty wins as **normal success** (e.g. `5,5,5` beats `5,5,2` beats `5,2,2`). Full tie → interpret as equally favourable.
- Both critical failures → `both_crit` → both suffer terrible outcomes.
- NPC vs NPC: GM decides outcome or asks players to roll for them.

---

## 4. Combat (Simple Turn-by-Turn)

> For tactical grid play see `tricube-tactics.md` / `tactics.pdf`. Below is the Tales core.

### 4.1 NPCs as Challenges

- Assign **difficulty** 4–6 (most `=5`) + **effort** pool (`1` per foe, or grouped). Use `set_effort(target, tokens)` or `set_effort_from_rank`.
- Use **Traits** to modify difficulty: `agile/brawny/crafty → +1` vs that trait; `clumsy/weak/stupid → −1`. Example: shooting `agile+weak` goblin `=6`; hitting in melee `=4`.
- **Ranks**: effort ≈ `rank` (boss `=2×rank`, may be `+1` rank). Bestiary (`models.py:110` `BESTIARY`):

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

### 4.2 Turn Order & Resolution (`state.py:163` `roll_initiative`)

- Follow narrative where possible (no strict initiative required; for LLM use `roll_initiative()` — `1d6 + rank` deterministic via `roll_tricube(1,4)`, sorted descending, stored as `initiative_order`/`current_turn_idx`/`round`).
- **Players roll to attack** on their turn (`roll_challenge`); **players roll to defend** on enemy's turn (`defense_roll`).
- **Lose 1 resolve on failed defense**, **2 on critical failure**. Only **one defense roll per turn** — vs. most dangerous attacker if multiple foes (GM picks `defense_roll` once).
- Exceptional defense/attack benefits apply as in Challenges (player-narrated).

### 4.3 Post-Combat

- At 0 resolve → affliction as above; recovered resolve for next scene.
- Gear/vehicles/mounts that are narrative do not add dice; perks/quirks do.

---

## 5. Genre Rules (condensed, all are perk-gated)

### 5.1 Hack-and-Slash — Traits, Ranks, Effort, Trappings

- As above. Boss = double effort + possibly `+1` rank. Apply rank difficulty mod and trait mods cumulatively.

### 5.2 Magic & Psionics

- As **perks** (`pyromancy`, `geomancy`, `psionicist`). Spending karma enables greater feats. **Narrative only** — if GM calls for agile challenge, mage still resolves as agile even via magic. Broad magic perk → GM asks for a **limitation**:
  - `Destructive` (collateral), `Draining` (spend resolve not karma), `Focus` (wand/staff, days to replace), `Personal` (self only), `Ritualistic` (minutes to prepare, no karma without prep), `Source` (needs nearby energy/matter), `Unsubtle` (gestures/incantations obvious).
- **Fixed spell lists** (optional): choose 3 spells at creation (name + limitation; more limitations = more potent). Learn new spells in play at GM discretion (scrolls, advances).

### 5.3 Fear & Insanity (`tools.py:519` `fear_check`)

- **Crafty 3d6**, others **2d6**; `−1` die if no prior exposure to that fear (concept/perks). Failure → **−1 resolve**; 0 resolve → flee or gain mental disorder.

### 5.4 Superheroes

- Powers = **perks** (e.g. `spider powers`, `iron power suit`). Broad powers take **limitations**: `Devices`, `Grounded`, `Intimidating`, `Negation` (substance), `Non-Offensive`, `Suit-Up`, `Unreliable` (GM may replace karma spend with complication).

### 5.5 Power Levels

- Extreme mismatches → no roll, narrate. Even invulnerable PCs can lose resolve via collateral (bystanders, humiliation, press).

### 5.6 Vehicles

- Minor: treat as gear/perk.
- **Major vehicles as characters**: `concept + perk + quirk`, **3 resolve** (no karma), advance at GM discretion. Driver rolls with **own trait** but may use vehicle's concept/perks/quirks as if own. Use Power Levels for starfighter vs dreadnought.

### 5.7 Sieges & Battles

- Each side maintains token pool. PC commander uses **crafty** challenges to eliminate opposing tokens; difficulty set by relative power/position. Individuals may eliminate tokens but risk own resolve on failed defense.

### 5.8 Other Subsystems

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
Mage: *roll_challenge(character=Mage, trait=brawny, difficulty=5) → rolls [2]
    dice_count 1d6 (2d6−1 scope) → [2] <5 fail* → spend_karma(rolls=[2], difficulty=5)
    → difficulty 5→4, reevaluate [2] <4 still fail; narrates elemental sputtering.
GM: Two skeletons turn to face you (effort 1 each, grouped 2).
Mage: Fireball them!
GM: Standard crafty, difficulty 5, dice_count auto 2d6 (crafty match).
Mage: *roll_challenge(Mage, crafty, 5, effort_target="skeletons") → [5,6] → 2 successes → exceptional
    → effort_removed 2 → both skeletons defeated, player narrates twin bursts.*
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

packages/tricube/src/tricube/            # additive Tricube package (used here)
  models.py   Trait, CombatStyle, Affliction, TricubeCharacter (karma/resolve/rank/pos),
              BESTIARY, effort_for_rank, rank_from_advances
  dice.py     seeded RNG, roll_tricube(dice_count, difficulty), reevaluate_with_difficulty, opposed_result
  state.py    TricubeState (players/monsters/pos/effort_pools/initiative/round/affliction_log/tool_trace),
              TricubeCampaignState (snapshot/restore/checkpoint/prune/save/load, long_rest)
  tools.py    TricubeTools + TricubeCampaignTools — ~30 typed tools + OpenAI schemas + dispatch()
  prompts.py  GM_PROMPT / PLAYER_PROMPT — transactional, sense→plan→validate→act→communicate
  agents.py   Tau harness wrappers + heuristic (greedy closest foe, check LoS, karma/quirk gates)
  simulation.py TricubeSimulation — scene init + turn loop (roll_challenge/defense_roll/affliction)
  session.py  TricubeCampaignSession — multi-scene via TricubeCampaignState
  memory.py   summarize_state(), compact_transcript() — bounded LLM context
  cli.py      tricube demo / gen-scenarios
```

No file under `dnd-tools/` is edited for Tricube. The `tricube` package is a workspace member (`pyproject.toml:1` `members = ["packages/*"]`, `packages/tricube/pyproject.toml` declares `dependencies = [dnd-tools, dnd-campaign, tau-ai]`).

### 7.2 New Models for Tricube (additive, isolated)

```python
# packages/tricube/src/tricube/models.py  (actual, trimmed for reference)

from dataclasses import dataclass, field

class Trait(str, Enum): agile="agile"; brawny="brawny"; crafty="crafty"
class CombatStyle(str, Enum): melee="melee"; ranged="ranged"; mental="mental"
TRAIT_DEFAULT_STYLE = {"agile":"ranged","brawny":"melee","crafty":"mental"}

@dataclass
class Affliction:
    name: str  # "broken arm", "lycanthropy", "despair"
    permanent: bool = False  # True if from critical failure
    recovery: str = "scene"  # scene|hours|days|weeks|months|years|permanent
    location: str | None = None
    source: str | None = None

@dataclass
class TricubeCharacter:
    name: str
    trait: str  # agile|brawny|crafty (lowercased in post_init)
    concept: str  # "elven ranger", "draconian knight"
    combat_style: str = ""  # melee|ranged|mental — frozen to trait if unset
    perks: list[str] = field(default_factory=list)
    quirks: list[str] = field(default_factory=list)
    afflictions: list[Affliction] = field(default_factory=list)
    karma: int = 3
    karma_max: int = 3  # grows to 6
    resolve: int = 3
    resolve_max: int = 3  # grows to 6
    rank: int = 1  # 1..6, rank_from_advances(advances)
    advances: int = 0
    xp: int = 0  # 1 XP = 1% of an advance
    # map/runtime (reuses dnd_tools Cell/dice for grid/LoS)
    pos: tuple[int,int,int] = (0,0,0)
    initiative: int = 0
    alive: bool = True
    is_player: bool = True
    # challenge gates (not persisted as content)
    _pending_quirk: str | None = None
    _karma_spent_this_challenge: bool = False
    _effort_init: int | None = None

    def dice_count_for(self, required_trait:str, *, out_of_scope:bool=False) -> int:
        base = 3 if self.trait==required_trait.lower() else 2
        return max(1, base - (1 if out_of_scope else 0))

    @property
    def retired(self) -> bool: return len(self.afflictions) > 3
```

`models.py:105` `rank_from_advances = min(6, 1+advances//4)`, `models.py:110` `BESTIARY` + `models.py:128` `effort_for_rank(rank, is_boss)` map directly to `state.py:88` `effort_pools` and `tools.py:191` rank-diff logic.

### 7.3 Dice Engine Extension (`dice.py`)

Deterministic helper seeded by `TricubeState.seed` via `dnd_tools.dice.seed`:

```python
# packages/tricube/src/tricube/dice.py
from dnd_tools.dice import seed as base_seed  # re-exported

def roll_tricube(dice_count:int, difficulty:int) -> dict:
    rolls = [_rng.randint(1,6) for _ in range(dice_count)]
    successes = sum(1 for r in rolls if r >= difficulty)
    return {"dice_count":dice_count,"difficulty":difficulty,"rolls":rolls,
            "successes":successes,"success":successes>=1,"exceptional":successes>=2,
            "critical_failure":all(r==1 for r in rolls),"effort_removed":successes}

def reevaluate_with_difficulty(rolls:list[int], new_difficulty:int) -> dict:
    successes = sum(1 for r in rolls if r >= new_difficulty)
    return {"rolls":list(rolls),"difficulty":new_difficulty,"successes":successes,
            "success":successes>=1,"exceptional":successes>=2,
            "critical_failure":all(r==1 for r in rolls),"effort_removed":successes}

def opposed_result(a_rolls:list[int], b_rolls:list[int]) -> dict:
    # each treats other's highest die as difficulty; most matches wins; both 1s → both_crit
    ...
```

Keep existing `roll_dice()` for `d20/AC` paths; Tricube never touches them. New helpers clamp `difficulty` only at floor `2` inside `tools.py:348` `spend_karma` (`max(2, diff−1)`) so `3→2` is the sole sub-3 path, matching RAW floor (§3.4).

### 7.4 GameState / CampaignState Additions

**`state.py : TricubeState`** (either subclass `GameState` or new module, here a dedicated `src/tricube/state.py` that reuses `Cell/dice`):
- Replaces `GameState`'s HP-centric `update_hp` with `update_resolve(name, delta)` and `check_resolve` (aliased as `check_hp`/`update_hp` for compat, `state.py:231`); `0 → affliction_r{round}` placeholder + `affliction_log`/`death_log` + `resolve→resolve_max` + `>3 afflictions → alive=False` matching §3.6.
- Adds `effort_pools: dict[str,int]` for multi-token challenges (grouped foes share a pool, e.g. `"skeletons":2`).
- Adds `roll_initiative()` (`1d6+rank` deterministic via `roll_tricube(1,4)`, sorted descending) for LLM ordering where RAW leaves it narrative; otherwise narrative order is valid.
- Keeps `map: list[list[Cell]]`, `pos`, `initiative_order`, `round`, `tool_trace`, `transcript` exactly as before for trace compatibility (`state.py:76`).
- Keeps `seed()` determinism — every roll goes through `_rng` (`dnd_tools.dice._rng`), re-seeded on `restore()`.

**`state.py : TricubeCampaignState`** — already wraps `TricubeState`:
- `snapshot()` / `restore()` serialize `players/monsters/positions/effort_pools/initiatives/round/affliction_log/campaign_meta`; `restore` re-seeds dice.
- `long_rest(name?)` → full resolve + clear non-permanent afflictions (`recovery in ("scene","minutes","hours")`), capped by `>3 → retired`; `short_rest` is a no-op bookkeep for compat.
- `checkpoint()` / `save(path)` / `load(path)` / `prune_traces(keep_last)` unchanged — call between scenes to bound LLM context (keep first ~10 + last 200 entries, `state.py:429`).

### 7.5 Tool Schemas (LLM-visible)

**Scene-level `TricubeTools`** (`tools.py:1`, each method logs to `state.log_tool` and returns JSON; `tool_schemas()` → OpenAI-compatible `{type:"function", function:{name,description,parameters}}`, `dispatch(name, args)` matches `tools.py:920`):

| Tool | Purpose | Key params |
|---|---|---|
| `roll_challenge(character, trait, difficulty, dice_count?, out_of_scope?, effort_target?)` | Authoritative 1–3d6 roll; counts successes, removes effort from pool, applies quirk `+1 diff` + auto `+1 karma` recovery, logs rolls/challenge_id | `character`, `trait agile|brawny|crafty`, `difficulty 2–7`, `dice_count 1–3`, `effort_target?` |
| `invoke_quirk(character, quirk)` | Declare **before** next `roll_challenge`: `+1 difficulty` on that roll, then `+1 karma` (or `+1 resolve` if that roll succeeds, via `choose_quirk_reward`) — max 1/challenge | `character`, `quirk` |
| `choose_quirk_reward(character, reward karma|resolve)` | After a successful quirk roll, swap the auto `+1 karma` to `+1 resolve` if desired | `character`, `reward` |
| `spend_karma(character, rolls, difficulty)` | `−1 difficulty` retroactively (after roll), consume 1 karma, max 1/challenge, `3→2` allowed, never below 2 | `character`, `rolls`, `difficulty` |
| `bypass_challenge(character, perk)` | 1 karma *before* roll to auto-succeed flavour-bypassable challenge (`tools.py:358`) | `character`, `perk` |
| `defense_roll(character, trait, difficulty?, out_of_scope?)` | Wraps `roll_challenge` + `update_resolve` (`−1` on fail, `−2` on crit, `0` on exceptional) | `character`, `trait` |
| `apply_affliction(target, name, permanent?, recovery?, location?)` | Victim-chosen at 0 resolve; `permanent=True` for crit-fail path | `target`, `name` |
| `check_afflictions(target)` | Affliction list + retirement check (`>3 → retired`) | `target` |
| `recover_affliction(target, affliction_name, perk?)` | Spend karma (`permanent` costs `karma_max−=1`) to cure; or convert via advance (narrative) | `target`, `affliction_name` |
| `check_karma_resolve(target)` | Current/max karma & resolve + rank/trait/perks/afflictions/pos | `target` |
| `check_effort(target)` / `set_effort(target, tokens)` / `set_effort_from_rank(target, rank, is_boss?)` | GM initializes/monitors effort pools (rank or 2×rank for boss) | `target`, `tokens`/`rank` |
| `opposed_challenge(char_a, char_b, trait_a?, trait_b?)` | Both `roll_tricube` under the hood; compare `opposed_result` + tie-break | `char_a`, `char_b` |
| `fear_check(character, difficulty?, inexperienced?)` | Crafty 3d6 else 2d6, `−1 die` if inexperienced; failure `→ −1 resolve` | `character` |
| `check_trait(name)` / `check_valid_attack_line(a,b)` / `move_player(name,x,y)` / `visualize_map()` / `roll_initiative()` / `end_turn(character)` / `print_affliction_log()` | Queries/movement/bookkeeping (aliases `check_hp`/`update_hp` map to resolve) | — |

**Campaign tools** (`tools.py:932` `TricubeCampaignTools`):

`long_rest(name?)`, `short_rest(name)`, `checkpoint()`, `save_checkpoint(path)`, `load_checkpoint(path)`, `get_summary()` (compact `memory.summarize_state`), `prune_traces(keep_last)`.

### 7.6 Agent Prompts & Harnesses

Reuse `dnd_tools.agents` pattern verbatim — **never subprocess, never raw LLM strings as truth** (`agents.py:1`, `prompts.py:1`):

```python
# src/tricube/prompts.py
GM_PROMPT = """You are the Game Master (GM) for Tricube Tales — a transactional controller.
General Rules: use ai_functions for all mechanics; GM never rolls; only players roll via roll_challenge/defense_roll.
Carry effort pools, track resolve/karma, grant quirk karma and spend_karma −1 diff, handle 0-resolve→affliction, etc.
Follow strict recipe: query → (optional) move → validate scope/dice → assign difficulty/effort → roll_challenge → (optional spend_karma) → resolve effort/affliction → narrate relative outcome → end_turn + <End Turn/>."""
PLAYER_PROMPT = """You play as a Tricube Tales player ... sense→plan→validate→act→communicate:
  check karma/resolve/effort → declare quirk BEFORE roll → roll_challenge (correct trait + out_of_scope flag)
  → spend_karma AFTER only once/challenge → bypass BEFORE if narrative → defense via GM → check effort → narrate → <DM/>."""
```

Wire via `agents.py:_tools_to_agent_tools()` + `AgentHarness` (`OpenAICompatibleProvider` for LMStudio at `:1234`):

```python
from dnd_tools.agents import make_tau_provider, _tools_to_agent_tools
from tau_agent.harness import AgentHarness, AgentHarnessConfig

tools = TricubeTools(state)  # or TricubeCampaignTools(TricubeCampaignState(...))
provider = make_tau_provider("http://127.0.0.1:1234/v1", "lm-studio")
harness = AgentHarness(AgentHarnessConfig(
    provider=provider, model="qwen3.6-35b-a3b-mtp",
    system=GM_PROMPT, tools=_tools_to_agent_tools(tools), max_turns=6,
))
```

**Simulation loop** (`simulation.py`): keep `Simulation.run()` structure — `roll_initiative` (or narrative order) → per-turn `check_side` → (optional `move` toward target) → `check_valid_attack_line` → `roll_challenge` (`invoke_quirk` gate before, `spend_karma` gate after, rank/out_of_scope handled inside) → `defense_roll` on enemy turn → `apply_affliction` at 0 resolve → `end_turn` (+ `choose_quirk_reward` if applicable) / buff expiry → `<End Turn/>`. For campaign, `CampaignSession.add_encounter()` initializes Tricube parties + effort pools, `run_encounter()` delegates to `Simulation`, then `checkpoint()` + `prune_traces()` (`memory.py:10` `summarize_state`/`compact_transcript`).

### 7.7 Determinism & Evaluation

- **Seeded RNG**: all rolls via `dnd_tools.dice.seed(seed_val)` derived from `TricubeState.seed` / `TricubeCampaignState` snapshot; re-seed on `restore()`.
- **Authoritative state**: narration never overrides tool results; tools are isolation boundary (return `error` not raise on obvious misuse — harness catches; `invoke_quirk`/`spend_karma` return `{valid:False, reason:...}` on gate violation).
- **Traces**: every tool call logs to `state.tool_trace` with `{tool, args, result, round, actor}` — same shape as 5e for `metrics.py` (`tactical_optimality`, `acting_quality`, `function_usage`, etc.).
- **Heuristic fallback**: `agents.py:heuristic_player_turn()` mirrors paper's greedy policy but for Tricube: pick nearest foe, check LoS, declare quirk if karma-starved (`<2`), roll with correct trait/scope, spend karma if `0 successes` and pool available, degrade gracefully if LLM unavailable.

### 7.8 The AI Fix — Rigid Prompt Templates

When the LLM fears softening, paste these gates (derive from `prompts.py:1`):

**Invoke gate** (quirk before roll):

```
I declare perk/quirk [quirk: Arrogant] BEFORE rolling. I call invoke_quirk(character, quirk)
so the next roll_challenge will be at difficulty +1, and on resolution I will recover
+1 karma (or swap to +1 resolve via choose_quirk_reward if the roll succeeds).
Show invoke_quirk → roll_challenge(dice_count by trait/scope) → recovery delta BEFORE narrating.
```

**Spend gate** (karma after roll):

```
I rolled [rolls: 2,3] vs difficulty 5 with trait brawny → 0 successes (fail).
I spend 1 karma AFTER the roll via spend_karma(rolls=[2,3], difficulty=5) → difficulty 5→4.
Re-evaluate vs 4 BEFORE narrating. Max 1 karma per challenge — do not allow a second spend_karma.
```

**Defense gate**:

```
On the enemy turn I must call defense_roll(character, trait, difficulty) exactly once
vs the most dangerous attacker. On fail −1 resolve, on critical fail (all 1s) −2 resolve
and the affliction at 0 resolve is permanent-capable. Show resolve delta BEFORE narrating.
```

The tool surface enforces all three by gating `invoke_quirk` pending state, `spend_karma` max-1 + `rolls+difficulty` requirement, and `defense_roll` single-per-turn resolve accounting.

### 7.9 Minimal CLI Wiring

```python
# tricube/cli.py pattern (also `dnd-tools tricube-demo` alias)
# tricube demo --seed 42 --turns 10 [--use-llm --model qwen3.6-35b-a3b-mtp] [--map outdoor|indoor]
# tricube gen-scenarios --seed 42 --out scenarios
# tricube run-scenario scenarios/tricube_scenario_01.json --turns 10
```

Reuse `dnd_tools.cli` arg parsing; `llm = LLMClient` alias → `TauLLM(provider, model)`. Map via `dnd_tools.mapgen.make_indoor_map` / `make_outdoor_map` (20×20).

### 7.10 What *Not* to Port

- Do **not** reintroduce AC/HP/damage dice for Tricube combat (resolve + effort are sufficient). Tactics supplement's `stride`, `knacks`, `edge modifiers` are optional phase-2 — keep Tales core first, add Tactics later behind a feature flag (`tricube-tactics.md`).
- Do **not** invent new traits/styles — keep `agile/brawny/crafty` canonical; micro-setting renames (`athletic/buff/cunning`) must map back.

---

## 8. Challenge Resolution Flow (pseudocode, deterministic)

```python
# GM assigns — mirrors tools.py:169 roll_challenge
difficulty = 5  # 4 easy, 5 standard, 6 hard (3/7 reserved for Tactics)
trait = "brawny"
effort = effort_for_rank(target.rank, is_boss=False)  # or GM-set token pool
dice_count = chr.dice_count_for(trait, out_of_scope=out_of_scope)  # 3 if match else 2, then −1 if oos, min 1

# optional quirk gate (before roll, must call invoke_quirk first)
if player_declares_quirk and chr._pending_quirk is None:
    invoke_quirk(chr.name, quirk_name)  # device: next roll_challenge will be difficulty+1

# authoritative roll
r = roll_challenge(chr.name, trait, difficulty, dice_count, out_of_scope, effort_target)
# r contains: rolls, successes, success, exceptional, critical_failure, effective_difficulty, challenge_id
# quirk auto-recovery (+1 karma, can swap to resolve) is already applied inside roll_challenge

# optional karma gate (after roll, max 1, must provide rolls+difficulty)
if r.successes == 0 and player_spends_karma and chr.karma > 0 and not chr._karma_spent_this_challenge:
    r = spend_karma(chr.name, rolls=r.rolls, difficulty=r.effective_difficulty)  # diff 5→4; recounts
    # chr.karma is debited inside spend_karma

effort_removed = min(effort_pool[effort_target], r.successes)
effort_pool[effort_target] -= effort_removed
if r.critical_failure:
    resolve_cost, affliction_permanent = 2, True
elif not r.success:
    resolve_cost, affliction_permanent = 1, False
else:
    resolve_cost = 0  # exceptional → player narrates benefit; may grant −1 difficulty to next roll (floor 3)
if resolve_cost:
    update_resolve(chr.name, -resolve_cost)
if chr.resolve == 0:  # handled by update_resolve: auto placeholder affliction + restore + retirement check
    apply_affliction(chr.name, name=choose_affliction(), permanent=affliction_permanent, recovery="scene")
    # chr.resolve is now resolve_max; chr.alive is False iff len(afflictions)>3
```

---

## 9. References

- Source text: `ref/tricube-tales.txt` / `tricube-tales.pdf` (print & phone PDF, DriveThruRPG) — CC BY 3.0, Richard Woolcock 2019–2026.
- Tactical supplement: `ref/tricube-tactics.txt` / `tricube-tactics.pdf` — adds strides, knacks, edge modifiers, etc. (phase 2, feature-flagged).
- Implementation ground truth: `packages/tricube/src/tricube/models.py:1` (Trait/CombatStyle/Affliction/TricubeCharacter/BESTIARY/effort_for_rank), `dice.py:1` (roll_tricube/reevaluate/opposed), `state.py:1` (TricubeState/TricubeCampaignState, resolve/affliction/initialive/map/LoS/prune), `tools.py:1` (TricubeTools/TricubeCampaignTools schemas + dispatch), `prompts.py:1` (GM/PLAYER strict recipes), `simulation.py:1`.
- Paper context: `ref/31_Setting_the_DC_Synthesis.md` — DC-setting evaluation frame (Function Usage / Parameter Fidelity / State Tracking / Efficiency / Acting Quality / Tactical Optimality) this implementation extends.

---

## 10. Notes on this Markdown

- Reformatted from `tricube-tales.txt` using section-order retention and `pdftotext -layout -raw`-style verification where PDF layering duplicated text. Tables (Token Economy, Archetype→Dice, Difficulty Scale, Bestiary) are normalised from running text.
- `tools.py` field names (`_pending_quirk`, `_karma_spent_this_challenge`, `effort_pools`) are quoted where they are authoritative state, not prose invention.
- No rules were invented for §1–§6; wording is kept verbatim where possible (e.g. affliction/retirement language), with only formatting, table structure, and cross-references added for implementation. §7–§8 are additive guidance explicitly marked as such.

*End of condensed implementation reference.*
