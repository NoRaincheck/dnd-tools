"""sword-and-sorcery — Swords & Sorcery OSR hack (Lasers & Feelings) tool-grounded implementation.

LLM-verified 2026-09-08 (LMStudio :1234, qwen3.6-35b-a3b-mtp via tau-ai/tau_agent).
See README.md for verified transcripts (heuristic + LLM).
Reuses dnd_tools (mapgen, dice, Cell) + dnd_campaign patterns.
"""

from .agents import LLMClient, heuristic_player_turn, make_tau_provider
from .memory import compact_transcript, summarize_state
from .models import SnSCharacter, SnSMonster
from .session import SnSSession
from .simulation import SnSSimulation, create_sns_monster, create_sns_player
from .state import SnSCampaignState, SnSState
from .tools import SnSCampaignTools, SnSTools

__all__ = [
    "LLMClient",
    "SnSCampaignState",
    "SnSCampaignTools",
    "SnSCharacter",
    "SnSMonster",
    "SnSSession",
    "SnSSimulation",
    "SnSState",
    "SnSTools",
    "compact_transcript",
    "create_sns_monster",
    "create_sns_player",
    "heuristic_player_turn",
    "make_tau_provider",
    "summarize_state",
]
