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

- `dnd-tools` / `dnd-campaign` / `tricube` remain unchanged; `triple-o`
  consumes `dnd_tools.dice` for seeded determinism and exposes `tau-ai`
  compatible `AgentTool`s via `TripleOTools.tool_schemas()`.
- Bring your own character Traits — background, alignment, flaws, skills, etc.

## Testing & quality

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run ty check .
```
