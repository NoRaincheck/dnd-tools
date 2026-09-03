"""tricube — Tricube Tales tool-grounded scenes & campaigns.

LLM-verified 2026-09-04 (LMStudio :1234, tiel-coder-35b-a3b-mtp via tau-ai/tau_agent):

>>> tricube scene --seed 42 --turns 3 --use-llm --model tiel-coder-35b-a3b-mtp
=== TRANSCRIPT ===
Initiative: [{'name': 'Lyra', 'initiative': 7}, {'name': 'Fenn', 'initiative': 7}, ...]
--- Player Turn: Lyra (round 1) ---
Lyra: Clean hit — the 6 clears difficulty 4, and the strike drops Goblin1's effort to 0.
*Lyra nocks a second arrow...* Goblin1 defeated (effort 0). <Call/>Fenn, Mira — focus the Ogre...
--- Player Turn: Fenn (round 1) ---
Fenn: Exceptional hit! ... The Ogre's effort pool empties... <Call/>Lyra, Borin — ogre down!...
--- Monster Turn: Ogre ---
Ogre (monster) pressures Fenn: [1, 5, 4] vs 5 -> success resolve cost 0 -> 3/3
Scene ended after 3 turns. Afflictions: {'log': []}
Tool Calls: 26 (visualize_map, check_karma_resolve, check_effort, roll_challenge, etc. all via TricubeTools)

Reuses dnd_tools (mapgen, dice, Cell) + dnd_campaign patterns (snapshot/campaign),
adds Tricube-specific resolve/karma/effort mechanics with tau-ai LLM harness.
"""

from .agents import LLMClient, heuristic_player_turn, make_tau_provider
from .memory import compact_transcript, summarize_state
from .models import Affliction, TricubeCharacter
from .session import TricubeSession
from .simulation import TricubeSimulation, create_tricube_monster, create_tricube_player
from .state import TricubeCampaignState, TricubeState
from .tools import TricubeCampaignTools, TricubeTools

__all__ = [
    "Affliction",
    "LLMClient",
    "TricubeCampaignState",
    "TricubeCampaignTools",
    "TricubeCharacter",
    "TricubeSession",
    "TricubeSimulation",
    "TricubeState",
    "TricubeTools",
    "compact_transcript",
    "create_tricube_monster",
    "create_tricube_player",
    "heuristic_player_turn",
    "make_tau_provider",
    "summarize_state",
]
