"""
CatController -- the one object intervention_manager.py talks to.

Owns exactly one CatWindow (never creates a second one, matching
CompanionOverlay's existing rule) and exactly one escalation counter
per distracted episode. Every public method here is safe to call even
if the window failed to start, assets are missing, or a previous call
raised -- errors are caught, logged once via _WINDOW_ERROR-style
events, and the affected feature is disabled rather than propagating
up into the distraction-monitor loop (section 25 of the integration
spec: the cat must never crash Study Guard).

Primary entry point used by intervention_manager.py:

    start_intervention()   -- call each time the cat should
                               appear/escalate for the current episode
    stop_intervention()    -- call on return-to-study (or shutdown)
    shutdown()              -- full teardown when Study Guard exits

The more granular methods listed in the integration spec (enter,
walk, stop_and_stare, peek, paw, pause_action, play_action,
rewind_action, forward_action, block, annoyed, smug, satisfied, exit,
stop, reset) are also exposed below for direct/manual testing (see
main.py's --test-cat flag) and for future callers that want a single
named action rather than the full orchestrated sequence. They are
thin wrappers that ask CatWindow to jump straight to that action's
step in the same choreography start_intervention() drives -- there is
one animation engine, not two.
"""

import time

from desktop_pet.cat_window import CatWindow
from desktop_pet import cat_state as cs


class CatController:
    def __init__(self, session_id=None, log_event_fn=None, media_controller=None,
                 max_intervention_seconds=90):
        self.session_id = session_id
        self._log_event_fn = log_event_fn
        self.media_controller = media_controller
        self.window = CatWindow(
            session_id=session_id,
            log_event_fn=log_event_fn,
            media_controller=media_controller,
            max_intervention_seconds=max_intervention_seconds,
        )
        self.available = False
        self._active = False
        self._escalation_count = 0
        self._started_ok = False

    def start(self) -> bool:
        try:
            self._started_ok = self.window.start()
            self.available = self._started_ok
            print(f"[CAT] CatController.start() -> window.start()={self._started_ok}, "
                  f"window.available={self.window.available}")
        except Exception as e:
            self._started_ok = False
            self.available = False
            print(f"[CAT] CatController.start() EXCEPTION: {e!r}")
        return self._started_ok

    # ---- main entry points used by intervention_manager.py ----

    def start_intervention(self, message: str = "") -> bool:
        """Call once per cat trigger (first appearance, and every
        re-trigger after CAT_COOLDOWN_SECONDS for the same episode).
        Escalates the level automatically; returns False (and leaves
        Study Guard's notification fallback to take over) if the
        overlay isn't usable."""
        if not self.available:
            return False
        self._escalation_count += 1
        level = cs.level_for_escalation_count(self._escalation_count)
        continuing = self._active
        self._active = True
        if not continuing:
            self._log("CAT_INTERVENTION_STARTED", level=level)
        else:
            self._log("CAT_INTERVENTION_ESCALATED", level=level)
        try:
            self.window.command("start_intervention", {
                "level": level, "message": message, "continuing": continuing,
            })
            return True
        except Exception:
            self.available = False
            self._log("CAT_WINDOW_ERROR", where="start_intervention")
            return False

    def stop_intervention(self):
        """Call on return-to-study. Safe to call even if the cat was
        never actually showing."""
        if not self._active:
            return
        self._active = False
        self._escalation_count = 0
        if not self.available:
            return
        try:
            self.window.command("stop_intervention")
        except Exception:
            self.available = False
            self._log("CAT_WINDOW_ERROR", where="stop_intervention")

    def shutdown(self):
        """Called once from main.py's session teardown. Always safe,
        even if start() was never called or failed."""
        try:
            self.window.stop()
        except Exception:
            pass

    # ---- granular actions (manual/testing use -- see spec section 7) ----
    # Each jumps the running (or freshly continuing) sequence straight
    # to the named step, reusing the same level-action dispatch
    # start_intervention() drives internally.

    def _direct_level(self, level: int, message: str = ""):
        if not self.available:
            return False
        continuing = self._active
        self._active = True
        try:
            self.window.command("start_intervention", {
                "level": level, "message": message, "continuing": continuing,
            })
            return True
        except Exception:
            self.available = False
            return False

    def enter(self, direction: str = "left"):
        return self._direct_level(cs.LEVEL_WALK_ACROSS)

    def walk(self, direction: str = "left"):
        return self._direct_level(cs.LEVEL_WALK_ACROSS)

    def stop_and_stare(self):
        return self._direct_level(cs.LEVEL_WALK_PAWPRINTS_STARE)

    def peek(self, direction: str = "left"):
        return self._direct_level(cs.LEVEL_WALK_ACROSS)

    def paw(self):
        return self._direct_level(cs.LEVEL_PAW_AT_SCREEN)

    def pause_action(self):
        return self._direct_level(cs.LEVEL_MEDIA_ACTION)

    def play_action(self):
        return self._direct_level(cs.LEVEL_MEDIA_ACTION)

    def rewind_action(self):
        return self._direct_level(cs.LEVEL_MEDIA_ACTION)

    def forward_action(self):
        return self._direct_level(cs.LEVEL_MEDIA_ACTION)

    def block(self):
        return self._direct_level(cs.LEVEL_BLOCK_SCREEN)

    def annoyed(self):
        if not self.available:
            return False
        try:
            self.window.command("show_expression", {"which": "annoyed"})
            return True
        except Exception:
            self.available = False
            return False

    def smug(self):
        if not self.available:
            return False
        try:
            self.window.command("show_expression", {"which": "smug"})
            return True
        except Exception:
            self.available = False
            return False

    def satisfied(self):
        self.stop_intervention()

    def exit(self, direction: str = "left"):
        self.stop_intervention()

    def stop(self):
        self.stop_intervention()

    def reset(self):
        self._active = False
        self._escalation_count = 0
        if self.available:
            try:
                self.window.command("hard_hide")
            except Exception:
                self.available = False

    # ---- internal ----

    def _log(self, event_name, **kwargs):
        if self._log_event_fn is None or self.session_id is None:
            return
        try:
            value = ",".join(f"{k}={v}" for k, v in kwargs.items())[:200]
            self._log_event_fn(self.session_id, event_name, value=value)
        except Exception:
            pass
