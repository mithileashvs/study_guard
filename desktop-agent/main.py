"""
Study Guard -- entry point.

Runs two monitors side by side:
  1. Distraction monitor: watches the active window title and alerts
     you if you've been off-task too long.
  2. Posture/presence monitor: watches your webcam to detect slouching,
     absence, and reminds you to take breaks.

Both monitors write into a small shared SessionStats object (protected
by a lock) which tracks how much time was spent focused, distracted,
away, and on break. That's the "session engine" the rest of the app
(logger, dashboard, health score) is built on.

Run:
    python main.py

Press Ctrl+C to stop -- shutdown is handled cleanly (camera released,
threads stopped, session totals saved) via try/finally.
"""
import desktop_pet.cat_animation as _ca_check
print(f"[DEBUG] cat_animation loaded from: {_ca_check.__file__}")
import threading
import time
import traceback
import cv2

from config import (
    WINDOW_CHECK_INTERVAL,
    POSTURE_CHECK_INTERVAL,
    CAMERA_INDEX,
    AWAY_TIMEOUT,
    BREAK_INTERVAL,
    BREAK_DURATION,
    COMPANION_ENABLED,
    INTERVENTION_DISPLAY_SECONDS,
    POSTURE_DEBUG_MODE,
    CAT_MAX_INTERVENTION_SECONDS,
    MEDIA_INTERFERENCE_ENABLED,
)
from window_tracker import get_active_window_title, get_app_label
from posture_tracker import PostureTracker, GOOD, SLIGHT_SLOUCH, SLOUCH, AWAY, UNKNOWN
from notifier import notify
from logger import log_event, new_session_id
from live_status import write_status, clear_status, write_frame, clear_frame
from session_context import prompt_for_session, create_session, classify_window, sync_roadmap_keywords, StudySession
from distraction_engine import DistractionStateMachine
from roadmap_bridge import get_active_topic_keywords
from runtime_settings import get_settings as get_runtime_settings
from intervention_manager import InterventionManager
from companion_overlay import CompanionOverlay
from desktop_pet import CatController
from media_control import MediaController
import session_bridge

_stop_event = threading.Event()
_lock = threading.Lock()

# Pause flag for the CURRENT session's monitor threads -- separate
# from _stop_event (which ends the session entirely). While set, the
# distraction/posture monitor loops keep their threads alive (webcam
# stays open, calibration baseline stays intact) but stop ticking
# stats and stop evaluating distraction/posture state, so pausing
# never resets calibration and never counts paused time into any
# bucket. Recreated per-session by SessionRuntime, same as _stop_event
# conceptually would be if it weren't shared/module-level for
# backward compatibility with run_overlay_test()/run_cat_test().
_pause_event = threading.Event()

# How often (seconds) the live status snapshot is written for the
# dashboard. Independent of the monitors' own poll intervals.
STATUS_WRITE_INTERVAL = 1

# PERF: camera CAPTURE cadence, decoupled from POSTURE_CHECK_INTERVAL
# (the heavy pose/face-detection cadence). cap.read() needs to be
# called often -- OpenCV/webcam drivers buffer frames internally, so
# only calling read() once every POSTURE_CHECK_INTERVAL seconds (the
# old behavior) meant every read returned a stale, buffered frame,
# which is exactly what showed up as camera "lag". Capturing (and
# publishing a preview frame) at this cadence keeps the feed live and
# responsive while the expensive Haar-cascade work below still only
# runs once per POSTURE_CHECK_INTERVAL.
CAMERA_CAPTURE_INTERVAL = 0.1

# Local web API / frontend address (see api_server.py). Loopback-only
# by default -- this never needs to be reachable off the machine.
API_HOST = "127.0.0.1"
API_PORT = 8000


def _notify_async(*args, **kwargs):
    """Fire-and-forget wrapper around notifier.notify() so a slow OS
    notification backend (plyer's native call can block for a
    noticeable fraction of a second) never stalls the camera capture
    loop that calls it. notify() already rate-limits itself per
    `kind`, so this just keeps the (already infrequent) call off the
    capture thread's critical path."""
    threading.Thread(target=notify, args=args, kwargs=kwargs, daemon=True).start()


