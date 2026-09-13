"""Lonelog notation (https://lonelog.org/) — emit, parse, render.

Core v1.6.0 + Combat Add-on v1.1.0. Five symbols: ``@`` action,
``?`` oracle question, ``d:`` mechanics roll, ``->`` result,
``=>`` consequence. Tags: ``[PC:]`` ``[F:]`` ``[N:]`` ``[L:]``
``[E:]`` ``[Thread:]`` ``[Clock:/Track:/Timer:]``. Combat blocks
``[COMBAT]``/``[/COMBAT]`` with ``Rd#`` round markers and
``@(Name)`` actor prefixes.

Spec is CC BY-SA 4.0 (doc only); session logs produced here are our own.
"""

from __future__ import annotations

import html as _html
import json
import re
from dataclasses import dataclass
from typing import Any, Literal

LONELOG_SPEC_URL = "https://lonelog.org/"
LONELOG_VERSION = "1.6.0"

EventKind = Literal[
    "scene",
    "combat_open",
    "combat_close",
    "round",
    "roster",
    "action",
    "oracle",
    "roll",
    "result",
    "consequence",
    "tag",
    "note",
    "raw",
]


@dataclass(frozen=True)
class LonelogEvent:
    kind: EventKind
    text: str  # full lonelog line (without code fences)
    actor: str | None = None
    round: int | None = None

    def to_line(self) -> str:
        return self.text


# ------------------------------------------------------------------
# Emit helpers — single source of truth for all packages
# ------------------------------------------------------------------


def scene_header(num: int, context: str, combat: bool = True) -> str:
    suffix = " [COMBAT]" if combat else ""
    return f"S{num} *{context}*{suffix}"


def session_header(num: int, date: str = "", extra: str = "") -> str:
    meta = f"Date: {date}" if date else ""
    if extra:
        meta = f"{meta} | {extra}" if meta else extra
    lines = [f"## Session {num}"]
    if meta:
        lines.append(f"*{meta}*")
    return "\n".join(lines)


def encounter_snapshot(
    pcs: dict[str, dict[str, Any]],
    foes: dict[str, dict[str, Any]],
) -> str:
    """One-line combat snapshot: [PC:A|HP x|AC y] [F:B|HP z|Close]."""
    parts: list[str] = []
    for name, s in pcs.items():
        parts.append(pc_tag(name, hp=s.get("hp"), max_hp=s.get("max_hp"), ac=s.get("ac")))
    for name, s in foes.items():
        parts.append(foe_tag(name, hp=s.get("hp"), max_hp=s.get("max_hp"), pos=s.get("pos", "Close")))
    return " ".join(parts)


def pc_tag(name: str, hp: Any = None, max_hp: Any = None, ac: Any = None, extra: str = "") -> str:
    bits = []
    if hp is not None and max_hp is not None:
        bits.append(f"HP {hp}/{max_hp}")
    elif hp is not None:
        bits.append(f"HP {hp}")
    if ac is not None:
        bits.append(f"AC {ac}")
    if extra:
        bits.append(extra)
    inner = f"{name}|{'|'.join(bits)}" if bits else name
    return f"[PC:{inner}]"


def foe_tag(
    name: str,
    hp: Any = None,
    max_hp: Any = None,
    pos: str = "Close",
    status: str = "",
) -> str:
    bits = []
    if hp is not None and max_hp is not None:
        bits.append(f"HP {hp}/{max_hp}")
    elif hp is not None:
        bits.append(f"HP {hp}")
    if pos:
        bits.append(pos)
    if status:
        bits.append(status)
    inner = f"{name}|{'|'.join(bits)}" if bits else name
    return f"[F:{inner}]"


def round_marker(n: int, initiative: list[dict[str, Any]] | None = None) -> str:
    if initiative:
        order = ", ".join(f"{e.get('name')} {e.get('initiative')}" for e in initiative)
        return f"Rd{n} (Init: {order})"
    return f"Rd{n}"


