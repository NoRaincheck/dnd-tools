# Setting the DC — Synthesis Note

> Source: Zeng et al., *Setting the DC: Tool-Grounded D&D Simulations to Test LLM Agents*, The First Workshop on Generative and Protective AI for Content Creation, NeurIPS 2025 (39th Conference). UC San Diego / U Penn. Original PDF intentionally not tracked in this repo — this file captures the core ideas in our own words for design reference.

## Why this paper

Single-turn QA and short-horizon benchmarks don't stress what agentic LLMs actually need: long-horizon planning, persistent memory, coordination with allies and adversaries, and strict rule following where fluent narration can be wrong. Dungeons & Dragons was chosen as a natural stress test because it couples:

- initiative-driven turn order (mixed cooperative / adversarial),
- bounded action economy (action / bonus action / reaction / movement / spell slots per turn),
- spatial reasoning with stochastic resolution (dice) and partial observability,
- team tactics that must survive behind dialogue.

Goal: make narration separate from mechanics so fluency can be judged without conflating it with correctness.

## What they built — D&D Agents

A **fully automated, closed-loop combat simulator** where LLMs occupy three roles at once:

- **DM (Dungeon Master)** — transactional controller, authoritative executor. Plans in natural language but every state-changing effect must go through a typed tool. Enforces legality.
- **Players** — 4-member party covering the 12 core 5e classes across scenario groups.
- **Monsters** — adversarial roster controlled by the DM LLM.

Also supports **human–AI co-play**: any 0..N player slots can be taken by a human, the rest filled by LLMs, same mechanics and tools.

This contrasts with FIREBALL / CALYPSO / Avrae-style helpers that log state or suggest commands outside the loop — here the LLM is *in* the loop and every effect is executed via an API, yielding deterministic, auditable traces.

## State

1. **Characters.** Structured 5e-like creation: canonical stats/AC/HP/derived properties from external D&D resources, plus class, speed, spell lists, monster type/size. `CreatePlayerKani` / `CreateMonsterKani` are prompt-driven but validated.
2. **Maps.** Two seedable, height-aware grid generators (discrete `z` per cell, fixed seed = reproducibility):
   - **Indoor** — rasterized from compact JSON (rooms, walls, doors).
   - **Outdoor** — procedural, guaranteed connectivity with distant start/end anchors.
   Slopes affect movement; height-aware line-of-sight gates ranged actions. Visualizable per turn.

## Actions — typed tool API

Every tool is typed, precondition-checked (ownership of initiative, remaining action/bonus/reaction/movement, spell slots, range, LoS, target existence, status effects). Paper groups them as:

1. **Query / validation** — state checks, LoS tests (e.g., line-of-sight, HP, side, properties).
2. **Movement / positioning** — `move`, `dash`, `disengage`.
3. **Dice primitives** — `roll_dice` (`1d20`, `2d20kh1` for advantage, etc.).
4. **Attack / spell resolution** — `roll_attack`, `roll_save`, `roll_dmg` (+ `roll_spell_attack`).
5. **Turn economy / bookkeeping** — `roll_initiative`, `reset_resources`/`reset_speed`, `check_concentration`.
6. **Rendering** — `visualize_map`.

Transitions are **atomic and deterministic given dice rolls**; simulator deducts budgets, applies HP/position/conditions, handles resistances and concentration automatically.

**Observations** = natural-language narration + structured tool returns (dice outcomes, query results). Per-agent local view → partial observability. No hidden global state beyond what tools reveal.

## Agent prompting

- **DM (`GM_PROMPT`)** is a declarative control policy, not hard-coded logic:
  - Recipe per turn: `query → (optional) move → validate → resolve → bookkeep` (initiative via `roll_initiative`; gating via line-of-sight; resolution via attack/save/damage; HP audits, `reset_resources`/`reset_speed`, `<End Turn/>` sentinel).
  - Mechanics are authoritative; narration is descriptive. Explicit `if–then` gates route failures to repairs (reposition, alternate action, end turn). Parameters must come from canonical sources. Economy semantics for Dash/Disengage are budget-tied; within-turn caching encouraged; stable handlers (e.g., opportunity attacks), tactical heuristics and archetypal exemplars (single-target attack roll vs. save-based AoE) generalize without extra code; condition glossary (charmed, prone, restrained, paralyzed, etc.) handled via tools.

