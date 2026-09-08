"""OKF bundle builder — writes a conformant OKF 0.1/0.2 bundle.

Spec: https://okf.md/spec
Conformance requires every non-reserved .md has frontmatter with `type`.
We produce:
  bundle/
    index.md              (no frontmatter, progressive disclosure)
    log.md                (chronological)
    characters/<name>.md  type: Character
    traits/<name>.md      type: Trait
    scenes/<id>.md        type: Scene
    events/<id>.md        type: Effect
    references/...        (optional attester docs)

Bundle is traversable by any OKF consumer (cat, rg, LLM agent).
"""

from __future__ import annotations

import datetime as _dt
import pathlib as _pl
import re
import textwrap
from typing import Any


def _iso_now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).isoformat().replace("+00:00", "Z")


def _yaml_escape(s: str) -> str:
    if any(c in s for c in (":", "#", '"', "'", "\n")) or s.strip() != s or not s:
        return '"' + s.replace('"', '\\"') + '"'
    return s


def _yaml_frontmatter(data: dict[str, Any]) -> str:
    lines: list[str] = ["---"]
    for k, v in data.items():
        if isinstance(v, str):
            lines.append(f"{k}: {_yaml_escape(v)}")
        elif isinstance(v, bool):
            lines.append(f"{k}: {str(v).lower()}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        elif isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                lines.append(f"{k}:")
                for item in v:
                    if isinstance(item, dict):
                        # inline dict as json-ish — minimal
                        import json as _json

                        lines.append(f"  - {_json.dumps(item)}")
                    else:
                        lines.append(f"  - {_yaml_escape(str(item))}")
        elif isinstance(v, dict):
            if not v:
                lines.append(f"{k}: {{}}")
            else:
                lines.append(f"{k}:")
                for kk, vv in v.items():
                    if isinstance(vv, str):
                        lines.append(f"  {kk}: {_yaml_escape(vv)}")
                    else:
                        lines.append(f"  {kk}: {vv}")
        elif v is None:
            lines.append(f"{k}: null")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.strip().lower())
    return s.strip("-") or "untitled"