class SessionStats:
    """
    Shared, lock-protected running totals for the session. Both
    threads update this; main() and a clean shutdown read from it.
    Kept intentionally simple -- plain counters, no persistence logic
    here (that's logger.py's job).
    """

    def __init__(self, session_id: str, session: StudySession):
        self.session_id = session_id
        self.session = session  # study context: subject/mode/allowed apps
        self.start_time = time.time()
        self.focus_seconds = 0.0
        self.distraction_seconds = 0.0
        self.away_seconds = 0.0
        self.break_seconds = 0.0
        self.slouch_events = 0
        self.distraction_events = 0
        self.on_break = False
        self._last_tick = time.time()

        # --- Current state, for the live dashboard only. Not part of
        # the scoring/session-totals logic above -- just a snapshot of
        # "what's true right now", refreshed by the two monitor loops
        # and periodically flushed to disk by the status_writer loop. ---
        self.presence_state = "PRESENT"       # PRESENT | AWAY
        self.posture_state = UNKNOWN          # GOOD | SLIGHT_SLOUCH | SLOUCH | AWAY | UNKNOWN
        self.distraction_active = False
        self.current_app_label = ""           # short label only, e.g. "VS Code" -- never the raw title
        self.calibrated = False
        self.duration_seconds = None          # planned session length, set by SessionRuntime (Live Session UI)

    def tick(self, bucket: str):
        """Adds elapsed time since the last tick into the given bucket
        (one of: focus, distraction, away, break). No-ops while the
        session is paused -- _last_tick is still refreshed so the
        elapsed-time gap the pause itself created is never retro-
        actively added to any bucket once resumed."""
        now = time.time()
        elapsed = now - self._last_tick
        self._last_tick = now
        if elapsed <= 0 or _pause_event.is_set():
            return
        with _lock:
            if bucket == "focus":
                self.focus_seconds += elapsed
            elif bucket == "distraction":
                self.distraction_seconds += elapsed
            elif bucket == "away":
                self.away_seconds += elapsed
            elif bucket == "break":
                self.break_seconds += elapsed


def _sync_runtime_settings(session: StudySession) -> None:
    """Folds allowed-sites/apps and extra study keywords set from the
    web Settings page into the live session, in place. Mirrors
    sync_roadmap_keywords()'s additive/idempotent approach: only ever
    adds to session.allowed_apps / session.study_keywords, never
    removes what the session started with, so a stale or cleared
    runtime_settings.json can't silently take away access mid-session.
    Cheap (one small local JSON read), safe to call every poll.
    """
    from config import ALLOWED_APP_ALIASES

    settings = get_runtime_settings()

    new_apps = settings.get("allowed_apps", [])
    if new_apps:
        existing = set(session.allowed_apps)
        for a in new_apps:
            a_lower = a.strip().lower()
            if not a_lower:
                continue
            for variant in ALLOWED_APP_ALIASES.get(a_lower, [a_lower]):
                if variant not in existing:
                    session.allowed_apps.append(variant)
                    existing.add(variant)

    new_keywords = settings.get("study_keywords", [])
    if new_keywords:
        existing_kw = set(session.study_keywords)
        additions = [k.strip().lower() for k in new_keywords if k.strip().lower() not in existing_kw]
        if additions:
            session.study_keywords = sorted(existing_kw.union(additions))


