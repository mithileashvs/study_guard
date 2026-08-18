"""
AI Study Coach -- logic behind the floating robot mascot on the
Overview page.

This module owns exactly two things:

  1. build_context(...)     -- packages the REAL, already-computed
                                Study Guard state (posture, presence,
                                distraction counts, elapsed time, cat
                                intervention history, health score)
                                into one small dict. It reads nothing
                                from disk itself and runs no detection
                                of its own -- every value it uses is
                                passed in by dashboard.py, which already
                                derived it from live_status.read_status()
                                and session_log.csv the same way the
                                rest of the dashboard does. No posture,
                                presence, or distraction number is
                                invented here.

  2. reply_to(...)           -- turns a quick-action key or free-typed
                                message, plus that same context, into
                                the robot's reply text.

INTEGRATION BOUNDARY -- swapping in a real AI backend
---------------------------------------------------------------------
reply_to() currently answers with a small local rule engine
(_LOCAL_REPLIES / _rule_based_reply below) so the Coach panel is fully
functional out of the box with zero external dependencies. When a real
AI backend (an LLM API call, a hosted assistant, etc.) is ready to be
wired in, it only needs to change ONE thing: replace the body of
reply_to() with a call to that backend, passing it `context` as
grounding data so it can't invent numbers either. Nothing in
dashboard.py needs to change -- it only ever calls reply_to(text,
context) and displays whatever string comes back. For example:

    def reply_to(user_text, context, action_key=None):
        return call_my_ai_backend(user_text, context=context, action_key=action_key)

No other function in this file, and no caller in dashboard.py, needs
to know whether the reply came from the local rule engine or a real
model.
"""

from __future__ import annotations

# ----------------------------------------------------------------------
# Quick actions shown as chips in the Coach panel. (key, icon, label)
# ----------------------------------------------------------------------
QUICK_ACTIONS = [
    ("focus", "\u26A1", "Help me focus"),
    ("motivate", "\U0001F525", "Motivate me"),
    ("method", "\U0001F4DA", "Study method"),
    ("distracted", "\U0001F635", "I'm distracted"),
    ("plan", "\u23F1\uFE0F", "Plan my session"),
    ("explain", "\U0001F4CA", "Explain my session"),
]


def build_context(
    *,
    running: bool,
    posture_state: str,
    presence_state: str,
    distraction_active: bool,
    distraction_events: int,
    slouch_events: int,
    elapsed_seconds: float | None,
    cat_intervened: bool,
    subject: str,
    study_mode: str,
    break_interval_seconds: int,
    score: dict | None,
) -> dict:
    """Bundles already-derived real state into one dict. Pure data
    plumbing -- no thresholds, no detection, no new state machine."""
    return {
        "running": running,
        "posture_state": posture_state,
        "presence_state": presence_state,
        "distraction_active": distraction_active,
        "distraction_events": distraction_events,
        "slouch_events": slouch_events,
        "elapsed_seconds": elapsed_seconds or 0,
        "cat_intervened": cat_intervened,
        "subject": subject,
        "study_mode": study_mode,
        "break_interval_seconds": break_interval_seconds,
        "score": score,
    }


def _fmt_duration(seconds: float) -> str:
    seconds = int(max(seconds, 0))
    h, rem = divmod(seconds, 3600)
    m, _ = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"


# ----------------------------------------------------------------------
# Proactive message -- what the robot shows next to itself (speech
# bubble) or opens the panel with, WITHOUT the user clicking anything.
# Priority-ordered so only the single most relevant thing is said --
# this is the "don't spam" rule: one message reflecting current real
# state, not a running feed of everything that's happened.
# ----------------------------------------------------------------------
def get_proactive_message(context: dict) -> tuple[str, str, bool]:
    """
    Returns (message, mood, should_show_bubble).

    mood is one of "good" | "warn" | "bad" | "neutral", used only for
    a subtle color accent -- purely cosmetic, no new state.

    should_show_bubble is False for the unremarkable "everything's
    fine" case, so the mascot stays a quiet, unobtrusive icon exactly
    when there's nothing worth interrupting the user for.
    """
    if not context["running"]:
        return ("Start a session and I'll help you stay on track.", "neutral", False)

    if context["cat_intervened"] and context["distraction_active"]:
        return (
            "Okay... the cat already had to intervene \U0001F62D\nLet's get back to work.",
            "bad",
            True,
        )

    if context["distraction_active"] and context["distraction_events"] >= 3:
        return (
            "You're getting pulled away again. Want a quick focus reset?",
            "bad",
            True,
        )

    if context["distraction_active"]:
        return ("Looks like you got distracted. Ready to refocus?", "warn", True)

    if context["posture_state"] == "SLOUCH":
        return ("Hey, straighten up a little \U0001F642", "warn", True)

    if context["posture_state"] == "SLIGHT_SLOUCH":
        return ("Try sitting up a bit straighter.", "warn", True)

    if context["presence_state"] == "AWAY":
        return ("Take your time -- I'll be here when you're back.", "neutral", True)

    if (
        context["posture_state"] == "GOOD"
        and context["elapsed_seconds"] >= context["break_interval_seconds"]
    ):
        return ("Nice focus streak! A short planned break might help.", "good", True)

    if context["posture_state"] == "GOOD":
        return ("You're doing great. Keep going!", "good", False)

    return ("I'm here if you need a hand.", "neutral", False)


