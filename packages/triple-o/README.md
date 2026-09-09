# triple-o — Obvious / Option / Odd middleware

System-agnostic implementation of the **Triple-O** framework
([gist](https://gist.github.com/NoRaincheck/3cb4b109e0d100a1327b6c7516351c36))
as a `dnd-tools` / `tau-ai` middleware to force LLM creativity.

> When action is uncertain, define three plausible courses:
> **Obvious (4-6)** — most predictable given Traits,
> **Option (2-3)** — reasonable alternative,
> **Odd (1)** — left-field / impulsive.
> Roll 1d6 to choose. This constrains the option space while injecting randomness.

## Triple-O at a glance

| Roll | Category | Meaning |
|------|----------|---------|
| 4,5,6 | **Obvious** | Default / expected action |
| 2,3 | **Option** | Tactical or narrative alternative |
| 1 | **Odd** | Unexpected / atypical |

**Double Down (Advantage / Disadvantage):** if Traits make an outcome highly likely,
roll `2d6` and pick the result that most favours established behaviour
(`advantage` → higher die favours Obvious, `disadvantage` → lower die favours Odd).

**Spark Tables** (1d6 each) help interpret *how* an action is executed:

- **Disposition & Motivation:** Aggressive/Greed … Erratic/Justice
- **Action & Method:** Investigate/Stealth … Flee/Deception

## Package layout

```
src/triple_o/
  core.py       — deterministic engine (seeded via dnd_tools.dice)
  spark.py      — spark tables
  tools.py      — typed tool API (OpenAI schemas) for tau harness
  middleware.py — prompt + turn wrapper that forces Triple-O
  cli.py        — `triple-o demo` / `triple-o spark`
```

## Quickstart

```bash
uv sync
uv run triple-o demo --seed 42
uv run triple-o spark --seed 42 --times 5
uv run triple-o demo --use-llm --model qwen3.6-35b-a3b-mtp  # requires LMStudio :1234
uv run pytest packages/triple-o
```

> **LLM-verified (2026-09-08, LMStudio :1234, `qwen3.6-35b-a3b-mtp` + `tiel-coder-35b-a3b-mtp` via `tau-ai`/`tau_agent`)**

<details open>
<summary><strong>Verified LLM run — triple-o demo (<code>triple-o demo --seed 42 --use-llm --model qwen3.6-35b-a3b-mtp</code>)</strong></summary>

```
--- Lyra ---
Situation: Goblin horde blocks the gate; party must breach
Chosen: {'character': 'Lyra', 'situation': 'Goblin horde blocks the gate; party must breach', 'traits': ['keen eye', 'reckless'], 'roll': 1, 'rolls': [1], 'category': 'odd', 'choice': 'Feign surrender or stumble forward to get close, then unleash a surprise attack.', 'proposal': {'character': 'Lyra', 'situation': 'Goblin horde blocks the gate; party must breach', 'obvious': 'Charge straight into the fray, trusting my reckless courage to carve a path through them.', 'option': 'Scan the perimeter with my keen eye for a weak point or guard post to flank.', 'odd': 'Feign surrender or stumble forward to get close, then unleash a surprise attack.', 'traits': ['keen eye', 'reckless']}}
Narration: I drop my weapon and stumble forward with a pitiful cry, playing the part of a broken surrenderer to slip past their front line. Once I'm within striking distance, my erratic desperation turns to cold vengeance as I spring back to my feet and drive my blade into the nearest goblin.

--- Borin ---
Situation: A trapped corridor hisses — do they search for traps?
Chosen: {'character': 'Borin', 'situation': 'A trapped corridor hisses', 'traits': ['stubborn', 'brave'], 'roll': 2, 'rolls': [2], 'category': 'option', 'choice': "I'll throw a rock down the hall first to trigger any mechanisms before stepping in.", 'proposal': {'character': 'Borin', 'situation': 'A trapped corridor hisses', 'obvious': "I'll search the corridor carefully for traps, checking every hissing vent and loose tile.", 'option': "I'll throw a rock down the hall first to trigger any mechanisms before stepping in.", 'odd': "I'll just kick the nearest wall and yell at the corridor to stop hissing.", 'traits': ['stubborn', 'brave']}}
Narration: Borin snatches a loose stone from the corridor wall and hurls it deep into the hissing darkness, carefully watching where it lands to trigger any hidden mechanisms before daring to step forward.

--- Group ['brave', 'cautious', 'reckless'] ---
Roll 6 (obvious) → hold position

Tool traces: 7 — deterministic seed 42
```
*LLM correctly invoked `propose_triple_o` → `roll_triple_o` (seed 42: Lyra roll 1 → odd, Borin roll 2 → option, Party roll 6 → obvious), deterministic selection of proposed branches, and narrated the chosen `choice` with trait-aware flavour via `TripleOMiddleware`.*

</details>

<details>
<summary><strong>Verified LLM run — second model (<code>triple-o demo --seed 42 --use-llm --model tiel-coder-35b-a3b-mtp</code>)</strong></summary>

```
--- Lyra ---
Situation: Goblin horde blocks the gate; party must breach
Chosen: {'character': 'Lyra', 'situation': 'Goblin horde blocks the gate; party must breach', 'traits': ['keen eye', 'reckless'], 'roll': 1, 'rolls': [1], 'category': 'odd', 'choice': 'Crawl low to investigate the surroundings for a secret drain grate or loose stone I could exploit.', 'proposal': {'character': 'Lyra', 'situation': 'Goblin horde blocks the gate; party must breach', 'obvious': 'Charge straight at the goblins with reckless fury, trying to smash through the gate with brute force.', 'option': 'Use my keen eye to spot a weak point or gap in the horde and lead a coordinated pincer breach.', 'odd': 'Crawl low to investigate the surroundings for a secret drain grate or loose stone I could exploit.', 'traits': ['keen eye', 'reckless']}}
Narration: The die lands on 1 — Odd. Lyra drops low and scours the base of the gate with a hawk's eye, ignoring the jeering goblin horde. Something's off about the foundation — a rusted drain grate, half-rusted shut, sits in the shadow where the horde's formation leaves it unwatched. With erratic, impulsive grit, she pries at the grating, hunting for a way in that brute force could never find.

--- Borin ---
Situation: A trapped corridor hisses — do they search for traps?
Chosen: {'character': 'Borin', 'situation': 'A trapped corridor hisses — do they search for traps?', 'traits': ['stubborn', 'brave'], 'roll': 2, 'rolls': [2], 'category': 'option', 'choice': 'Borin pauses to scan the floor and walls for pressure plates and vents before advancing cautiously.', 'proposal': {'character': 'Borin', 'situation': 'A trapped corridor hisses — do they search for traps?', 'obvious': 'Borin charges headlong down the hissing corridor, trusting bravery to outrun any trap.', 'option': 'Borin pauses to scan the floor and walls for pressure plates and vents before advancing cautiously.', 'odd': 'Borin slams his weapon against the wall to provoke the trap early and stomp through the triggered hazards.', 'traits': ['stubborn', 'brave']}}
Narration: Borin plants his boots and holds the party back, eyes tracing the hissing walls for pressure plates and vent slits before he dares a step — methodical and low, reading the corridor for its triggers rather than charging in.

--- Group ['brave', 'cautious', 'reckless'] ---
Roll 6 (obvious) → hold position

Tool traces: 7 — deterministic seed 42
```
*Same seeded rolls (1→odd, 2→option, 6→obvious) produce consistent category Selection across models, but the LLM-generated prose for each branch differs — demonstrating Triple-O's creativity-forcing: constrained option space + randomness, open-ended narration.*

</details>

<details>
<summary><strong>Verified heuristic run (<code>triple-o demo --seed 42</code> — no LLM)</strong></summary>

```
Lyra — ambush at gate
  roll 6 → obvious: snipe from rooftop (agile, keen eye)
  spark: Aggressive / Confrontational → Investigate the surroundings via Stealth / Subterfuge

Borin — pit trap ahead
  roll 6 → obvious: probe with pole
  spark: Inquisitive / Curious → Attack or confront the obstacle via Brute Force / Violence

Mira — rune on altar
  roll 2 → option: touch it with mage hand
  spark: Cautious / Defensive → Flee, reposition, or hide via Deception / Trickery

--- GM Question ---
  Do they search for traps? → odd (1) → No / rush in

--- Group Decision ---
  traits ['brave', 'cautious', 'reckless'] → roll 6 obvious → hold

Tool traces: 8 — heuristic mode (seed 42)
```
*Heuristic fallback uses the same `TripleO` engine + `TripleOTools` (`propose_triple_o` → `roll_triple_o` + `spark_roll`) without an LLM.*

</details>

## Tool-grounded usage

```python
from triple_o import TripleO, TripleOTools

engine = TripleO(seed=42)
tools = TripleOTools(engine)

# LLM proposes three options (validated, logged)
tools.propose_triple_o(
    "Lyra", "ambush at gate", obvious="snipe from roof", option="flank via alley", odd="charge shouting"
)

# deterministic roll chooses one
result = tools.roll_triple_o("Lyra", advantage=None)
# -> {"roll":5, "category":"obvious", "choice":"snipe from roof", ...}

# spark for flavour
tools.spark_roll()  # -> {"disposition":..., "motivation":..., "action":..., "method":...}

# group decision
tools.group_triple_o(["brave", "cautious", "reckless"], ["hold", "negotiate", "flee"])
```

Middleware forces creativity via `TripleOMiddleware`:

```python
from triple_o.middleware import TripleOMiddleware

mw = TripleOMiddleware(engine, tools)
text, choice = mw.run_turn_sync(player_name="Lyra", traits="reckless", situation="trapped", provider=..., model=...)
```

The middleware prompts the LLM to emit three short options, validates them,
rolls, and returns the selected action plus narration — reducing option-space
while keeping randomness.

## Integration

- `dnd-tools` / `dnd-campaign` remain unchanged; `triple-o`
  consumes `dnd_tools.dice` for seeded determinism and exposes `tau-ai`
  compatible `AgentTool`s via `TripleOTools.tool_schemas()`.
- Bring your own character Traits — background, alignment, flaws, skills, etc.

## Testing & quality

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run ty check .
```
