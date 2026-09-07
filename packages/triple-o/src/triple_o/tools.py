"""TripleOTools — typed, validated tool surface for Tau LLM harness.

Each method logs to an internal tool_trace (mirrors dnd_tools.tools pattern)
and validates proposals before rolling — the roll is authoritative and
deterministic via ``TripleO``'s seeded RNG.

Tool surface exposed to Tau:
  propose_triple_o, roll_triple_o, group_triple_o, ask_triple_o,
  spark_roll, spark_disposition, spark_action,
  roll_triple_o_die (bare 1d6 with category)
"""

from __future__ import annotations

from typing import Any

from .core import Advantage, TripleO
from .spark import roll_action, roll_disposition, roll_spark


class TripleOTools:
    """Tool-grounded API for LLM to use Triple-O as creativity middleware."""

    def __init__(self, engine: TripleO | None = None, seed: int | None = None):
        if engine is not None:
            self.engine = engine
        else:
            self.engine = TripleO(seed=seed or 0)
        self.tool_trace: list[dict[str, Any]] = []
        self._pending: dict[str, Any] | None = None  # last proposal per character

    # -- internal logging -------------------------------------------------
    def _log(self, tool: str, args: dict[str, Any], result: Any) -> None:
        self.tool_trace.append({"tool": tool, "args": args, "result": result})

    # -- proposal ---------------------------------------------------------
    def propose_triple_o(
        self,
        character: str,
        situation: str,
        obvious: str,
        option: str,
        odd: str,
        traits: list[str] | None = None,
    ) -> dict[str, Any]:
        """LLM proposes three plausible branches.

        The roll MUST happen after this via ``roll_triple_o``; the choice is
        not free-form — the die picks the branch.
        """
        proposal = self.engine.propose(character, situation, obvious, option, odd, traits=traits)
        # stash pending for simple roll_triple_o without args
        self._pending = proposal.as_dict()
        self._pending["engine_proposal_obj"] = proposal  # internal, stripped in log
        res = {"pending": proposal.as_dict(), "note": "now call roll_triple_o to choose"}
        # clone without internal obj for log
        log_res = {"pending": proposal.as_dict()}
        self._log("propose_triple_o", {"character": character, "situation": situation}, log_res)
        return res

    def roll_triple_o(
        self,
        character: str | None = None,
        advantage: str | None = None,
        obvious: str | None = None,
        option: str | None = None,
        odd: str | None = None,
        situation: str | None = None,
        traits: list[str] | None = None,
    ) -> dict[str, Any]:
        """Roll 1d6 (or 2d6 with advantage/disadvantage) to select among O/O/O.

        Either reuses the last ``propose_triple_o`` pending proposal (if
        ``character`` matches) or accepts inline ``obvious``/``option``/``odd``.
        """
        adv: Advantage = None
        if advantage == "advantage" or advantage == "disadvantage":
            adv = advantage

        proposal = None
        # reuse pending?
        if self._pending and obvious is None and option is None and odd is None:
            # check character matches pending
            pending_char = self._pending.get("character")
            if character is None or character == pending_char:
                proposal = self._pending.get("engine_proposal_obj")
        if proposal is None:
            # need inline trio or pending miss — build one
            if not (obvious and option and odd):
                raise ValueError("Need either pending propose_triple_o or explicit obvious/option/odd")
            if not character:
                character = self._pending.get("character", "unknown") if self._pending else "unknown"
            if not situation:
                situation = self._pending.get("situation", "") if self._pending else ""
            proposal = self.engine.propose(
                character, situation or "situation", obvious, option, odd, traits=traits or []
            )
        result = self.engine.resolve(proposal, advantage=adv)
        # clear pending after consume
        self._pending = None
        self._log("roll_triple_o", {"character": result["character"], "advantage": adv}, result)
        return result

    # -- bare die ---------------------------------------------------------
    def roll_triple_o_die(self, advantage: str | None = None) -> dict[str, Any]:
        """Bare 1d6 → category without proposal (for questions / group assignment)."""
        adv: Advantage = None
        if advantage == "advantage" or advantage == "disadvantage":
            adv = advantage
        r = self.engine.roll(advantage=adv)
        res = r.as_dict()
        self._log("roll_triple_o_die", {"advantage": adv}, res)
        return res

    # -- group ------------------------------------------------------------
    def group_triple_o(
        self,
        traits: list[str],
        plans: list[str],
        advantage: str | None = None,
    ) -> dict[str, Any]:
        """Party dilemma: 3 traits → 3 plans (index 0 obvious, 1 option, 2 odd) then roll."""
        adv: Advantage = None
        if advantage == "advantage" or advantage == "disadvantage":
            adv = advantage
        res = self.engine.group_resolve(list(traits), list(plans), advantage=adv)
        self._log("group_triple_o", {"traits": traits, "plans": plans, "advantage": adv}, res)
        return res

    # -- questions (GM intent) -------------------------------------------
    def ask_triple_o(
        self,
        question: str,
        yes_is_obvious: bool = True,
        advantage: str | None = None,
    ) -> dict[str, Any]:
        """Answer a GM question like 'Do they search for traps?' via 1d6 flavour."""
        adv: Advantage = None
        if advantage == "advantage" or advantage == "disadvantage":
            adv = advantage
        res = self.engine.question(question, yes_is_obvious=yes_is_obvious, advantage=adv)
        self._log("ask_triple_o", {"question": question, "yes_is_obvious": yes_is_obvious}, res)
        return res

    # -- spark ------------------------------------------------------------
    def spark_roll(self) -> dict[str, Any]:
        res = roll_spark()
        self._log("spark_roll", {}, res)
        return res

    def spark_disposition(self) -> dict[str, Any]:
        res = roll_disposition()
        self._log("spark_disposition", {}, res)
        return res

    def spark_action(self) -> dict[str, Any]:
        res = roll_action()
        self._log("spark_action", {}, res)
        return res

    # -- dispatch + schemas (OpenAI-compatible) ---------------------------
    def dispatch(self, name: str, args: dict[str, Any]) -> Any:
        fn = getattr(self, name, None)
        if not fn:
            raise ValueError(f"Unknown Triple-O tool {name}")
        return fn(**args)

    def tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "propose_triple_o",
                    "description": "Propose three branches: obvious (most predictable from Traits), option (reasonable alt), odd (left-field). Must be followed by roll_triple_o which authoritatively picks one via 1d6 (4-6 obvious, 2-3 option, 1 odd).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string", "description": "PC name or 'party'"},
                            "situation": {"type": "string", "description": "Current dilemma / context"},
                            "obvious": {"type": "string", "description": "Obvious branch (1-2 sentences)"},
                            "option": {"type": "string", "description": "Option branch"},
                            "odd": {"type": "string", "description": "Odd branch"},
                            "traits": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["character", "situation", "obvious", "option", "odd"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "roll_triple_o",
                    "description": "Roll 1d6 (or 2d6 with advantage/disadvantage) to choose among the three proposed branches. Use after propose_triple_o; or provide inline obvious/option/odd.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "advantage": {
                                "type": "string",
                                "enum": ["advantage", "disadvantage"],
                                "description": "Double Down: advantage=roll 2d6 keep higher (favours Obvious), disadvantage=keep lower (favours Odd)",
                            },
                            "obvious": {"type": "string"},
                            "option": {"type": "string"},
                            "odd": {"type": "string"},
                            "situation": {"type": "string"},
                            "traits": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "roll_triple_o_die",
                    "description": "Bare 1d6 Triple-O die: 4-6 obvious, 2-3 option, 1 odd. For questions or manual assignment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "advantage": {"type": "string", "enum": ["advantage", "disadvantage"]},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "group_triple_o",
                    "description": "Group decision: 3 traits -> 3 plans (plans[0]=obvious, [1]=option, [2]=odd), roll 1d6 to agree.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "traits": {"type": "array", "items": {"type": "string"}},
                            "plans": {"type": "array", "items": {"type": "string"}},
                            "advantage": {"type": "string", "enum": ["advantage", "disadvantage"]},
                        },
                        "required": ["traits", "plans"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ask_triple_o",
                    "description": "Resolve a GM intent question (e.g. 'Do they search for traps?') via Triple-O: obvious=yes thoroughly, option=partial, odd=no/rush in (flipped if yes_is_obvious=false).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "yes_is_obvious": {"type": "boolean"},
                            "advantage": {"type": "string", "enum": ["advantage", "disadvantage"]},
                        },
                        "required": ["question"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "spark_roll",
                    "description": "Roll both spark tables (Disposition+Motivation and Action+Method, each 1d6) to flavour how a Triple-O outcome is executed. Combine with roll choice.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "spark_disposition",
                    "description": "Roll Disposition & Motivation spark table (1d6).",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "spark_action",
                    "description": "Roll Action & Method spark table (1d6).",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
        ]
