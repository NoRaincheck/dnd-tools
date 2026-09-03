# scripts — workspace examples

Self-documenting examples for `dnd-workspace`. Each script's docstring contains the
actual output from `tau-ai` (or heuristic fallback), so you can read the I/O without running.

| Script | What it shows | Run |
|---|---|---|
| `full_campaign.py` | **Canonical** — combines `dnd-tools` (paper) + `dnd-campaign` (long-horizon). Party → 2 encounters (outdoor/indoor) → rests → checkpoint/prune → persistence. Supports heuristic or `tau-ai` (`--use-llm`). | `uv run python scripts/full_campaign.py --seed 42 --turns 5` |
| `minimal_encounter.py` | Low-level `dnd-tools` only — single `GameState` + `Tools` + `Simulation` without campaign wrapper. Good for unit tests / paper reproduction. | `uv run python scripts/minimal_encounter.py --seed 42 --turns 5` |

## tau-ai notes

Both scripts use `tau-ai` via `dnd_tools.agents`:
- `make_tau_provider(base_url, api_key)` → `OpenAICompatibleProvider`
- `_tools_to_agent_tools(tools)` → `list[AgentTool]` (each dispatches to `Tools.dispatch`)
- `run_tau_player_turn_sync` / `LLMClient` (alias `TauLLM`) → `AgentHarness` loop

If LMStudio (or any OpenAI-compatible endpoint) is not running at `--base-url`,
the scripts fall back to `heuristic_player_turn` — trace shape is identical, only narration differs.
Set `OPENAI_API_KEY` / `--base-url https://api.openai.com/v1` for hosted LLMs.

## Quick verification

```bash
uv sync
uv run python scripts/full_campaign.py --seed 42 --turns 5 | head -n 50
uv run python scripts/minimal_encounter.py --seed 42 --turns 3 | head -n 30
```