def roster_line(n: int, pcs: dict[str, dict[str, Any]], foes: dict[str, dict[str, Any]]) -> str:
    return f"Rd{n} Roster: {encounter_snapshot(pcs, foes)}"


def action(actor: str | None, text: str) -> str:
    if actor:
        return f"@({actor}) {text}"
    return f"@ {text}"


def oracle_q(question: str) -> str:
    q = question.strip()
    if not q.startswith("?"):
        q = f"? {q}"
    if not q.endswith("?"):
        q = f"{q}?"
    return q


def roll_attack_line(roll: Any, modifier: Any, ac: Any, *, target: str = "") -> str:
    mod = f"+{modifier}" if modifier not in (None, 0) else ""
    vs = f" vs AC {ac}" if ac is not None else ""
    tgt = f" @ {target}" if target else ""
    return f"d: d20{mod}={roll}{vs}{tgt}"


def roll_line(expr: str, result: Any, *, vs: str = "", target: str = "") -> str:
    tgt = f" @ {target}" if target else ""
    vs_s = f" vs {vs}" if vs else ""
    return f"d: {expr}={result}{vs_s}{tgt}"


def result_line(outcome: str, detail: str = "") -> str:
    return f"-> {outcome}{(' ' + detail) if detail else ''}"


def consequence(text: str, tags: str = "") -> str:
    return f"=> {text}{(' ' + tags) if tags else ''}"


def attack_sequence(
    actor: str,
    target: str,
    weapon: str,
    roll: Any,
    ac: Any,
    hit: bool,
    damage: Any = None,
    damage_type: str = "",
    target_hp: Any = None,
    target_max: Any = None,
    target_is_pc: bool = False,
    critical: bool = False,
) -> list[str]:
    """Full @/d:/->/=> combat exchange for one attack."""
    lines = [action(actor, f"Attack {target} with {weapon}" if weapon else f"Attack {target}")]
    crit = " Critical" if critical else ""
    lines.append(f"d: d20={roll} vs AC {ac} -> {'Hit' if hit else 'Miss'}{crit}")
    if hit and damage is not None:
        dt = f" ({damage_type})" if damage_type else ""
        if target_is_pc:
            tags = pc_tag(target, hp=target_hp, max_hp=target_max)
            if target_hp == 0:
                tags = f"[PC:{target}|HP 0]"
        else:
            tags = foe_tag(target, hp=target_hp, max_hp=target_max)
            if target_hp == 0:
                tags = foe_tag(target, status="dead")
        lines.append(consequence(f"{damage} dmg{dt} to {target}.", tags))
    elif not hit:
        lines.append(consequence(f"{actor}'s strike misses {target}."))
    return lines


def death_line(name: str, round_n: int, is_pc: bool = False) -> str:
    tag = f"[PC:{name}|HP 0]" if is_pc else f"[F:{name}|dead]"
    return consequence(f"{name} drops to 0 HP (Rd{round_n}).", tag)


def aftermath(summary: str, tags: str = "") -> list[str]:
    return ["[/COMBAT]", consequence(summary, tags)]


def to_markdown(lines: list[str], title: str = "Session Log") -> str:
    body = "\n".join(lines)
    return f"# {title}\n\n```lonelog\n{body}\n```\n"


# ------------------------------------------------------------------
# Parse — tolerant reader for HTML renderer + metrics
# ------------------------------------------------------------------

_RE_ROUND = re.compile(r"^Rd(\d+)\b")
_RE_SCENE = re.compile(r"^S(\d+)\b")
_RE_ACTOR = re.compile(r"^@\(([^)]+)\)\s?(.*)$")
_RE_TAG = re.compile(r"\[(PC|F|N|L|E|Thread|Clock|Track|Timer)(?::[^\]]*)?\]")
_RE_HIT = re.compile(r"->\s*(Hit|Miss|Success|Fail|Critical)", re.IGNORECASE)
_RE_DEAD = re.compile(r"\bdead\b|\bHP 0\b", re.IGNORECASE)


