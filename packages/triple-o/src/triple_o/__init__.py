"""triple-o — Obvious / Option / Odd middleware for LLM creativity.

See ``src/triple_o/core.py`` (engine), ``tools.py`` (typed tools),
``middleware.py`` (Tau harness), ``spark.py`` (spark tables) and ``cli.py``.

Verified 2026-09-08 (heuristic + Tau):
  >>> triple-o demo --seed 42
  Lyra roll 2 -> option: flank via alley
  Borin roll 6 -> obvious: probe with pole
  ... group/ask + spark
"""

from .core import Category, Proposal, TripleO, TripleORoll
from .middleware import TripleOMiddleware, make_triple_o_provider
from .spark import roll_action, roll_disposition, roll_spark
from .tools import TripleOTools

__all__ = [
    "Category",
    "Proposal",
    "TripleO",
    "TripleOMiddleware",
    "TripleORoll",
    "TripleOTools",
    "make_triple_o_provider",
    "roll_action",
    "roll_disposition",
    "roll_spark",
]
