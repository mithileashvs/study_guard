"""
Dialogue for the cat companion, kept separate from companion_overlay.py
so the messages can be tweaked without touching any GUI code.

Three tiers, though only tier 3 is used by the cat overlay itself now
(tiers 1-2 exist for compatibility/reuse and possible future use):
  1 -- light and playful
  2 -- a bit more pointed
  3 -- reserved for the cat's final/only message: this is the tier the
       cat overlay uses (see intervention_manager.py), shown only
       after Notification #1, #2, and #3 (plain desktop notifications,
       NOT this module) have all already fired and the user is still
       distracted.

Kept short and non-judgmental by design -- playful, never insulting,
threatening, or sarcastic in a mean way (see Day 2 tone rules).
"""

import random

MESSAGES = {
    1: [
        "Hey... you're supposed to be studying. \U0001F440",
        "Back to work?",
        "Focus time. \U0001F431",
        "Your study session is waiting.",
    ],
    2: [
        "Again?",
        "Seriously? \U0001F611",
        "That looks suspiciously like procrastination.",
        "Your notes are getting lonely.",
    ],
    3: [
        "Bro... we need to talk.",
        "Your study session is not going to finish itself.",
        "Okay, that's enough. Back to studying. \U0001F62D",
    ],
}


def get_message(level: int) -> str:
    """Returns a random message for the given intervention level (1-3).
    Falls back to level 1 for any out-of-range level, so a bad call
    site never crashes the intervention flow."""
    tier = MESSAGES.get(level, MESSAGES[1])
    return random.choice(tier)
