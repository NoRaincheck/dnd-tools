# dnd-tools workspace

`uv` workspace for paper-grounded D&D simulation and long-horizon campaign layer.

Implements the framework from *Setting the DC: Tool-Grounded D&D Simulations to Test LLM Agents* (NeurIPS 2025 Workshop). Paper © original authors; code in this repo is MIT (implementation only).

## Packages

| Package | Path | Purpose |
|---|---|---|
| `dnd-tools` | `packages/dnd-tools/` | Paper implementation (frozen) — 30+ validated tools, seeded simulation, 6 metrics. See [`packages/dnd-tools/README.md`](packages/dnd-tools/README.md) for full reproduction docs. |
| `dnd-campaign` | `packages/dnd-campaign/` | Long-horizon campaign layer — `CampaignState` (snapshots/persistence/rest), `CampaignTools` (delegation), `CampaignSession` (multi-encounter), memory compaction. Depends on `dnd-tools` via workspace. |

```
packages/dnd-tools/src/dnd_tools/   # paper
packages/dnd-campaign/src/dnd_campaign/  # campaign
```

## Quickstart

```bash
uv sync
uv run dnd-tools demo --seed 42 --turns 10
uv run dnd-campaign demo --seed 42 --turns 10
```

## Testing & quality

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run ty check .
```

All package tests live in `packages/<name>/tests/`. Paper reproduction (27 scenarios, heuristic baseline `O 0.795 | A 0.552 | func_err 2.1%`) is documented in [`packages/dnd-tools/README.md`](packages/dnd-tools/README.md#reproducing-paper-tables) — not repeated here.

## License

MIT — implementation only; paper © authors.