- **Players (`PLAYER_PROMPT`)** — `sense → plan → validate → act → communicate`:
  - Query state/resources; pick moves within budgets; gate ranged options via LoS and distance; propose actions by calling simple queries directly but *proposing* state-changing calls for the DM to execute (reduces hallucination / parameter errors); emit 1–2 sentence intent narration plus isolated coordination messages (`<Call/>Name, Message<Call/>`) for flank / focus-fire / peel.

## Evaluation — six axes + 27 scenarios

**Scenarios:** 27 JSON saves, 3×3×3 — three 4-class groups (covering all 12 classes) × three stat tiers (low/medium/high) × three monster–map sets (Goblin Ambush, Kennel in Cragmaw Hideout, Klarg's Cave from *Lost Mine of Phandelver*). Every model runs identical seeds; 10 turns per episode; transcript + ordered tool trace exported per run.

Models: Claude 3.5 Haiku, GPT-4o, DeepSeek-V3 (gpt-oss-120b tried but failed identity consistency; omitted).

**Automated + human metrics:**

1. **Function Usage** — correct function chosen and executable.
2. **Parameter Fidelity** — arguments obey types/budgets/range/LoS.
3. **State Tracking (anti-hallucination)** — buffs, positions, resources, alive/dead/entity identity stay faithful.
4. **Function Efficiency** — no redundant or missing calls (F1 vs. gold plan).
5. **Acting Quality** — persona density + trait diversity (whether narration feels in-character and varied); validated vs. human judges (r≈0.96).
6. **Tactical Optimality** — per-turn reward (1 attack/spell, 0.5 move-only, 0 else) averaged; plus survivability, combat efficiency, resource conservation; validated vs. human (r≈0.98).

Ground truth for tool use is the prompt-adherent plan per model, not a single optimal path; micro-averaged. Human-vs-auto judges align strongly.

## Key findings (paraphrased)

- **Claude 3.5 Haiku most reliable overall**, especially tool reliability / parameter fidelity and combat efficiency; lowest unnecessary-call and missing-call rates, highest F1 (auto: ~1.2% function / 1.1% param errors; human: 95% F1).
- **GPT-4o close behind**; occasionally strongest peaks but higher variance.
- **DeepSeek-V3 trails** — notably higher missing-call rate and hallucination, but competitive on persona density.
- **Hallucination grows with horizon** on all models even after removing late-game entity-state errors; status-effect and resource errors dominate; entity-state confusion is rare but high-rate when it occurs.
- **Resource trade-offs diverge:** in easy scenarios survivability is similar while Haiku is more aggressive (lower remaining resources); in hard scenarios that aggression yields best combat efficiency at cost of conservation.
- Small open models not yet stable for this task — likely pre-training / tuning mismatch, not just scale.
- Structured APIs + tool grounding make error analysis, seeded re-runs, and incremental improvements (prompting, tool-use policy, memory) tractable.

## Limitations & extensions noted

Combat-only scope; progressive degradation in longer horizons; no fine-tuning yet. Future: fine-tune on traces, extend to full campaigns, and transfer the pattern (structured tools + multi-agent loop + auditable traces) to other rule-governed domains (legal simulation, business games, negotiation).

## How we use it here

- Implemented the 6-category tool surface and atomic transition semantics in `src/dnd_tools/tools.py` + `state.py`/`dice.py`.
- Reproduced generation (Kani agents + indoor/outdoor maps) and the generation→simulation loop (Fig.1 in paper) in `simulation.py`.
- Kept the two prompts as declarative contracts (`prompts.py`) and the bookkeeping checklist (`reset_resources/speed`, buff/resist/concentration audits, `<End Turn/>`).
- Seeded reproducibility and the 3×3×3 scenario design are mirrored in `cli.py gen-scenarios` / `eval`.
- Metrics are approximated with lightweight heuristics in `metrics.py` aligned to the paper's formulas (A = ½ persona density + ½ diversity capped at 1; O = mean turn reward).

## Citation (paraphrased)

Zeng, Li, Xi, Zhu, Ammanabrolu — *Setting the DC: Tool-Grounded D&D Simulations to Test LLM Agents* — NeurIPS 2025 Workshop on Generative and Protective AI for Content Creation. Keep the PDF out of version control; cite the workshop preprint and re-derive from this note + code.

## What was left out

Verbatim prompt blocks, table data, and figure artwork are intentionally omitted. Refer to the original workshop PDF from the authors' distribution channel. The checklist / NeurIPS supplemental pages are not relevant to the implementation and are not reproduced here.
