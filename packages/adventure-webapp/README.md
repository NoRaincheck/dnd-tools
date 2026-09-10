# adventure-webapp — Choose-Your-Adventure (single scene, playable)

Plays a single `fused` Scene as a choose-your-adventure:

`user pick (1 of 3) → tool rolls (action_roll) → LLM narrates outcome → tick clock → next beat` until `progress` clock completes.

- 3 options per turn are **LLM-authored Triple-O** (`obvious`/`option`/`odd`, `propose_choice`) — auto mode rolls `triple_o` `1d6` to pick; manual mode forces your pick but **still rolls** `action_roll` so even the safe option can fail/partial.
- `Position/Effect` gate (`risky/standard` by default) → `action_roll` pool derived from `CharacterTraits`, outcome `success 6 / partial 4-5+consequence / failure 1-3+consequence` (`CONSEQUENCE_TABLE`), ticks `limited1/standard2/great3`.
- Story is laid out automatically at scene end — choices offered vs chosen are styled differently, with toggle to hide.

## Run

```bash
uv sync
uv run adventure serve --port 8000 --seed 42
open http://127.0.0.1:8000
# or seeded demo dump (no browser):
uv run adventure demo --seed 42
```

API:

- `GET /` — playable SPA (file://-ish, no build)
- `GET /api/templates` — scene templates
- `POST /api/games` — `{template_id, actor, seed, clock_segments}` → `{game_id, scene, turn, choices, clock}`
- `POST /api/games/{id}/choose` — `{pick: "obvious"|"option"|"odd"}` → roll + narration + next turn or `completed`
- `POST /api/games/{id}/auto` — rolls Triple-O to pick for you
- `GET /api/games/{id}` — state + story timeline
```
