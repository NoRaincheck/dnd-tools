"""dnd_campaign — long-horizon campaign layer (isolated from dnd_tools paper impl).

This package wraps `dnd_tools` without modifying it. All state mutations go through
the authoritative `dnd_tools.state.GameState`; this layer adds snapshots,
persistence, rests, and context pruning for 50-100+ turn play.
"""

from .memory import compact_transcript, summarize_state
from .session import CampaignSession
from .state import CampaignState
from .tools import CampaignTools

__all__ = ["CampaignSession", "CampaignState", "CampaignTools", "compact_transcript", "summarize_state"]
