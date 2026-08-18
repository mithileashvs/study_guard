"""
State names and escalation-level definitions for the cat overlay.

Kept as plain string constants (matching the rest of the project's
style -- see distraction_engine.py's FOCUSED/POTENTIAL_DISTRACTION/
DISTRACTION_CONFIRMED) rather than a formal Enum, so log values and
debug prints stay human-readable without an extra .value everywhere.
"""

IDLE = "IDLE"
ENTERING = "ENTERING"
WALKING = "WALKING"
STARING = "STARING"
PEEKING = "PEEKING"
PAWING = "PAWING"
MEDIA_ACTION = "MEDIA_ACTION"
BLOCKING = "BLOCKING"
EXITING = "EXITING"
SATISFIED = "SATISFIED"
STOPPED = "STOPPED"

# Escalation levels 1-6. Each re-trigger of the cat (same distracted
# episode, after CAT_COOLDOWN_SECONDS) advances one level, capping at
# 6 and then repeating level 6's behavior rather than growing further
# -- deterministic and testable, not randomly chaotic.
#
# IMPORTANT: every level runs the SAME full choreography -- enter,
# walk, stare, paw, a real media action, an occasional annoyed/smug
# reaction, a brief wait, then exit (see cat_window.py's
# _run_level_action()/_do_media_action()). The level only changes the
# flavor of that same sequence (double-paw, a "block" prelude, which
# expression is more likely) -- it never gates whether the cat
# actually interacts. An earlier version had levels 1-2 skip straight
# to an idle hold with no paw/media step at all, which is what made
# the cat appear to get stuck doing nothing after it walked in.
LEVEL_WALK_ACROSS = 1
LEVEL_WALK_PAWPRINTS_STARE = 2
LEVEL_PAW_AT_SCREEN = 3
LEVEL_MEDIA_ACTION = 4
LEVEL_BLOCK_SCREEN = 5
LEVEL_REPEAT = 6

MAX_LEVEL = LEVEL_REPEAT


def level_for_escalation_count(count: int) -> int:
    """count is 1 for the cat's first appearance this episode, 2 for
    its second (after cooldown), etc. Clamps at MAX_LEVEL so a
    long-running distraction episode keeps repeating level 6's
    behavior instead of indexing past the defined levels."""
    return min(max(count, 1), MAX_LEVEL)
