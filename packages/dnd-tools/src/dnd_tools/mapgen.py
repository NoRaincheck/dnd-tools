"""Seedable map generation — indoor rasterized + outdoor procedural."""

from __future__ import annotations

import random

from .models import Cell


def make_outdoor_map(seed: int, w: int = 20, h: int = 20) -> list[list[Cell]]:
    rng = random.Random(seed)
    cells: list[list[Cell]] = [[Cell(x=x, y=y, z=0, valid=True) for x in range(w)] for y in range(h)]
    # Add height variation sparse so LoS mostly clear (keep tactical but not blocked every line)
    for y in range(h):
        for x in range(w):
            if rng.random() < 0.04:
                cells[y][x].valid = False  # tree/rock
            else:
                r = rng.random()
                if r < 0.02:
                    cells[y][x].z = 2
                elif r < 0.07:
                    cells[y][x].z = 1
                else:
                    cells[y][x].z = 0
    # ensure start/end anchors traversable
    cells[0][0].valid = True
    cells[0][0].z = 0
    cells[h - 1][w - 1].valid = True
    cells[h - 1][w - 1].z = 0
    # ensure connectivity via simple BFS carve if needed: clear a path
    # carve straight corridor if blocked
    for i in range(min(w, h)):
        cells[i][i].valid = True
    return cells


def make_indoor_map(seed: int, layout: dict | None = None, w: int = 20, h: int = 20) -> list[list[Cell]]:
    """Rasterize from compact JSON: {rooms:[{x,y,w,h}], walls:[{x,y}], doors:[{x,y}]}"""
    rng = random.Random(seed)
    cells: list[list[Cell]] = [[Cell(x=x, y=y, z=0, valid=False) for x in range(w)] for y in range(h)]
    if layout is None:
        # generate 3 rooms connected by corridors
        rooms: list[tuple[int, int, int, int]] = []
        for _ in range(3):
            rw, rh = rng.randint(4, 8), rng.randint(4, 8)
            rx = rng.randint(1, w - rw - 1)
            ry = rng.randint(1, h - rh - 1)
            rooms.append((rx, ry, rw, rh))
            for y in range(ry, ry + rh):
                for x in range(rx, rx + rw):
                    cells[y][x].valid = True
                    cells[y][x].z = 0
        # connect rooms with L-shaped corridors
        for i in range(len(rooms) - 1):
            x1, y1 = rooms[i][0] + rooms[i][2] // 2, rooms[i][1] + rooms[i][3] // 2
            x2, y2 = (
                rooms[i + 1][0] + rooms[i + 1][2] // 2,
                rooms[i + 1][1] + rooms[i + 1][3] // 2,
            )
            for x in range(min(x1, x2), max(x1, x2) + 1):
                cells[y1][x].valid = True
            for y in range(min(y1, y2), max(y1, y2) + 1):
                cells[y][x2].valid = True
    else:
        rooms = layout.get("rooms", [])
        for r in rooms:
            for y in range(r["y"], r["y"] + r["h"]):
                for x in range(r["x"], r["x"] + r["w"]):
                    if 0 <= y < h and 0 <= x < w:
                        cells[y][x].valid = True
        for wv in layout.get("walls", []):
            if 0 <= wv["y"] < h and 0 <= wv["x"] < w:
                cells[wv["y"]][wv["x"]].valid = False
        for d in layout.get("doors", []):
            if 0 <= d["y"] < h and 0 <= d["x"] < w:
                cells[d["y"]][d["x"]].valid = True
        # height from layout if provided
        for row in cells:
            for c in row:
                # indoor flat
                c.z = 0
    return cells
