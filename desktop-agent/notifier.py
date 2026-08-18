"""
Thin wrapper around desktop notifications so the rest of the code
doesn't need to know or care which backend is used. Falls back to
printing to the console if plyer/notifications aren't available
(e.g. running inside some IDEs or restricted environments).

BUGFIX (posture messages silently not appearing): `from plyer import
notification` succeeding at import time does NOT mean an actual
notification will succeed at call time. plyer resolves its real OS
backend (e.g. plyer.platforms.win.notification.WindowsNotification on
Windows) lazily, the first time .notify() is actually called -- and
that backend import can itself fail for reasons that have nothing to
do with plyer being "installed" (e.g. the Windows backend needs
pywin32, which is a separate package plyer does not force-install and
which was missing from requirements.txt; see the fix there too).
Previously that failure was caught by a bare `except Exception: pass`
and silently fell through to a plain `print()` -- which is invisible
if Study Guard isn't launched from a console the user is watching
(e.g. a double-clicked shortcut / pythonw). The tracker, the
threshold, and the trigger were never the problem; the notifier was
failing at the very last step without telling anyone.

Fixed by:
  1. Logging every attempt/outcome with the [NOTIFIER] tag requested
     in the integration spec, so the failure (if any) is visible in
     the same console output posture_tracker's [POSTURE] logs use.
  2. Never silently losing a notification: if plyer's real send
     fails OR isn't available, the console-print fallback always
     fires (not just when plyer was never importable), so the message
     is never simply dropped.
"""

import time
from config import APP_NAME, NOTIFICATION_COOLDOWN

try:
    from plyer import notification as _plyer_notification
    _HAS_PLYER = True
except Exception:
    _plyer_notification = None
    _HAS_PLYER = False
    print("[NOTIFIER] plyer not importable -- falling back to console notifications only")

# Tracks the last time each notification "kind" fired, so a state that
# stays true (e.g. still slouching) doesn't spam a notification every
# loop iteration. Keyed by an arbitrary string the caller chooses.
_last_fired = {}


def notify(title: str, message: str, kind: str = None):
    """
    Sends a desktop notification (falls back to console print if the
    OS backend is unavailable or errors). If `kind` is given, this
    notification type is rate-limited to once per NOTIFICATION_COOLDOWN
    seconds -- pass a stable string like "slouch" or "distraction" to
    avoid spam.
    """
    if kind is not None:
        now = time.time()
        last = _last_fired.get(kind, 0)
        if now - last < NOTIFICATION_COOLDOWN:
            print(f"[NOTIFIER] Suppressed '{kind}' notification (cooldown "
                  f"{NOTIFICATION_COOLDOWN}s, {now - last:.1f}s since last)")
            return
        _last_fired[kind] = now

    print(f"[NOTIFIER] Sending {'' if kind is None else kind + ' '}notification: {title} - {message}")

    sent_natively = False
    if _HAS_PLYER:
        try:
            _plyer_notification.notify(
                title=f"{APP_NAME} - {title}",
                message=message,
                app_name=APP_NAME,
                timeout=6,
            )
            sent_natively = True
        except Exception as e:
            # This is the exact failure that was previously silent.
            # Surface it clearly instead of swallowing it -- the
            # console fallback below still guarantees the user sees
            # *something*, but now we also know WHY the native
            # notification didn't show.
            print(f"[NOTIFIER] Native notification backend failed ({e!r}); "
                  f"falling back to console")

    # Always print the console fallback line when the native send
    # didn't actually succeed -- previously this only ran when plyer
    # was unavailable at import time, so a call-time failure (the
    # common real-world case) produced NO visible output at all.
    if not sent_natively:
        print(f"[{APP_NAME}] {title}: {message}")
    print("[NOTIFIER] Notification sent" if sent_natively else "[NOTIFIER] Notification sent (console fallback)")