def distraction_monitor(stats: SessionStats, intervention: InterventionManager):
    """
    Background loop: polls the active window every WINDOW_CHECK_INTERVAL
    seconds and classifies it against the current study session
    (session_context.classify_window) instead of a flat keyword check --
    e.g. YouTube is only a distraction if the title doesn't look
    study-related. A DistractionStateMachine turns sustained distraction
    into exactly one DISTRACTION_STARTED / DISTRACTION_ENDED +
    FOCUS_RECOVERED pair per episode (not one event per poll). Only the
    matched category/app label is ever logged, never the raw window title.

    The same event list produced by the state machine each poll is
    handed to the InterventionManager (Day 2) -- it reacts to those
    events rather than re-deriving distraction state on its own.
    """
    engine = DistractionStateMachine(stats.session.grace_period)

    while not _stop_event.is_set():
        if _pause_event.is_set():
            # Paused: don't evaluate window/distraction state at all --
            # the DistractionStateMachine's own timers stay frozen in
            # place (grace period / escalation) rather than continuing
            # to run against a paused session, and no new events fire
            # while paused. Nothing to clean up on resume; this simply
            # picks back up exactly where it left off.
            time.sleep(0.2)
            continue

        # Cheap, local, no-network sync of the Learning Roadmap's
        # current topic into this session's study keywords -- see
        # roadmap_bridge.py. A no-op (empty list) whenever there's no
        # active roadmap, so behavior is unchanged unless the roadmap
        # feature is actually in use.
        sync_roadmap_keywords(stats.session, get_active_topic_keywords())

        # Same idea, for settings pushed from the web frontend's
        # Settings page (see runtime_settings.py / api_server.py).
        # Additive and idempotent, same as sync_roadmap_keywords --
        # never removes anything the session started with, only adds
        # what the user has added from the UI so far.
        _sync_runtime_settings(stats.session)

        title = get_active_window_title()
        result = classify_window(title, stats.session)
        stats.current_app_label = get_app_label(title)

        events = engine.update(result.is_distraction, result.label)

        for event_name, kwargs in events:
            if event_name == "DISTRACTION_STARTED":
                stats.distraction_events += 1
            if event_name == "FOCUS_RECOVERED":
                # Intentionally NOT logged here anymore -- InterventionManager
                # now owns "FOCUS_RECOVERED" exclusively (it needs the exact
                # same transition to reset its own notification/cat escalation
                # state below), so logging it here too would write two
                # FOCUS_RECOVERED rows for the same moment. DISTRACTION_STARTED
                # and DISTRACTION_ENDED are unrelated event names and are still
                # logged directly here -- scoring.py and dashboard.py's
                # timeline both still depend on those two.
                continue
            log_event(stats.session_id, event_name, **kwargs)

        # Day 2: the InterventionManager owns HOW the user gets alerted
        # (playful companion, or a plain notification fallback) -- the
        # old direct "Focus Reminder" notify() call here was replaced so
        # the user isn't hit with both a boring notification AND the cat
        # for the same event. Posture keeps using notify() directly
        # (see posture_monitor below); distraction does not.
        intervention.handle_poll(engine.is_confirmed, result.label, events)

        # Only count time toward "distraction" once the grace period has
        # actually been exceeded (state == DISTRACTION_CONFIRMED) --
        # short glances and the grace-period window itself stay "focus".
        stats.tick("distraction" if engine.is_confirmed else "focus")
        stats.distraction_active = engine.is_confirmed

        time.sleep(WINDOW_CHECK_INTERVAL)

    # Session ended mid-distraction: close the open episode so it isn't
    # left dangling in the log, and make sure the companion isn't left
    # visible after the app exits.
    for event_name, kwargs in engine.close():
        log_event(stats.session_id, event_name, **kwargs)
    intervention.shutdown()


