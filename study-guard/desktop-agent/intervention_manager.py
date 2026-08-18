"""
Intervention manager -- the escalation backend.

    window_tracker (Day 1)
          |
    session_context.classify_window (Day 1)
          |
    distraction_engine.DistractionStateMachine (Day 1)
          |
    InterventionManager (this file)
          |
    desktop_pet.CatController  (final escalation step, once all
          |                       plain notifications are exhausted)
          v (falls back if unavailable)
    companion_overlay.CompanionOverlay
          v (falls back if unavailable)
    notifier.notify()

This module does NOT detect distraction itself and does not duplicate
Day 1's grace-period logic. It only reacts to the exact event list
already produced by DistractionStateMachine.update() each poll:

  - "DISTRACTION_STARTED"                 -> begin escalation: log
                                              DISTRACTION_DETECTED, send
                                              plain Notification #1
                                              immediately (the grace
                                              period has already been
                                              served by the Day 1 engine)
  - "DISTRACTION_ENDED"/"FOCUS_RECOVERED" -> stop escalation right away,
                                              hide the cat if it's up,
                                              log FOCUS_RECOVERED, reset
  - (still confirmed, no new event)       -> advance to the next plain
                                              notification every
                                              NOTIFICATION_INTERVAL, up
                                              to MAX_NOTIFICATIONS; once
                                              all of those have fired and
                                              the user is STILL
                                              distracted, trigger the cat
                                              (repeatable, gated by
                                              CAT_COOLDOWN_SECONDS, as
                                              long as the same episode
                                              never recovers)

Escalation flow (see config.py for the exact numbers):

    IDLE
      | DISTRACTION_STARTED
      v
    NOTIFICATION_1  --(NOTIFICATION_INTERVAL, still distracted)-->  NOTIFICATION_2
      |                                                                  |
      |                                          (NOTIFICATION_INTERVAL, still distracted)
      |                                                                  v
      |                                                            NOTIFICATION_3
      |                                                                  |
      |                                                    (still distracted next poll)
      |                                                                  v
      |                                                            CAT_INTERVENTION --(CAT_COOLDOWN_SECONDS, still distracted)--> CAT_INTERVENTION (repeat)
      |                                                                  |
      +------------------------- DISTRACTION_ENDED / FOCUS_RECOVERED, from ANY state ------------------------+
                                                       |
                                                       v
                                                     IDLE

Switching between two different DISTRACTING windows (e.g. Instagram ->
a different distracting site) does NOT reset this -- the Day 1 engine
only emits a recovery event when the window classifies as allowed/
study, so escalation naturally keeps advancing through a string of
different distractions rather than restarting at Notification #1 each
time the user flips tabs. Nothing extra is needed here for that; it
falls straight out of only reacting to the engine's own events.
"""

import time

from config import (
    COMPANION_ENABLED,
    MAX_NOTIFICATIONS,
    NOTIFICATION_INTERVAL,
    CAT_COOLDOWN_SECONDS,
)
from companion_messages import get_message
from notifier import notify
from logger import log_event

IDLE = "IDLE"
NOTIFYING = "NOTIFYING"      # notification_stage tracks which of 1..MAX_NOTIFICATIONS was last sent
CAT_PHASE = "CAT_PHASE"      # all notifications sent; cat has fired at least once this episode

# Plain desktop notifications for stages 1-3 (NOT the cat overlay --
# the cat is reserved for the final, post-notifications escalation).
_STAGE_MESSAGES = {
    1: "Hey \U0001F440 Let's get back to studying.",
    2: "Your study session is waiting \U0001F63C",
    3: "Okay... last warning. \U0001F440",
}