def parse(lines: list[str]) -> list[LonelogEvent]:
    events: list[LonelogEvent] = []
    cur_round: int | None = None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        m = _RE_ROUND.match(line)
        if m:
            cur_round = int(m.group(1))
            kind: EventKind = "roster" if "Roster:" in line else "round"
            events.append(LonelogEvent(kind, line, round=cur_round))
            continue
        if _RE_SCENE.match(line) or line.startswith("## Session"):
            events.append(LonelogEvent("scene", line, round=cur_round))
            continue
        if line in ("[COMBAT]", "--- COMBAT ---"):
            events.append(LonelogEvent("combat_open", line, round=cur_round))
            continue
        if line in ("[/COMBAT]", "--- END COMBAT ---"):
            events.append(LonelogEvent("combat_close", line, round=cur_round))
            continue
        if line.startswith("?"):
            events.append(LonelogEvent("oracle", line, round=cur_round))
            continue
        ma = _RE_ACTOR.match(line)
        if line.startswith("@"):
            actor = ma.group(1) if ma else None
            events.append(LonelogEvent("action", line, actor=actor, round=cur_round))
            continue
        if line.startswith("d:"):
            events.append(LonelogEvent("roll", line, round=cur_round))
            continue
        if line.startswith("->"):
            events.append(LonelogEvent("result", line, round=cur_round))
            continue
        if line.startswith("=>"):
            events.append(LonelogEvent("consequence", line, round=cur_round))
            continue
        if line.startswith("(") and line.endswith(")"):
            events.append(LonelogEvent("note", line, round=cur_round))
            continue
        if line.startswith("[") and line.endswith("]"):
            events.append(LonelogEvent("tag", line, round=cur_round))
            continue
        events.append(LonelogEvent("raw", line, round=cur_round))
    return events


def is_hit(line: str) -> bool | None:
    m = _RE_HIT.search(line)
    if not m:
        return None
    return m.group(1).lower() in ("hit", "success", "critical")


def is_death(line: str) -> bool:
    return bool(_RE_DEAD.search(line))


# ------------------------------------------------------------------
# Render HTML — self-contained, file:// friendly (no deps, no fetch)
# ------------------------------------------------------------------

_CSS = """body{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;background:#111;color:#e8e6e3}
h1{font-size:1.4rem}a{color:#9ecbff}.bar{position:sticky;top:0;background:#111;padding:.5rem 0;border-bottom:1px solid #333;display:flex;gap:.5rem;flex-wrap:wrap;align-items:center}
button,select{background:#222;color:#eee;border:1px solid #444;border-radius:6px;padding:.3rem .6rem;cursor:pointer}
.log{margin-top:1rem}.ev{padding:.35rem .6rem;border-left:3px solid #444;margin:.25rem 0;background:#1a1a1a;border-radius:0 6px 6px 0;white-space:pre-wrap}
.ev.scene{border-color:#b48cf2;font-weight:700}.ev.round{border-color:#f2c14e;font-weight:700}
.ev.action{border-color:#4da3ff}.ev.oracle{border-color:#b48cf2}.ev.roll{border-color:#ffa94d}
.ev.result-hit{border-color:#51cf66}.ev.result-miss{border-color:#ff6b6b}
.ev.consequence{border-color:#63e6be}.ev.death{border-color:#ff6b6b;background:#2a1515}
.tag{display:inline-block;background:#333;border-radius:4px;padding:0 .35rem;margin:0 .15rem;font-size:.85em}
.tag.pc{background:#1c3d5a}.tag.foe{background:#5a1e1e}.meta{color:#999;font-size:.85em}
"""

