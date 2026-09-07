"""triple-o — Obvious / Option / Odd middleware for LLM creativity.

See ``src/triple_o/core.py`` (engine), ``tools.py`` (typed tools),
``middleware.py`` (Tau harness), ``spark.py`` (spark tables) and ``cli.py``.

Verified 2026-09-08 (LMStudio :1234, qwen3.6-35b-a3b-mtp + tiel-coder-35b-a3b-mtp via tau-ai/tau_agent):

>>> triple-o demo --seed 42 --use-llm --model qwen3.6-35b-a3b-mtp
--- Lyra ---
Situation: Goblin horde blocks the gate; party must breach
Chosen: {'character': 'Lyra', 'situation': 'Goblin horde blocks the gate; party must breach', 'traits': ['keen eye', 'reckless'], 'roll': 1, 'rolls': [1], 'category': 'odd', 'choice': 'Feign surrender or stumble forward to get close, then unleash a surprise attack.', 'proposal': {'obvious': 'Charge straight into the fray...', 'option': 'Scan the perimeter...', 'odd': 'Feign surrender...'}}
Narration: I drop my weapon and stumble forward with a pitiful cry, playing the part of a broken surrenderer to slip past their front line. Once I'm within striking distance, my erratic desperation turns to cold vengeance as I spring back to my feet and drive my blade into the nearest goblin.
--- Borin ---
Situation: A trapped corridor hisses — do they search for traps?
Chosen: {'roll': 2, 'category': 'option', 'choice': "I'll throw a rock down the hall first to trigger any mechanisms before stepping in."}
Narration: Borin snatches a loose stone from the corridor wall and hurls it deep into the hissing darkness...
--- Group ['brave', 'cautious', 'reckless'] ---
Roll 6 (obvious) → hold position
Tool traces: 7 — deterministic seed 42 (LLM correctly invoked propose_triple_o → roll_triple_o, odd/option/obvious)

>>> triple-o demo --seed 42 --use-llm --model tiel-coder-35b-a3b-mtp
Lyra roll 1 → odd: Crawl low to investigate ... drain grate ...
Borin roll 2 → option: pause to scan floor/walls for pressure plates...
Narration: The die lands on 1 — Odd. Lyra drops low and scours the base of the gate...
Tool traces: 7 — same seeded categories across models, different prose per branch

Heuristic (no LLM): triple-o demo --seed 42
Lyra roll 6 → obvious: snipe from rooftop | Borin 6 obvious | Mira 2 option; group 6 obvious; Q odd(1) No/rush in
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