class InterventionManager:
    """
    One instance per session, shared by the distraction monitor thread.
    Owns exactly one CompanionOverlay (never creates a second one) and
    falls back to a plain desktop notification if the overlay is
    disabled, unavailable, or fails at runtime -- the monitoring loop
    must keep running either way.
    """

    def __init__(self, session_id: str, overlay=None, cat_controller=None):
        self.session_id = session_id
        self.overlay = overlay
        self.cat_controller = cat_controller  # desktop_pet.CatController; may be None
        self.state = IDLE
        self.notification_stage = 0   # 0..MAX_NOTIFICATIONS
        self._category = ""
        self._last_event_at = None    # last notification OR last cat trigger, depending on phase
        self._overlay_broken = False  # sticky: once the overlay breaks, stop trying it
        self._cat_broken = False      # sticky: same idea, for the cat overlay specifically

    def handle_poll(self, is_confirmed: bool, category: str, engine_events: list):
        """
        Call once per distraction_monitor poll with the SAME event list
        already returned by DistractionStateMachine.update() this cycle
        (not recomputed) -- there is exactly one source of truth for
        state transitions, and this method never has to guess at them.
        """
        started = False
        recovered = False
        for event_name, kwargs in engine_events:
            if event_name == "DISTRACTION_STARTED":
                started = True
                category = kwargs.get("category", category)
            elif event_name in ("DISTRACTION_ENDED", "FOCUS_RECOVERED"):
                recovered = True

        if recovered:
            self._recover(category)
        elif started:
            self._begin(category)
        elif is_confirmed and self.state != IDLE:
            self._continue(category)

    # ---- escalation steps ----

    def _begin(self, category: str):
        self.state = NOTIFYING
        self.notification_stage = 0
        self._category = category
        log_event(self.session_id, "DISTRACTION_DETECTED", category=category)
        self._send_notification(1, category)

    def _send_notification(self, stage: int, category: str):
        message = _STAGE_MESSAGES[stage]
        # Plain notification -- never the cat overlay. kind=None
        # deliberately bypasses notifier.py's own cooldown, since this
        # class already owns the cadence via NOTIFICATION_INTERVAL.
        notify("Study Guard", message)
        log_event(self.session_id, "NOTIFICATION_SENT", category=category, value=f"stage={stage}")
        self.notification_stage = stage
        self.state = NOTIFYING
        self._last_event_at = time.time()

    def _continue(self, category: str):
        now = time.time()
        elapsed = now - (self._last_event_at or now)

        if self.notification_stage < MAX_NOTIFICATIONS:
            if elapsed >= NOTIFICATION_INTERVAL:
                self._send_notification(self.notification_stage + 1, category)
            return

        # All MAX_NOTIFICATIONS have been sent. Trigger the cat as soon
        # as we observe the user is STILL distracted -- no extra delay
        # on top of the notification cadence for the FIRST cat trigger.
        # If the cat has already fired once this episode and the user
        # is somehow still distracted, only re-trigger after cooldown.
        print(f"[INTERVENTION] distraction detected, stage={self.notification_stage}")
        print(f"[INTERVENTION] last warning already delivered")
        cat_trigger_condition = self.state != CAT_PHASE or elapsed >= CAT_COOLDOWN_SECONDS
        print(f"[INTERVENTION] CAT_TRIGGER_CONDITION state={self.state} elapsed={elapsed:.1f}s "
              f"cooldown={CAT_COOLDOWN_SECONDS}s -> {cat_trigger_condition}")
        if cat_trigger_condition:
            print("[INTERVENTION] triggering cat intervention")
            self._trigger_cat(category)

    def _trigger_cat(self, category: str):
        message = get_message(3)  # reuse the existing "long distraction" tier verbatim

        # Escalation ladder for who actually shows something:
        #   1) the real animated cat overlay (desktop_pet.CatController)
        #   2) the plain companion speech-bubble (companion_overlay.py),
        #      if the cat window specifically is unavailable/broken
        #   3) a bare desktop notification, if neither GUI works at all
        # Each rung only fires if the one above it didn't.
        cat_controller_state = (
            f"present={self.cat_controller is not None} "
            f"available={getattr(self.cat_controller, 'available', None)} "
            f"broken={self._cat_broken} companion_enabled={COMPANION_ENABLED}"
        )
        print(f"[CAT] CAT_CONTROLLER_STATE {cat_controller_state}")

        used_cat = False
        if COMPANION_ENABLED and self.cat_controller is not None and self.cat_controller.available and not self._cat_broken:
            print("[CAT] start_intervention()")
            try:
                used_cat = self.cat_controller.start_intervention(message)
                print(f"[CAT] overlay requested -> start_intervention() returned {used_cat}")
                if used_cat:
                    print("[CAT] overlay shown")
            except Exception as e:
                self._cat_broken = True
                print(f"[CAT] EXCEPTION in start_intervention(): {e!r}")
                log_event(self.session_id, "OVERLAY_FAILURE", category=category, value="cat_controller")
        else:
            print("[CAT] skipped -- cat_controller not usable (see CAT_CONTROLLER_STATE above)")

        print(f"[INTERVENTION] CAT_TRIGGERED used_cat={used_cat}")

        if not used_cat:
            used_overlay = False
            if COMPANION_ENABLED and self.overlay is not None and self.overlay.available and not self._overlay_broken:
                try:
                    self.overlay.show(message)
                    used_overlay = True
                except Exception:
                    # Overlay misbehaved at runtime -- log it once, then
                    # fall back to plain notifications for the rest of the
                    # session rather than repeatedly retrying a broken GUI.
                    self._overlay_broken = True
                    log_event(self.session_id, "OVERLAY_FAILURE", category=category)

            if not used_overlay:
                notify("Study Guard", message)

        log_event(self.session_id, "INTERVENTION_TRIGGERED", category=category)
        self.state = CAT_PHASE
        self._last_event_at = time.time()

    def _recover(self, category: str):
        if self.state == IDLE:
            return
        if self.cat_controller is not None:
            try:
                self.cat_controller.stop_intervention()
            except Exception:
                pass
        if COMPANION_ENABLED and self.overlay is not None and self.overlay.available:
            try:
                self.overlay.hide()
            except Exception:
                pass
        log_event(self.session_id, "FOCUS_RECOVERED", category=category)
        self.state = IDLE
        self.notification_stage = 0
        self._category = ""
        self._last_event_at = None

    def shutdown(self):
        """Best-effort cleanup if the session ends mid-escalation, so
        nothing is left visibly showing after Study Guard exits."""
        if self.state != IDLE:
            self._recover(self._category)

