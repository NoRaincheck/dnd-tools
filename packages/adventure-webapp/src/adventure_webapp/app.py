"""FastAPI app — single-scene choose-your-adventure."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .engine import AdventureEngine
from .scenes import SCENE_TEMPLATES

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Adventure Webapp — Fused Single-Scene", version="0.1.0")
engine = AdventureEngine()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/templates")
def list_templates() -> list[dict[str, Any]]:
    return engine.list_templates()


@app.post("/api/games")
def create_game(payload: dict[str, Any]) -> dict[str, Any]:
    template_id = str(payload.get("template_id") or payload.get("template") or "veiled-archive")
    if template_id not in SCENE_TEMPLATES:
        # allow preset id but fallback
        template_id = "veiled-archive"
    actor = str(payload.get("actor") or "Elaria").strip() or "Elaria"
    seed = payload.get("seed")
    try:
        seed_i = int(seed) if seed is not None and str(seed).strip() != "" else None
    except Exception:
        seed_i = None
    segs = payload.get("segments") or payload.get("clock_segments")
    try:
        segs_i = int(segs) if segs is not None else None
    except Exception:
        segs_i = None
    try:
        game = engine.create_game(template_id=template_id, actor=actor, seed=seed_i, segments=segs_i)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return engine.to_dict(game)


@app.get("/api/games/{game_id}")
def get_game(game_id: str) -> dict[str, Any]:
    try:
        game = engine.get_game(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="game not found") from None
    return engine.to_dict(game)


@app.post("/api/games/{game_id}/choose")
def choose(game_id: str, payload: dict[str, Any]) -> Any:
    try:
        _ = engine.get_game(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="game not found") from None
    pick = str(payload.get("pick") or payload.get("choice") or payload.get("category") or "").strip()
    if not pick:
        raise HTTPException(status_code=400, detail="pick required: obvious|option|odd")
    try:
        res = engine.resolve_pick(game_id, pick, auto=False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except KeyError:
        raise HTTPException(status_code=404, detail="game not found") from None
    # merge full dict for convenience
    g = engine.get_game(game_id)
    res["game"] = engine.to_dict(g)
    return JSONResponse(res)


@app.post("/api/games/{game_id}/auto")
def auto_choose(game_id: str, payload: dict[str, Any] | None = None) -> Any:
    _ = payload
    try:
        _ = engine.get_game(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="game not found") from None
    # pick placeholder — engine will roll triple-o internally
    try:
        res = engine.resolve_pick(game_id, "obvious", auto=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    g = engine.get_game(game_id)
    res["game"] = engine.to_dict(g)
    return JSONResponse(res)


@app.get("/api/games/{game_id}/story")
def get_story(game_id: str) -> dict[str, Any]:
    try:
        game = engine.get_game(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="game not found") from None
    return {"story": game.story_text(), "turns": game.turns_view(), "clock": game.clock(), "completed": game.completed}


# Static site — mount after API so "/" serves index
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    p = STATIC_DIR / "index.html"
    if p.exists():
        return p.read_text(encoding="utf-8")
    return "<h1>Adventure Webapp</h1><p>static/index.html missing</p>"