_JS = """const evs=[...document.querySelectorAll('.ev')];let i=evs.length;
function show(n){i=Math.max(0,Math.min(evs.length,n));evs.forEach((e,k)=>{e.style.display=k<i?'':'none'});document.getElementById('seq').value=i;document.getElementById('lbl').textContent=i+'/'+evs.length;location.hash='seq='+i}
function filt(){const a=document.getElementById('actor').value;const t=document.getElementById('q').value.toLowerCase();evs.forEach(e=>{const okA=!a||(e.dataset.actor||'')===a;const okT=!t||e.textContent.toLowerCase().includes(t);if(e.style.display!=='none')e.style.display=(okA&&okT)?'':'none'})}
window.addEventListener('DOMContentLoaded',()=>{const m=location.hash.match(/seq=(\\d+)/);show(m?+m[1]:evs.length);
document.getElementById('seq').max=evs.length;document.getElementById('prev').onclick=()=>show(i-1);document.getElementById('next').onclick=()=>show(i+1);
document.getElementById('start').onclick=()=>show(0);document.getElementById('end').onclick=()=>show(evs.length);
document.getElementById('seq').oninput=e=>show(+e.target.value);
let timer=null;document.getElementById('play').onclick=()=>{if(timer){clearInterval(timer);timer=null;return}timer=setInterval(()=>{if(i>=evs.length){clearInterval(timer);timer=null;return}show(i+1)},600)};
document.getElementById('actor').onchange=filt;document.getElementById('q').oninput=filt;})"""


def _classify(ev: LonelogEvent) -> tuple[str, bool]:
    cls = f"ev {ev.kind}"
    death = ev.kind == "consequence" and is_death(ev.text)
    if ev.kind == "result":
        h = is_hit(ev.text)
        cls += " result-hit" if h else (" result-miss" if h is False else "")
    if death:
        cls += " death"
    return cls, death


def _link_tags(text: str) -> str:
    def _rep(m: re.Match[str]) -> str:
        kind = m.group(1).lower()
        css = "tag pc" if kind == "pc" else ("tag foe" if kind == "f" else "tag")
        return f'<span class="{css}">{_html.escape(m.group(0))}</span>'

    # escape first, then re-inject spans (tags contain no HTML-significant chars beyond brackets)
    esc = _html.escape(text)
    return _RE_TAG.sub(lambda m: _rep(m), esc)


def render_html(
    lines: list[str],
    title: str = "Lonelog — Session",
    meta: dict[str, Any] | None = None,
) -> str:
    """Render lonelog lines to a self-contained HTML page."""
    events = parse(lines)
    actors = sorted({e.actor for e in events if e.actor})
    opts = "".join(f"<option>{_html.escape(a)}</option>" for a in actors)
    rows: list[str] = []
    for k, ev in enumerate(events):
        cls, _ = _classify(ev)
        body = _link_tags(ev.text)
        round_s = f"Rd{ev.round}" if ev.round is not None else ""
        rows.append(
            f'<div class="{cls}" data-actor="{_html.escape(ev.actor or "")}">'
            f'<span class="meta">#{k} {round_s}</span> {body}</div>'
        )
    bundle = json.dumps({"lines": lines, "meta": meta or {}}, default=str)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_html.escape(title)}</title><style>{_CSS}</style></head>
<body><h1>{_html.escape(title)}</h1>
<p class="meta">Lonelog <a href="{LONELOG_SPEC_URL}">spec</a> v{LONELOG_VERSION} · {len(lines)} lines ·
<a href="#" onclick="document.getElementById('raw').style.display='block';return false">raw</a></p>
<div class="bar"><button id="start">⏮</button><button id="prev">◀</button>
<button id="play">▶</button><button id="next">▶</button><button id="end">⏭</button>
<input id="seq" type="range" min="0" value="0" style="flex:1"><span id="lbl"></span>
<select id="actor"><option value="">all actors</option>{opts}</select>
<input id="q" placeholder="filter text" size="12"></div>
<div class="log">{"".join(rows) or '<p class="meta">empty log</p>'}</div>
<pre id="raw" style="display:none">{_html.escape(chr(10).join(lines))}</pre>
<script type="application/json" id="lonelog-data">{_html.escape(bundle)}</script>
<script>{_JS}</script></body></html>"""
