"""CampaignTools — delegated wrapper around dnd_tools.tools.Tools.

Isolated module: does NOT edit Tools. Delegates all 30+ paper tools and adds
campaign-level tools (long_rest, short_rest, checkpoint, summary).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dnd_tools.tools import Tools

from .state import CampaignState


class CampaignTools:
    """Wraps Tools(inner GameState) + CampaignState helpers.

    LLM sees a unified schema list: base paper tools + campaign tools.
    All mutations still go through authoritative GameState and are logged
    to inner.tool_trace.
    """

    def __init__(self, cstate: CampaignState):
        self.cstate = cstate
        self.inner_tools = Tools(cstate.inner)

    # -- delegation: expose base tools directly -----------------------------
    def __getattr__(self, name: str) -> Any:
        # delegate any Tools method (check_hp, roll_attack, move_player, etc.)
        if hasattr(self.inner_tools, name):
            return getattr(self.inner_tools, name)
        raise AttributeError(name)

    def dispatch(self, name: str, args: dict[str, Any]) -> Any:
        # first try campaign tools, then base tools
        if hasattr(self, name) and name in {
            "long_rest",
            "short_rest",
            "checkpoint",
            "save_checkpoint",
            "load_checkpoint",
            "get_summary",
            "prune_traces",
        }:
            fn = getattr(self, name)
            return fn(**args)
        return self.inner_tools.dispatch(name, args)

    # -- campaign-level tools -----------------------------------------------
    def long_rest(self, name: str | None = None) -> dict[str, Any]:
        """Full heal + restore slots for one or all players. Honors paper economy."""
        res = self.cstate.long_rest(name)
        self.cstate.inner.log_tool("long_rest", {"name": name}, res)
        self.cstate.checkpoint()
        return res

    def short_rest(self, name: str) -> dict[str, Any]:
        res = self.cstate.short_rest(name)
        self.cstate.inner.log_tool("short_rest", {"name": name}, res)
        return res

    def checkpoint(self) -> dict[str, Any]:
        self.cstate.checkpoint()
        res: dict[str, Any] = {"history_len": len(self.cstate.history)}
        self.cstate.inner.log_tool("checkpoint", {}, res)
        return res

    def save_checkpoint(self, path: str) -> dict[str, Any]:
        p = self.cstate.save(path)
        res = {"path": str(p)}
        self.cstate.inner.log_tool("save_checkpoint", {"path": path}, res)
        return res

    def load_checkpoint(self, path: str) -> dict[str, Any]:
        loaded = CampaignState.load(path)
        # restore into current cstate (keep object identity for Tools binding)
        self.cstate.restore(loaded.snapshot())
        self.cstate.inner.tool_trace = loaded.inner.tool_trace
        self.cstate.inner.transcript = loaded.inner.transcript
        res = {"path": path, "round": self.cstate.round}
        self.cstate.inner.log_tool("load_checkpoint", {"path": path}, res)
        return res

    def get_summary(self) -> dict[str, Any]:
        """Compact state summary for LLM context (replaces feeding full trace)."""
        from .memory import summarize_state

        s = summarize_state(self.cstate)
        self.cstate.inner.log_tool("get_summary", {}, s)
        return s

    def prune_traces(self, keep_last: int = 200) -> dict[str, Any]:
        self.cstate.prune_traces(keep_last=keep_last)
        res = {"tool_trace_len": len(self.cstate.inner.tool_trace)}
        self.cstate.inner.log_tool("prune_traces", {"keep_last": keep_last}, res)
        return res

    # -- schemas ------------------------------------------------------------
    def tool_schemas(self) -> list[dict[str, Any]]:
        base = self.inner_tools.tool_schemas()
        extra: list[dict[str, Any]] = [
            {
                "type": "function",
                "function": {
                    "name": "long_rest",
                    "description": "Long rest: full heal, restore spell slots, clear temp buffs (one or all players)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Character name or omit for all players"}
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "short_rest",
                    "description": "Short rest: reset speed/action economy",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "checkpoint",
                    "description": "Snapshot current state to bounded history",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "save_checkpoint",
                    "description": "Persist snapshot + tail traces to file",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_summary",
                    "description": "Compact campaign summary for LLM context window",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "prune_traces",
                    "description": "Prune tool_trace/transcript to last N entries",
                    "parameters": {
                        "type": "object",
                        "properties": {"keep_last": {"type": "integer"}},
                        "required": [],
                    },
                },
            },
        ]
        # ensure Path is handled if someone imports tools directly
        _ = Path
        return base + extra
