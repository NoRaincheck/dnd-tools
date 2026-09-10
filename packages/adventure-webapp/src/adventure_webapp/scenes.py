"""Scene templates — single-scene playable packs."""

from __future__ import annotations

SCENE_TEMPLATES: dict[str, dict[str, object]] = {
    "veiled-archive": {
        "scene_id": "scene-veiled-archive",
        "title": "The Veiled Archive",
        "objective": "Recover Wyldfyre from the sealed archive before the ward collapses",
        "location": "Undercity — Veiled Archive",
        "patron": "Wizard Nimdronde",
        "threat": "Collapsing wards / rival seekers",
        "segments": 6,
        "beats": [
            "Find the hidden archivist's antechamber",
            "Bypass the sigil-locked vault",
            "Outwit or evade rival seekers",
            "Claim Wyldfyre and escape before collapse",
        ],
        "cast": ["Elaria"],
    },
    "goblin-ambush": {
        "scene_id": "scene-goblin-ambush",
        "title": "Goblin Ambush",
        "objective": "Survive the ambush on the road to Tanglewood and hold the pass",
        "location": "Wilderlands — Tanglewood Road",
        "patron": "Lord Garrington",
        "threat": "Goblin raiders",
        "segments": 6,
        "beats": [
            "Spot the ambush before it closes",
            "Hold the chokepoint",
            "Drive off the war leader",
            "Secure the road",
        ],
        "cast": ["Elaria"],
    },
    "starlit-heist": {
        "scene_id": "scene-starlit-heist",
        "title": "The Starlit Heist",
        "objective": "Lift the moon-sigil from the guildhouse during the masquerade",
        "location": "Everspire — Guildhouse",
        "patron": "Lady Voss",
        "threat": "City watch + sigil wards",
        "segments": 6,
        "beats": [
            "Infiltrate the masquerade unseen",
            "Locate the moon-sigil vault",
            "Lift the sigil without triggering wards",
            "Vanish into the night",
        ],
        "cast": ["Borin"],
    },
}

DEFAULT_TEMPLATE = "veiled-archive"

# Heuristic choice seeds per beat — used when LLM unavailable.
BEAT_CHOICES: dict[str, list[dict[str, str]]] = {
    "veiled-archive": [
        {
            "obvious": "Follow the archivist's chalk marks down the service stair",
            "option": "Bribe the porter for the back ledger and pick the side door",
            "odd": "Pry open the sealed dumbwaiter and ride it down humming",
            "situation": "The antechamber is hidden somewhere beneath the library. How do you find it?",
            "position": "risky",
            "effect": "standard",
        },
        {
            "obvious": "Trace the sigils methodically and dispel the key glyph",
            "option": "Jam the mechanism with iron shavings and force the lock",
            "odd": "Mimic the old archivist's oath aloud to trick the ward",
            "situation": "The vault door thrums with a sigil-lock, counting down to reseal.",
            "position": "risky",
            "effect": "standard",
        },
        {
            "obvious": "Slip behind the shelves and let rivals pass",
            "option": "Bargain — offer rivals a share of lesser tomes",
            "odd": "Topple a stack to block the lane and sprint through dust",
            "situation": "Rival seekers sweep the aisle with lanterns. You hear boots.",
            "position": "desperate",
            "effect": "standard",
        },
        {
            "obvious": "Seize Wyldfyre with the ward-cloth and brace for collapse",
            "option": "Anchor a rope to the balustrade and swing to the prize",
            "odd": "Whisper Wyldfyre's name and beckon — let it come to you",
            "situation": "Wyldfyre flares on the pedestal as stone shudders. The ward is failing.",
            "position": "desperate",
            "effect": "great",
        },
    ],
    "goblin-ambush": [
        {
            "obvious": "Drop low and flank through bracken to spot the trap",
            "option": "Hurl a stone to spring the snare early",
            "odd": "Stride openly, daring them to reveal themselves",
            "situation": "The road narrows — birds have gone silent. The ambush is near.",
            "position": "risky",
            "effect": "standard",
        },
        {
            "obvious": "Plant feet at the chokepoint and hold with shield",
            "option": "Topple the cart to bar the pass",
            "odd": "Charge the treeline screaming to scatter them",
            "situation": "Goblins spill from cover. The pass will be lost unless held.",
            "position": "risky",
            "effect": "standard",
        },
        {
            "obvious": "Challenge the war leader blade to blade",
            "option": "Loose an arrow for the leader's knee and break morale",
            "odd": "Offer single combat — stakes: the road",
            "situation": "A hulking goblin chief bangs drum and blade. Break him and they rout.",
            "position": "desperate",
            "effect": "standard",
        },
        {
            "obvious": "Dress the wounded and fortify the pass",
            "option": "Pursue stragglers into the woods",
            "odd": "Light the tar barrel and signal Tanglewood from the ridge",
            "situation": "The raiders waver. How do you seal the victory?",
            "position": "risky",
            "effect": "limited",
        },
    ],
    "starlit-heist": [
        {
            "obvious": "Borrow a mask at the door and slip with the crowd",
            "option": "Pose as entertainer and be waved past the watch",
            "odd": "Scale the ivy to the balcony mid-toasts",
            "situation": "The masquerade doors are watched. How do you enter?",
            "position": "risky",
            "effect": "standard",
        },
        {
            "obvious": "Track footfalls to the vault — servants know the quiet stairs",
            "option": "Lift a steward's keyring at the fountain",
            "odd": "Follow the cats — they always know the warm vault",
            "situation": "The guildhouse is a maze. The sigil could be anywhere.",
            "position": "risky",
            "effect": "standard",
        },
        {
            "obvious": "Breathe, read the ward threads, pluck them in sequence",
            "option": "Flood the ward with moonlight via the skylight",
            "odd": "Offer a drop of blood — old pacts open old locks",
            "situation": "The moon-sigil hangs in a lattice of light. One twitch triggers the alarm.",
            "position": "desperate",
            "effect": "great",
        },
        {
            "obvious": "Melt into departing guests with sigil against your chest",
            "option": "Swap sigil with a gilded forgery and stroll out",
            "odd": "Toss sigil from window to your accomplice and vault after",
            "situation": "Guards turn. You have seconds before the absence is noticed.",
            "position": "desperate",
            "effect": "standard",
        },
    ],
}
