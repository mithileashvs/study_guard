"""
Stateful distraction detection.

The old approach fired a fresh log event every polling cycle for as
long as a distracting window stayed active. This turns that into an
explicit state machine so one distraction *episode* produces exactly
one DISTRACTION_STARTED and one DISTRACTION_ENDED/FOCUS_RECOVERED
pair, no matter how many polls it spans.

    FOCUSED --(distraction seen)--> POTENTIAL_DISTRACTION
    POTENTIAL_DISTRACTION --(still distracted past grace period)--> DISTRACTION_CONFIRMED
    POTENTIAL_DISTRACTION --(back to focus before grace period)--> FOCUSED   (silent -- just a glance)
    DISTRACTION_CONFIRMED --(back to focus)--> FOCUSED  (logs DISTRACTION_ENDED + FOCUS_RECOVERED)
"""

import time

FOCUSED = "FOCUSED"
POTENTIAL_DISTRACTION = "POTENTIAL_DISTRACTION"
DISTRACTION_CONFIRMED = "DISTRACTION_CONFIRMED"


class DistractionStateMachine:
    """
    Call update(is_distraction_now, label) once per poll. Returns a
    list of (event_name, kwargs) tuples to log -- usually empty, since
    most polls don't cross a state boundary.
    """

    def __init__(self, grace_period: int):
        self.grace_period = grace_period
        self.state = FOCUSED
        self._started_at = None
        self._label = ""

    @property
    def is_confirmed(self) -> bool:
        return self.state == DISTRACTION_CONFIRMED

    def update(self, is_distraction_now: bool, label: str):
        events = []
        now = time.time()

        if is_distraction_now:
            if self.state == FOCUSED:
                self.state = POTENTIAL_DISTRACTION
                self._started_at = now
                self._label = label

            elapsed = now - self._started_at
            if self.state == POTENTIAL_DISTRACTION and elapsed >= self.grace_period:
                self.state = DISTRACTION_CONFIRMED
                events.append(("DISTRACTION_STARTED", {"category": self._label}))
        else:
            if self.state == DISTRACTION_CONFIRMED:
                duration = now - self._started_at
                events.append(("DISTRACTION_ENDED", {
                    "category": self._label,
                    "duration": f"{duration:.0f}",
                }))
                events.append(("FOCUS_RECOVERED", {"category": label}))
            # POTENTIAL_DISTRACTION -> FOCUSED before the grace period
            # elapsed is a non-event: just a brief glance, nothing to log.
            self.state = FOCUSED
            self._started_at = None
            self._label = ""

        return events

    def close(self):
        """
        Call on shutdown if a distraction was mid-episode (confirmed)
        when the session ended, so the episode isn't left open forever
        in the log. Returns the same kind of event list as update().
        """
        if self.state == DISTRACTION_CONFIRMED:
            duration = time.time() - self._started_at
            events = [("DISTRACTION_ENDED", {
                "category": self._label,
                "duration": f"{duration:.0f}",
                "value": "session_end",
            })]
            self.state = FOCUSED
            self._started_at = None
            self._label = ""
            return events
        return []