def greeting_message(context: dict) -> str:
    """The first bubble shown when the panel is opened -- a short,
    real-data summary in the same voice as the reference mockup
    ("You had 2 distractions this session...")."""
    if not context["running"]:
        return "Hey! No session is running right now -- start Study Guard and I'll keep you company."

    n = context["distraction_events"]
    distraction_bit = (
        f" You've had {n} distraction{'s' if n != 1 else ''} this session."
        if n
        else " No distractions so far -- nice."
    )
    return f"Hey! You're doing well.{distraction_bit} Want a quick focus strategy?"


# ----------------------------------------------------------------------
# Quick-action / free-text replies (local rule engine -- see the
# INTEGRATION BOUNDARY note at the top of this file).
# ----------------------------------------------------------------------
def _rule_based_reply(action_key: str | None, user_text: str, context: dict) -> str:
    if action_key == "focus":
        if context["distraction_active"] or context["distraction_events"] > 0:
            return (
                f"You've had {context['distraction_events']} distraction"
                f"{'s' if context['distraction_events'] != 1 else ''} so far. "
                "Try closing anything not related to this session, silence notifications, "
                "and set a single small goal for the next 10 minutes."
            )
        return "You're on track. Pick one concrete task for the next block and start a short timer for it."

    if action_key == "motivate":
        studied = _fmt_duration(context["elapsed_seconds"])
        return f"You've already put in {studied} today -- that adds up. Keep the streak going, one focused block at a time \U0001F4AA"

    if action_key == "method":
        return (
            "A couple that work well for most people: the Pomodoro technique "
            "(25 min focus / 5 min break), and active recall -- close your notes and "
            "try to explain the topic out loud before re-reading it."
        )

    if action_key == "distracted":
        return (
            "That happens. Try this: name the distraction, close it, take one slow breath, "
            "then go back to the exact sentence or problem you left off on."
        )

    if action_key == "plan":
        subject = context["subject"] or "your subject"
        mode = (context["study_mode"] or "Balanced").title()
        return (
            f"For {subject} in {mode} mode, try blocking 25-40 minutes of focused work, "
            "then a short break. Want me to remind you about posture and breaks as you go?"
        )

    if action_key == "explain":
        score = context.get("score")
        if not score:
            return "Not enough data yet to score this session -- keep going a little longer and check back."
        return (
            f"Session health is {score['overall']}% right now -- "
            f"Focus {score['focus']}%, Posture {score['posture']}%, "
            f"Presence {score['presence']}%, Distractions {score['distractions']}%. "
            f"You've logged {context['slouch_events']} posture warning"
            f"{'s' if context['slouch_events'] != 1 else ''} and "
            f"{context['distraction_events']} distraction"
            f"{'s' if context['distraction_events'] != 1 else ''} so far."
        )

    # Free-typed message, no quick-action key -- the local engine can't
    # have a real conversation, so it's upfront about that and still
    # grounds its one tip in real state rather than inventing a reply.
    msg, _, _ = get_proactive_message(context)
    return (
        "I can't have a full conversation yet -- that needs an AI backend that "
        f"isn't connected. Here's what I can tell from your session right now: {msg}"
    )


def reply_to(user_text: str, context: dict, action_key: str | None = None) -> str:
    """Single entry point dashboard.py calls for every Coach reply,
    whether triggered by a quick-action chip or free text. See the
    INTEGRATION BOUNDARY note at the top of this file to swap this for
    a real AI backend later."""
    return _rule_based_reply(action_key, user_text, context)