def posture_monitor(stats: SessionStats):
    """
    Background loop: uses the webcam to track posture and presence as
    explicit state machines, and handles break reminders.

    Presence is a strict PRESENT -> AWAY -> RETURNED transition -- each
    transition is logged exactly once, not repeatedly while the state
    holds (that was the bug in the original version).
    """
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("Webcam unavailable.\nPosture monitoring disabled.")
        log_event(stats.session_id, "WEBCAM_UNAVAILABLE")
        clear_frame()
        return

    tracker = PostureTracker()

    print("Calibrating posture...")
    print("Sit normally and look at the camera.")
    session_bridge.publish_state(phase=session_bridge.PHASE_CALIBRATING, calibration_progress=0.0)
    calibrated = False
    calibration_attempts = 0
    # Attempts ceiling generous enough for ~10s of calibration even at
    # a slow camera-init cadence (0.2s/attempt = up to 20s of tries),
    # matching the required 5-10s target under normal conditions where
    # most attempts succeed rather than every attempt needing a retry.
    while not calibrated and calibration_attempts < 100 and not _stop_event.is_set():
        ret, frame = cap.read()
        if ret:
            calibrated = tracker.calibrate(frame)
            # Same frame already read for calibration -- just also save
            # it for the dashboard, so Live Camera shows real video
            # from the moment monitoring starts instead of waiting for
            # calibration to finish.
            write_frame(frame)
            session_bridge.publish_state(calibration_progress=tracker.calibration_progress)
        calibration_attempts += 1
        time.sleep(0.2)

    if calibrated:
        print("Baseline established.")
        log_event(stats.session_id, "CALIBRATION", value="success")
        stats.calibrated = True
        session_bridge.publish_state(calibration_progress=1.0)
    else:
        print("Could not calibrate (no person detected) -- posture checks will be limited.")
        log_event(stats.session_id, "CALIBRATION", value="failed")
        session_bridge.publish_state(calibration_progress=1.0)

    # Presence state machine: PRESENT / AWAY. RETURNED is a one-off
    # event logged at the moment of transition back, not a resting state.
    presence_state = "PRESENT"
    away_started_at = None

    # Posture ALERT state machine (separate from the raw GOOD/SLIGHT/
    # SLOUCH/AWAY/UNKNOWN reading above): tracks whether we're
    # currently "in" a slouch episode, so a warning/log fires once on
    # the transition into it and once on recovery -- not every poll
    # for as long as the slouch continues. (BUGFIX: the previous
    # version logged a new SLOUCH row to session_log.csv on every
    # single poll while SLOUCH/SLIGHT_SLOUCH held, which could mean
    # dozens of duplicate rows for one continuous slouch.)
    posture_alert_state = "NONE"  # NONE | SLIGHT | FULL
    bad_posture_started_at = None  # wall-clock start of the current SLIGHT/FULL episode, for [POSTURE] duration logs
    _last_logged_raw_state = None  # so the [POSTURE] diagnostic line below only prints on change, not every frame

    # Break state machine.
    study_start = time.time()
    break_notified = False
    on_break = False
    break_started_at = None

    # PERF: CAMERA CAPTURE / preview-publish runs every loop tick at
    # CAMERA_CAPTURE_INTERVAL; the expensive POSE PROCESSING + STATE
    # UPDATE block below (Haar-cascade detection, presence/posture
    # state machines, notifications, break reminders) only actually
    # runs once elapsed time reaches POSTURE_CHECK_INTERVAL. This is
    # the "process every N frames while continuously displaying the
    # camera" split -- one cv2.VideoCapture, read every tick (so the
    # driver's buffer never goes stale), heavy work throttled
    # separately. No cat/notification/UI work runs inside the tight
    # per-tick part of this loop -- notify() below is the only thing
    # that could block, and it's dispatched via _notify_async so it
    # never does.
    last_processed_at = 0.0

    try:
        while not _stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                time.sleep(CAMERA_CAPTURE_INTERVAL)
                continue

            # Publish every captured frame for the dashboard's Live
            # Camera card -- cheap relative to detection, and this is
            # what keeps the preview smooth even while pose processing
            # itself is throttled below.
            write_frame(frame)

            now = time.time()
            if now - last_processed_at < POSTURE_CHECK_INTERVAL:
                time.sleep(CAMERA_CAPTURE_INTERVAL)
                continue
            last_processed_at = now

            if _pause_event.is_set():
                # Paused: camera stays open and the preview frame above
                # keeps publishing (so the UI can still show the paused
                # camera view), but posture/presence evaluation, alerts,
                # and break timers are all frozen -- the calibrated
                # baseline and every state machine below are left
                # exactly as they were, so resuming continues seamlessly
                # rather than re-calibrating or losing context.
                time.sleep(CAMERA_CAPTURE_INTERVAL)
                continue

            posture_state = tracker.update(frame)
            stats.posture_state = posture_state

            if POSTURE_DEBUG_MODE and tracker.last_debug:
                d = tracker.last_debug
                print(
                    f"[posture debug] baseline_y={d['baseline_y']} current_y={d['current_y']} "
                    f"face_h_ratio={d['face_height_ratio']} displacement={d['displacement_ratio']} "
                    f"state={d['state']} (stable={posture_state})"
                )

            # --- Presence state machine ---
            if posture_state == AWAY:
                if presence_state == "PRESENT":
                    presence_state = "AWAY"
                    away_started_at = time.time()
                    log_event(stats.session_id, "AWAY")
                stats.tick("away")
                stats.presence_state = "AWAY"
            else:
                if presence_state == "AWAY":
                    presence_state = "PRESENT"
                    away_duration = time.time() - (away_started_at or time.time())
                    log_event(stats.session_id, "RETURNED", duration=f"{away_duration:.0f}")
                    away_started_at = None
                    # Coming back from a long AWAY effectively starts a
                    # fresh study clock, so we don't immediately fire a
                    # break reminder right after returning.
                    if away_duration > AWAY_TIMEOUT:
                        study_start = time.time()
                        break_notified = False
                stats.tick("focus" if posture_state == GOOD else "focus")
                stats.presence_state = "PRESENT"

            # --- [POSTURE] diagnostic logging (state-change only, not
            # every frame -- POSTURE_CHECK_INTERVAL already runs every
            # couple seconds, so a per-frame print would spam the
            # console). This traces the exact chain asked for:
            # detection -> classification -> threshold -> trigger.
            if posture_state != _last_logged_raw_state:
                if posture_state in (GOOD,):
                    print("[POSTURE] Good posture detected")
                    if _last_logged_raw_state in (SLIGHT_SLOUCH, SLOUCH):
                        print("[POSTURE] Bad posture timer reset")
                elif posture_state in (SLIGHT_SLOUCH, SLOUCH):
                    print(f"[POSTURE] Current posture: {posture_state}")
                else:
                    print(f"[POSTURE] Current posture: {posture_state}")
                _last_logged_raw_state = posture_state

            # --- Posture alerts (only meaningful while actually present) ---
            # Transition-based, same philosophy as the Day 1 distraction
            # state machine: exactly one log entry per episode boundary,
            # not one per poll. notify() is still called every poll while
            # SLOUCH (notifier.py's own NOTIFICATION_COOLDOWN throttles
            # the actual repeat reminders), but log_event() only fires on
            # state changes now.
            if posture_state == SLOUCH:
                if bad_posture_started_at is None:
                    bad_posture_started_at = time.time()
                bad_duration = time.time() - bad_posture_started_at
                print(f"[POSTURE] Bad posture duration: {bad_duration:.0f}s")
                if posture_alert_state != "FULL":
                    print("[POSTURE] Threshold reached")
                    print("[POSTURE] Triggering posture notification")
                _notify_async(
                    "Posture Reminder",
                    "Sit back and straighten your posture.",
                    kind="slouch",
                )
                if posture_alert_state != "FULL":
                    log_event(stats.session_id, "POSTURE_WARNING", category="SLOUCHING")
                    stats.slouch_events += 1
                    posture_alert_state = "FULL"
            elif posture_state == SLIGHT_SLOUCH:
                if bad_posture_started_at is None:
                    bad_posture_started_at = time.time()
                bad_duration = time.time() - bad_posture_started_at
                print(f"[POSTURE] Bad posture duration: {bad_duration:.0f}s")
                if posture_alert_state != "SLIGHT":
                    log_event(stats.session_id, "POSTURE_WARNING", category="SLIGHT_SLOUCH")
                    posture_alert_state = "SLIGHT"
            elif posture_state in (GOOD, AWAY, UNKNOWN):
                # AWAY (no person) must never be reported/left as GOOD,
                # and the bad-posture timer must reset in all three of
                # these cases -- there's no "bad posture" to time when
                # nobody's there to have bad posture, or before we even
                # know their baseline.
                bad_posture_started_at = None
                if posture_alert_state != "NONE":
                    log_event(stats.session_id, "POSTURE_RECOVERED")
                    posture_alert_state = "NONE"

            # --- Break reminder ---
            if on_break:
                stats.tick("break")
                if time.time() - break_started_at >= BREAK_DURATION:
                    on_break = False
                    study_start = time.time()
                    break_notified = False
                    log_event(stats.session_id, "BREAK_END")
            else:
                elapsed_study = time.time() - study_start
                if elapsed_study >= BREAK_INTERVAL and not break_notified and presence_state == "PRESENT":
                    minutes = int(BREAK_INTERVAL // 60)
                    _notify_async(
                        "Break Time",
                        f"You've been studying continuously for {minutes} minutes.",
                        kind="break",
                    )
                    log_event(stats.session_id, "BREAK_START", value=str(BREAK_DURATION))
                    on_break = True
                    break_started_at = time.time()
                    break_notified = True

            time.sleep(CAMERA_CAPTURE_INTERVAL)
    finally:
        cap.release()
        # Camera is going away (session end, or this thread exiting) --
        # drop the stale frame so the dashboard shows "camera
        # unavailable" / inactive instead of a frozen last image.
        clear_frame()


def status_writer(stats: SessionStats):
    """
    Background loop: periodically snapshots `stats`' current-state
    fields to live_state.json for the dashboard, and mirrors the same
    countdown-relevant fields into session_bridge for the Live Session
    page's timer/pause UI. Purely observational -- reads stats, writes
    a file, changes no monitoring behavior.
    """
    while not _stop_event.is_set():
        write_status(
            session_id=stats.session_id,
            start_time=stats.start_time,
            focus_seconds=stats.focus_seconds,
            distraction_seconds=stats.distraction_seconds,
            away_seconds=stats.away_seconds,
            break_seconds=stats.break_seconds,
            slouch_events=stats.slouch_events,
            distraction_events=stats.distraction_events,
            on_break=stats.on_break,
            presence_state=stats.presence_state,
            posture_state=stats.posture_state,
            distraction_active=stats.distraction_active,
            current_app_label=stats.current_app_label,
            calibrated=stats.calibrated,
            subject=stats.session.subject,
            study_mode=stats.session.mode,
            paused=_pause_event.is_set(),
        )

        if stats.duration_seconds is not None:
            elapsed = stats.focus_seconds + stats.distraction_seconds + stats.away_seconds
            remaining = max(0, stats.duration_seconds - elapsed)
            session_bridge.publish_state(
                remaining_seconds=remaining,
                phase=(session_bridge.PHASE_PAUSED if _pause_event.is_set()
                       else session_bridge.PHASE_ACTIVE),
            )

        time.sleep(STATUS_WRITE_INTERVAL)


def run_overlay_test():
    """
    Standalone companion test -- exercises ONLY window_tracker's sibling
    module, companion_overlay.py, with no distraction detection, no
    session config, no webcam involved at all. This exists precisely to
    answer "does the overlay even work" in isolation before trusting it
    plugged into the full detection pipeline (per Day 2 debugging: test
    the button-to-cat path before testing distraction-to-cat).

    Run with:
        python main.py --test-overlay
    """
    print("=== Companion overlay standalone test ===")
    print("Creating overlay and attempting to show a test message...\n")

    overlay = CompanionOverlay(session_id=None)
    started = overlay.start()
    print(f"\noverlay.available = {overlay.available}")
    print(f"overlay.start() returned = {started}\n")

    if not started:
        print("RESULT: FAILED to start. See the [companion_overlay] "
              "OVERLAY_ERROR lines above (and the traceback, if any) "
              "for the exact reason. The cat cannot appear until this "
              "is fixed -- this is independent of distraction detection.")
        return

    try:
        overlay.show("Test companion \U0001F431 -- if you can see this, the overlay works!")
        print(f"Companion should now be visible for {INTERVENTION_DISPLAY_SECONDS} seconds "
              f"near the '{__import__('config').COMPANION_POSITION}' corner of your screen.")
        print("Look for a small cat + speech bubble. It should be on top of any other window.")
        time.sleep(INTERVENTION_DISPLAY_SECONDS + 2)
        print("\nRESULT: show() completed without raising. If you did NOT see the cat, "
              "check the OVERLAY_POSITION line above for its coordinates -- it may be "
              "off-screen on a multi-monitor setup, or hidden behind an always-on-top "
              "window of your own.")
    except Exception as e:
        print(f"\nRESULT: show() raised an exception: {e!r}")
        traceback.print_exc()
    finally:
        overlay.stop()


def run_cat_test():
    """
    Standalone cat-overlay test, same idea as run_overlay_test() above
    but for desktop_pet.CatController -- no distraction detection, no
    session config, no webcam. Answers "does the animated cat even
    work" in isolation.

    Run with:
        python main.py --test-cat
    """
    print("=== Cat overlay standalone test ===")
    print("Creating the cat window and running one full intervention...\n")

    media_controller = MediaController() if MEDIA_INTERFERENCE_ENABLED else None
    cat = CatController(session_id=None, log_event_fn=None, media_controller=media_controller,
                         max_intervention_seconds=CAT_MAX_INTERVENTION_SECONDS)
    started = cat.start()
    print(f"\ncat.available = {cat.available}")
    print(f"cat.start() returned = {started}\n")

    if not started:
        print("RESULT: FAILED to start. See the [cat_window] CAT_WINDOW_ERROR "
              "lines above (and the traceback, if any) for the exact reason.")
        return

    try:
        print("First appearance: cat should enter, walk in, stare, paw, perform a "
              "real media action (if a YouTube tab is focused), then leave on its "
              "own -- it should NOT get stuck sitting there idle.")
        cat.start_intervention("Test intervention -- appearance 1")
        time.sleep(14)  # long enough for the full enter->...->exit sequence to finish on its own
        print("Second appearance (fresh visit, same as any re-trigger after "
              "CAT_COOLDOWN_SECONDS): should enter and run the full sequence again.")
        cat.start_intervention("Test intervention -- appearance 2")
        time.sleep(6)
        print("Simulating return-to-study mid-sequence: cat should settle, then exit cleanly.")
        cat.stop_intervention()
        time.sleep(2)
        print("\nRESULT: sequence completed without raising. If you did NOT see the "
              "cat, check CAT_ENTERED/CAT_STARED lines above for its coordinates. If "
              "it appeared but never pawed/acted, check CAT_LEVEL_ACTION and "
              "CAT_MEDIA_SKIPPED lines for why.")
    except Exception as e:
        print(f"\nRESULT: cat sequence raised an exception: {e!r}")
        traceback.print_exc()
    finally:
        cat.shutdown()


class SessionRuntime:
    """
    Owns exactly one running study session's threads/overlays/webcam,
    the same set main() used to start once and run until Ctrl+C. Now
    extracted into start()/stop() so a SessionSupervisor can create and
    tear one of these down per web-triggered session, any number of
    times, within the same long-lived process -- this is the piece
    that used to only be reachable via prompt_for_session()'s
    terminal input() prompts.

    Nothing about the monitor loops (distraction_monitor,
    posture_monitor, status_writer) or the escalation chain
    (InterventionManager, CompanionOverlay, CatController) changed --
    this class just calls the exact same functions main() already did,
    at a time of the supervisor's choosing instead of at import/process
    start.
    """

    def __init__(self, session: StudySession, duration_seconds: int):
        self.session = session
        self.session_id = new_session_id()
        self.stats = SessionStats(self.session_id, session)
        self.stats.duration_seconds = duration_seconds
        self.overlay = None
        self.cat_controller = None
        self.intervention = None
        self._threads = []

    def start(self):
        global _stop_event, _pause_event
        _stop_event = threading.Event()
        _pause_event = threading.Event()

        log_event(self.session_id, "SESSION_START", category=self.session.subject, value=self.session.mode)

        if COMPANION_ENABLED:
            self.overlay = CompanionOverlay(session_id=self.session_id)
            if not self.overlay.start():
                log_event(self.session_id, "OVERLAY_UNAVAILABLE")
                print("WARNING: companion overlay failed to start -- falling back "
                      "to plain desktop notifications for this session.")

        if COMPANION_ENABLED:
            media_controller = MediaController() if MEDIA_INTERFERENCE_ENABLED else None
            self.cat_controller = CatController(
                session_id=self.session_id,
                log_event_fn=log_event,
                media_controller=media_controller,
                max_intervention_seconds=CAT_MAX_INTERVENTION_SECONDS,
            )
            if not self.cat_controller.start():
                log_event(self.session_id, "OVERLAY_UNAVAILABLE", value="cat_controller")
                print("WARNING: cat overlay failed to start -- falling back to the "
                      "plain companion bubble (or notifications) for this session.")

        self.intervention = InterventionManager(self.session_id, self.overlay, self.cat_controller)

        print(f"Study Guard session '{self.session_id}' starting ({self.session.subject}, "
              f"{duration_seconds_label(self.stats.duration_seconds)}).")

        t1 = threading.Thread(target=distraction_monitor, args=(self.stats, self.intervention), daemon=True)
        t2 = threading.Thread(target=posture_monitor, args=(self.stats,), daemon=True)
        t3 = threading.Thread(target=status_writer, args=(self.stats,), daemon=True)
        self._threads = [t1, t2, t3]
        for t in self._threads:
            t.start()

    def pause(self):
        _pause_event.set()
        log_event(self.session_id, "SESSION_PAUSED")

    def resume(self):
        _pause_event.clear()
        log_event(self.session_id, "SESSION_RESUMED")

    def stop(self, reason: str = "manual"):
        _stop_event.set()
        for t in self._threads:
            t.join(timeout=3)
        if self.cat_controller is not None:
            self.cat_controller.shutdown()
        if self.overlay is not None:
            self.overlay.stop()
        clear_status()
        clear_frame()

        duration = time.time() - self.stats.start_time
        log_event(self.session_id, "SESSION_END", duration=f"{duration:.0f}", value=reason)
        print(f"Session '{self.session_id}' ended ({reason}). "
              f"Focus: {self.stats.focus_seconds:.0f}s | Distraction: {self.stats.distraction_seconds:.0f}s | "
              f"Away: {self.stats.away_seconds:.0f}s | Break: {self.stats.break_seconds:.0f}s")

        summary = {
            "session_id": self.session_id,
            "duration_seconds": round(duration),
            "focus_seconds": round(self.stats.focus_seconds),
            "distraction_seconds": round(self.stats.distraction_seconds),
            "away_seconds": round(self.stats.away_seconds),
            "slouch_events": self.stats.slouch_events,
            "distraction_events": self.stats.distraction_events,
        }
        try:
            from scoring import read_events, compute_totals, compute_health_score
            rows = read_events(self.session_id)
            score = compute_health_score(compute_totals(rows))
            summary["score"] = score
        except Exception:
            # Scoring is a nice-to-have summary -- never let it stop
            # a clean session end.
            summary["score"] = None
        return summary


def duration_seconds_label(seconds) -> str:
    if not seconds:
        return "no timer"
    minutes = round(seconds / 60)
    return f"{minutes} min"


class SessionSupervisor:
    """
    The web-facing session lifecycle owner. Runs forever in the main
    thread (replacing prompt_for_session() + the one-shot monitor
    start main() used to do), polling session_bridge for commands
    queued by api_server.py's /api/session/* routes and driving exactly
    one SessionRuntime at a time -- there is never more than one
    concurrent study session, same invariant main() always had, just
    now enforced by only creating a new SessionRuntime in response to a
    "start" command while none is already active.

    Also owns automatic timer completion: once a session's planned
    duration has elapsed, it is ended exactly the same way a manual
    "END SESSION" click would end it (same summary, same logging) --
    the user never has to be the one to notice the timer hit zero.
    """

    POLL_INTERVAL = 0.5

    def __init__(self):
        self.runtime: SessionRuntime | None = None

    def _handle_start(self, cmd: dict):
        if self.runtime is not None:
            # A session is already active/paused -- a stray/duplicate
            # start request is simply ignored rather than silently
            # replacing the running session's state.
            return
        duration_seconds = int(cmd.get("duration_seconds") or 0)
        if duration_seconds <= 0:
            session_bridge.publish_state(error="invalid_duration")
            return

        session = create_session(
            subject=cmd.get("subject"),
            mode=cmd.get("mode"),
            allowed_apps=cmd.get("allowed_apps"),
            extra_keywords=cmd.get("extra_keywords"),
        )
        self.runtime = SessionRuntime(session, duration_seconds)
        session_bridge.publish_state(
            phase=session_bridge.PHASE_CALIBRATING,
            duration_seconds=duration_seconds,
            remaining_seconds=duration_seconds,
            calibration_progress=0.0,
            session_id=self.runtime.session_id,
            subject=session.subject,
            study_mode=session.mode,
            last_summary=None,
            error=None,
        )
        self.runtime.start()

    def _handle_pause(self):
        if self.runtime is None:
            return
        self.runtime.pause()
        session_bridge.publish_state(phase=session_bridge.PHASE_PAUSED)

    def _handle_resume(self):
        if self.runtime is None:
            return
        self.runtime.resume()
        session_bridge.publish_state(phase=session_bridge.PHASE_ACTIVE)

    def _handle_end(self, reason: str = "manual"):
        if self.runtime is None:
            return
        summary = self.runtime.stop(reason=reason)
        self.runtime = None
        session_bridge.publish_state(
            phase=session_bridge.PHASE_COMPLETE,
            remaining_seconds=0,
            last_summary=summary,
        )

    def run(self):
        print("Study Guard session supervisor ready -- waiting for a session "
              "to be started from the Live Session page.")
        while True:
            for cmd in session_bridge.pop_commands():
                kind = cmd.get("cmd")
                if kind == session_bridge.CMD_START:
                    self._handle_start(cmd)
                elif kind == session_bridge.CMD_PAUSE:
                    self._handle_pause()
                elif kind == session_bridge.CMD_RESUME:
                    self._handle_resume()
                elif kind == session_bridge.CMD_END:
                    self._handle_end(reason="manual")

            # Automatic timer completion: once the planned duration has
            # elapsed on an ACTIVE (not paused) session, end it exactly
            # as if the user had clicked End Session.
            if (self.runtime is not None and not _pause_event.is_set()
                    and self.runtime.stats.duration_seconds is not None):
                elapsed = (self.runtime.stats.focus_seconds
                           + self.runtime.stats.distraction_seconds
                           + self.runtime.stats.away_seconds)
                if elapsed >= self.runtime.stats.duration_seconds:
                    self._handle_end(reason="timer_complete")

            time.sleep(self.POLL_INTERVAL)


def main():
    # Local HTTP API for the web frontend (see api_server.py). Runs as
    # a daemon thread in this SAME process so it can read live_state.json
    # / live_frame.jpg / session_bridge state the instant the monitors
    # write them, with no extra IPC. Started immediately (not after a
    # session begins) so the Live Session page can show readiness
    # indicators and issue the very first "start session" request --
    # this is what makes "no VS Code, no terminal input()" possible.
    try:
        import api_server
        t_api = threading.Thread(
            target=api_server.run, kwargs={"host": API_HOST, "port": API_PORT}, daemon=True
        )
        t_api.start()
        print(f"Web UI: http://{API_HOST}:{API_PORT}")
    except ImportError:
        print("WARNING: Flask not installed -- the web API/frontend will not be available. "
              "Run 'pip install flask' to enable it.")

    supervisor = SessionSupervisor()
    try:
        supervisor.run()
    except KeyboardInterrupt:
        print("\nStopping Study Guard...")
        if supervisor.runtime is not None:
            supervisor.runtime.stop(reason="shutdown")


if __name__ == "__main__":
    import sys
    if "--test-overlay" in sys.argv:
        run_overlay_test()
    elif "--test-cat" in sys.argv:
        run_cat_test()
    else:
        main()