class OKFBundle:
    """Builder for an OKF bundle on disk. Enables git-style distribution."""

    def __init__(self, root: str | _pl.Path, *, meta_name: str = "fused-campaign", seed: int = 0):
        self.root = _pl.Path(root)
        self.meta_name = meta_name
        self.seed = seed
        self.created_at = _iso_now()
        # in-memory registries for index/log generation
        self._concepts: list[tuple[str, dict[str, Any]]] = []  # (rel_path, frontmatter)
        self._log_entries: list[tuple[str, str]] = []  # (date, line)

    # ------------------------------------------------------------------
    # low-level writers
    # ------------------------------------------------------------------
    def _write_concept(self, rel_path: str, frontmatter: dict[str, Any], body: str) -> _pl.Path:
        if "type" not in frontmatter or not str(frontmatter["type"]).strip():
            raise ValueError(f"OKF concept {rel_path} missing required frontmatter 'type'")
        # enrich with okf_version + generated for 0.2 awareness
        fm = dict(frontmatter)
        fm.setdefault("okf_version", "0.2")
        # trust fields: generated + sources (optional)
        fm.setdefault("generated", {"by": "process:fused", "at": _iso_now()})
        if "timestamp" not in fm:
            fm["timestamp"] = fm["generated"]["at"]  # type: ignore[index]

        out = self.root / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)
        md = _yaml_frontmatter(fm) + "\n" + body.lstrip() + "\n"
        out.write_text(md, encoding="utf-8")
        self._concepts.append((rel_path, fm))
        return out

    def write_character(self, name: str, frontmatter: dict[str, Any], body: str) -> _pl.Path:
        rel = f"characters/{_slug(name)}.md"
        return self._write_concept(rel, {"type": "Character", **frontmatter}, body)

    def write_trait(self, name: str, frontmatter: dict[str, Any], body: str) -> _pl.Path:
        rel = f"traits/{_slug(name)}.md"
        return self._write_concept(rel, {"type": "Trait", **frontmatter}, body)

    def write_scene(self, scene_id: str, frontmatter: dict[str, Any], body: str) -> _pl.Path:
        rel = f"scenes/{_slug(scene_id)}.md"
        return self._write_concept(rel, {"type": "Scene", **frontmatter}, body)

    def write_event(self, effect_id: str, frontmatter: dict[str, Any], body: str) -> _pl.Path:
        rel = f"events/{_slug(effect_id)}.md"
        return self._write_concept(rel, {"type": "Effect", **frontmatter}, body)

    def write_raw(self, rel_path: str, frontmatter: dict[str, Any], body: str) -> _pl.Path:
        return self._write_concept(rel_path, frontmatter, body)

    # ------------------------------------------------------------------
    # log / index
    # ------------------------------------------------------------------
    def add_log(self, message: str, *, date: str | None = None, kind: str = "Update") -> None:
        d = date or _dt.datetime.now(tz=_dt.UTC).date().isoformat()
        # okf log entry headings use ## YYYY-MM-DD
        if not re.match(r"\d{4}-\d{2}-\d{2}", d):
            raise ValueError(f"bad date {d}")
        self._log_entries.append((d, f"**{kind}**: {message}"))

    def _flush_index(self) -> None:
        # root index.md (no frontmatter per spec)
        # Group by top-level directory
        groups: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for rel, fm in self._concepts:
            top = rel.split("/")[0] if "/" in rel else "root"
            groups.setdefault(top, []).append((rel, fm))
        lines: list[str] = [f"# {self.meta_name}", "", f"Seed {self.seed} — generated {self.created_at}", ""]
        # optional okf_version comment in index body (frontmatter not allowed except root okf_version)
        lines.append("<!-- okf_version: 0.2 -->")
        lines.append("")
        for top in sorted(groups):
            lines.append(f"## {top.capitalize()}")
            lines.append("")
            for rel, fm in sorted(groups[top], key=lambda x: x[0]):
                title = str(fm.get("title", rel))
                desc = str(fm.get("description", ""))
                lines.append(f"* [{title}]({rel}) - {desc}")
            lines.append("")
        # citations section
        lines.append("## Citations")
        lines.append("")
        lines.append("[1] [OKF Spec](https://okf.md/spec)")
        lines.append("[2] [Triple-O gist](https://gist.github.com/NoRaincheck/3cb4b109e0d100a1327b6c7516351c36)")
        (self.root / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

        # per-directory index.md
        for top, items in groups.items():
            if top == "root":
                continue
            d = self.root / top
            d.mkdir(parents=True, exist_ok=True)
            sub_lines = [f"# {top.capitalize()}", ""]
            for rel, fm in sorted(items, key=lambda x: x[0]):
                title = str(fm.get("title", rel))
                desc = str(fm.get("description", ""))
                base = _pl.Path(rel).name
                sub_lines.append(f"* [{title}]({base}) - {desc}")
            sub_lines.append("")
            (d / "index.md").write_text("\n".join(sub_lines) + "\n", encoding="utf-8")

    def _flush_log(self) -> None:
        if not self._log_entries:
            return
        # group by date desc
        by_date: dict[str, list[str]] = {}
        for d, line in self._log_entries:
            by_date.setdefault(d, []).append(line)
        out = ["# Update Log", ""]
        for d in sorted(by_date, reverse=True):
            out.append(f"## {d}")
            for entry in by_date[d]:
                out.append(f"* {entry}")
            out.append("")
        (self.root / "log.md").write_text("\n".join(out) + "\n", encoding="utf-8")

    def flush(self) -> _pl.Path:
        """Write index.md and log.md; return bundle root."""
        self.root.mkdir(parents=True, exist_ok=True)
        self._flush_index()
        self._flush_log()
        return self.root

    # ------------------------------------------------------------------
    # traversal helpers (agent-readable)
    # ------------------------------------------------------------------
    def list_concepts(self, type_filter: str | None = None, tag: str | None = None) -> list[dict[str, Any]]:
        out = []
        for rel, fm in self._concepts:
            if type_filter and fm.get("type") != type_filter:
                continue
            if tag and tag not in (fm.get("tags") or []):
                continue
            out.append({"path": rel, **fm})
        return out

    def read_concept(self, rel_path: str) -> str:
        return (self.root / rel_path).read_text(encoding="utf-8")

    @staticmethod
    def validate_bundle(root: str | _pl.Path) -> list[str]:
        """Lightweight OKF conformance check (rules 1+2). Returns error strings."""
        p = _pl.Path(root)
        errs: list[str] = []
        for md in p.rglob("*.md"):
            rel = str(md.relative_to(p))
            if md.name in ("index.md", "log.md"):
                continue
            text = md.read_text(encoding="utf-8")
            if not text.startswith("---"):
                errs.append(f"{rel}: missing frontmatter")
                continue
            parts = text.split("---", 2)
            if len(parts) < 3:
                errs.append(f"{rel}: unclosed frontmatter")
                continue
            fm_text = parts[1]
            # lightweight check: frontmatter must contain a type: field
            has_type = False
            for line in fm_text.splitlines():
                stripped = line.strip()
                # skip list items
                if stripped.startswith("type:"):
                    val = stripped[len("type:") :].strip().strip('"').strip("'")
                    if val:
                        has_type = True
                        break
            if not has_type:
                errs.append(f"{rel}: missing required 'type'")
        return errs

    # ------------------------------------------------------------------
    # markdown body helpers
    # ------------------------------------------------------------------
    @staticmethod
    def body_for_trait(name: str, traits: list[str], flaws: list[str], bonds: list[str]) -> str:
        lines = [f"# {name} — Traits", ""]
        if traits:
            lines += ["## Traits", ""] + [f"* {t}" for t in traits] + [""]
        if flaws:
            lines += ["## Flaws", ""] + [f"* {f}" for f in flaws] + [""]
        if bonds:
            lines += ["## Bonds", ""] + [f"* {b}" for b in bonds] + [""]
        lines += ["## Citations", "", "[1] [OKF Spec](https://okf.md/spec)"]
        return "\n".join(lines)

    @staticmethod
    def body_for_scene(scene: Any) -> str:  # Scene typed loosely to avoid circular
        beats = getattr(scene, "beats", [])
        cast = getattr(scene, "cast", [])
        lines = [
            f"# {scene.title}",
            "",
            f"**Objective:** {scene.objective}",
            "",
            f"**Location:** {scene.location} | **Patron:** {scene.patron} | **Threat:** {scene.threat}",
            "",
        ]
        if cast:
            lines += (
                ["## Cast", ""] + [f"* {c} — see [traits/{_slug(c)}.md](/traits/{_slug(c)}.md)" for c in cast] + [""]
            )
        if beats:
            lines += ["## Beats", ""] + [f"{i + 1}. {b}" for i, b in enumerate(beats)] + [""]
        # link to effects via directory listing
        lines += ["## Effects", "", f"See [events/](/events/index.md) for effect log of scene `{scene.scene_id}`.", ""]
        lines += ["## Citations", "", "[1] [OKF Spec](https://okf.md/spec)"]
        return "\n".join(lines)

    @staticmethod
    def body_for_event(effect: Any) -> str:
        lines = [
            f"# Effect {effect.effect_id}",
            "",
            f"**Scene:** [{effect.scene_id}](/scenes/{_slug(effect.scene_id)}.md) | **Actor:** {effect.actor} | **Kind:** `{effect.kind}` | **Round:** {effect.round}",
            "",
            f"> {effect.summary}",
            "",
        ]
        if effect.payload:
            lines += ["## Payload", "", "```json", textwrap.indent(str(effect.payload), ""), "```", ""]
            # also provide pretty json
            import json as _json

            lines[-3] = _json.dumps(effect.payload, indent=2, default=str)
        lines += ["## Citations", "", "[1] [OKF Spec](https://okf.md/spec)"]
        return "\n".join(lines)

    @staticmethod
    def body_for_character(name: str, char_summary: str, trait_ref: str) -> str:
        return "\n".join(
            [
                f"# {name}",
                "",
                char_summary,
                "",
                f"Traits: see [{trait_ref}]({trait_ref})",
                "",
                "## Citations",
                "",
                "[1] [OKF Spec](https://okf.md/spec)",
            ]
        )
