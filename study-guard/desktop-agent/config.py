"""
All the tunable settings live here so you don't have to dig through
the rest of the code to change behaviour. Nothing below should be
hardcoded anywhere else in the project.
"""

import os

# --- Data directory (deployment-aware) ---
# Where every local state file (session_log.csv, live_state.json,
# live_frame.jpg, roadmap_data.json, runtime_settings.json) is read
# from / written to. Defaults to "." (the process's current working
# directory) -- identical to this project's original behavior, so
# running `python launcher.py` / `python main.py` on a Windows desktop
# is completely unaffected.
#
# Only matters when api_server.py is also run standalone off the
# desktop (see backend/app.py) -- e.g. on Render, where the working
# directory may not be writable/persistent across deploys. Set the
# DATA_DIR env var there to a writable, persistent path.
DATA_DIR = os.environ.get("DATA_DIR", ".")
if DATA_DIR != "." and not os.path.isdir(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)


def data_path(filename: str) -> str:
    """Resolves a state filename against DATA_DIR. Used by every
    module that persists local state (config.py's own LOG_FILE /
    ROADMAP_DATA_FILE below, plus live_status.py, runtime_settings.py)."""
    return os.path.join(DATA_DIR, filename)

# --- Distraction detection: known-distraction apps/sites ---
# If the ACTIVE WINDOW TITLE contains any of these words (case-insensitive),
# the app itself is treated as a known distraction *unless* the session
# explicitly allows it. Add/remove freely. The matched keyword itself
# (capitalized) is what gets logged -- never the full window title.
#
# NOTE: YouTube is deliberately NOT in this list. YouTube hosts both
# lectures and entertainment, so it can't be judged by app name alone --
# see CONTENT_DEPENDENT_APPS below, which inspects the window title
# instead of blanket-flagging the app.
DISTRACTION_KEYWORDS = [
    "instagram",
    "facebook",
    "netflix",
    "twitter",
    "x.com",
    "reddit",
    "tiktok",
    "whatsapp web",
]

# Apps where the app name alone doesn't tell you whether it's a
# distraction -- the window title has to be inspected (study keywords
# vs. distraction keywords) to decide. YouTube is the canonical example:
# "YouTube - Linked List Lecture" vs. "YouTube - Funny Videos".
CONTENT_DEPENDENT_APPS = [
    "youtube",
]

# Words in a content-dependent app's window title that suggest
# entertainment rather than study, even though the app itself is
# ambiguous (e.g. "YouTube - Gaming Highlights").
DISTRACTION_CONTENT_KEYWORDS = [
    "funny",
    "prank",
    "comedy",
    "meme",
    "highlights",
    "compilation",
    "gameplay",
    "gaming",
    "trailer",
    "reaction",
    "vlog",
    "unboxing",
    "live stream",
    "shorts",
]

# Generic words that suggest a window is study-related, regardless of
# subject. Combined at session-start with words from the subject name
# itself and any keywords the user adds, so the user never has to type
# out a long list by hand.
STUDY_KEYWORDS = [
    "lecture",
    "tutorial",
    "course",
    "class",
    "chapter",
    "notes",
    "exam",
    "assignment",
    "problem",
    "solution",
    "study",
    "learn",
    "crash course",
    "full course",
    "walkthrough",
    "explained",
    "concept",
    "fundamentals",
    "basics",
    "revision",
]

# Apps/sites offered as sensible defaults when starting a session --
# the user can accept these or type their own comma-separated list.
DEFAULT_ALLOWED_APPS = [
    "YouTube",
    "VS Code",
    "ChatGPT",
    "College LMS",
]

# BUGFIX (allowed apps still triggering the cat): the actual OS window
# title often doesn't literally contain the short name a user types --
# e.g. VS Code's real title bar says "...- Visual Studio Code", not
# "VS Code", so a plain substring match against "vs code" never hit
# and the app fell through to "unknown_window" -> treated as a
# distraction. This maps common short/typed names to every real
# title-bar variant they should also match. Matching in
# session_context.py checks the typed name AND all of its aliases.
ALLOWED_APP_ALIASES = {
    "vs code": ["vs code", "visual studio code"],
    "vscode": ["vscode", "visual studio code"],
    "chatgpt": ["chatgpt", "chat gpt", "openai"],
    "youtube": ["youtube"],
}

# --- Study modes ---
# Each mode controls how forgiving the grace period is before a
# potential distraction is confirmed. Kept as three simple named
# presets rather than lots of independent knobs.
DISTRACTION_GRACE_STRICT = 20
DISTRACTION_GRACE_BALANCED = 60
DISTRACTION_GRACE_FLEXIBLE = 120

STUDY_MODES = {
    "STRICT": {"grace_period": DISTRACTION_GRACE_STRICT},
    "BALANCED": {"grace_period": DISTRACTION_GRACE_BALANCED},
    "FLEXIBLE": {"grace_period": DISTRACTION_GRACE_FLEXIBLE},
}
DEFAULT_STUDY_MODE = "BALANCED"

# Fallback grace period for any code path that isn't session-aware.
# Kept equal to the BALANCED preset so existing behavior is unchanged
# if this constant is used directly.
DISTRACTION_GRACE_PERIOD = DISTRACTION_GRACE_BALANCED

# How often (seconds) we check the active window title.
WINDOW_CHECK_INTERVAL = 3

# --- Posture / screen-time detection ---
# How often (seconds) we grab a webcam frame to check posture/presence.
POSTURE_CHECK_INTERVAL = 2

# Which webcam to use. 0 is almost always the built-in/default camera.
CAMERA_INDEX = 0

# How many valid face detections to collect during calibration before
# locking in a baseline (the MEDIAN of these readings, not just the
# first frame -- a single noisy frame used to badly skew the whole
# session's posture readings).
POSTURE_CALIBRATION_SAMPLES = 15

# How many recent frames' face-position readings to smooth together
# (rolling median) before comparing against the baseline. This is what
# lets a slow/subtle slouch survive single-frame detector jitter long
# enough to register at all.
POSTURE_SMOOTHING_WINDOW = 5

# Vertical drop from the calibrated baseline, normalized by the
# CURRENT SHOULDER WIDTH (not frame height) -- so the same physical
# slouch angle reads the same whether you're sitting close to or far
# from the camera. Two thresholds give a SLIGHT_SLOUCH state before a
# full SLOUCH state, rather than one abrupt cutoff.
#
# Recommended starting points (see README for how to tune these with
# POSTURE_DEBUG_MODE against your own webcam/desk setup):
POSTURE_SENSITIVITY = {
    "slight": 0.15,   # displacement past this, as a fraction of shoulder width -> SLIGHT_SLOUCH
    "full": 0.30,      # displacement past this -> SLOUCH
}

# How many consecutive (already-smoothed) readings before we alert.
# Lower than before (was 5) because the rolling median above already
# absorbs single-frame noise, so we don't need as much extra margin on
# top of it -- keeps sustained slouches from taking too long to confirm.
POSTURE_CONSECUTIVE_FRAMES = 4

# Minimum per-landmark visibility (MediaPipe Pose's own 0..1 confidence
# score) required for the nose and both shoulders to count as
# "reliably detected" this frame. Below this, the landmark is treated
# as missing even though MediaPipe still returned *some* coordinate
# for it (it extrapolates when unsure) -- this is exactly what keeps a
# barely-visible/occluded nose or shoulder from being scored as if it
# were a clean read. Hip landmarks are never checked -- posture
# tracking does not use them.
POSTURE_MIN_LANDMARK_VISIBILITY = 0.6

# How long (seconds) a momentary pose-tracking miss is tolerated
# before presence actually drops to AWAY. One bad frame at the
# ~POSTURE_CHECK_INTERVAL cadence should never flip presence -- this
# is the grace window that keeps a blink, a hand pass, or one dropped
# frame from being reported as the user leaving the desk. Sustained
# absence past this window still reports AWAY promptly (presence is
# time-critical), same as before.
POSTURE_AWAY_GRACE_SECONDS = 4

# When True, posture_monitor prints one line per check with the exact
# numbers behind the current posture decision (baseline/current/face
# height/displacement ratio/state) -- use this to tune the thresholds
# above against your own webcam. OFF by default; this is a genuinely
# verbose per-frame stream and shouldn't run in normal use.
POSTURE_DEBUG_MODE = False

# Continuous "at desk" study time before we nudge you to take a break.
# Paired with BREAK_DURATION below (Pomodoro-style).
BREAK_INTERVAL = 50 * 60
BREAK_DURATION = 10 * 60

# If no face is detected for this long, we treat you as AWAY.
AWAY_TIMEOUT = 30

# --- Logging ---
LOG_FILE = data_path("session_log.csv")

# --- Notifications ---
APP_NAME = "Study Guard"

# Minimum seconds between two notifications of the same kind, so a
# borderline state doesn't spam repeated alerts.
NOTIFICATION_COOLDOWN = 45

# --- Companion / escalation (final model) ---
# Master switch for the cat overlay specifically. When False, the cat
# stage of escalation falls back to a plain desktop notification
# instead -- the notification stages (1-3) below are unaffected either
# way, since those were always plain notifications, never the cat.
COMPANION_ENABLED = True

# The distraction has to be CONFIRMED by the existing Day 1 state
# machine (i.e. already past the session's own STRICT/BALANCED/FLEXIBLE
# grace period) before escalation starts at all -- there is no second,
# separate grace period here. Notification #1 fires immediately at
# that point.
MAX_NOTIFICATIONS = 3

# Seconds of *continued* confirmed distraction between successive
# notifications (1->2 and 2->3). Same interval reused for both steps,
# per the "configured escalation interval" behavior.
NOTIFICATION_INTERVAL = 30

# Once all MAX_NOTIFICATIONS have been sent and the user is STILL
# distracted, the cat triggers immediately (no extra wait) -- but if
# it keeps triggering because the SAME distraction episode never ends,
# this is the minimum gap between one cat appearance and the next.
CAT_COOLDOWN_SECONDS = 60

# How long the companion stays visible per appearance before it
# auto-hides (it can also be hidden immediately by focus recovery).
INTERVENTION_DISPLAY_SECONDS = 6

# Roughly how wide the companion + speech bubble are, in pixels.
# Actual placement adapts to the detected screen resolution.
COMPANION_WIDTH = 320
COMPANION_HEIGHT = 170

# Which screen corner the companion slides in from/rests near.
# One of: "bottom-right", "bottom-left", "top-right", "top-left".
COMPANION_POSITION = "bottom-right"

# Animation step delay in milliseconds -- smaller is smoother but
# uses more CPU while animating. Kept deliberately simple (a linear
# slide), not a fancy easing curve.
COMPANION_ANIMATION_STEP_MS = 15

# Temporary diagnostic logging for the overlay's lifecycle (create /
# show / position / hide / destroy / error), on top of always-on
# console prints. Written to session_log.csv when True so overlay
# events show up alongside everything else while we're debugging why
# it wasn't appearing. Safe to flip to False once it's confirmed
# reliable -- console prints on errors stay on regardless.
COMPANION_DEBUG = True

# --- Cat desktop-pet intervention (final escalation step) ---
# Reuses COMPANION_ENABLED above as the master on/off switch for the
# whole escalation-overlay feature (unchanged meaning: False falls
# back to plain notifications for every stage, same as before this
# integration). These settings only affect what happens once
# escalation actually reaches the cat.

# Safety ceiling: the cat intervention window always exits itself
# after this many seconds even if return-to-study is never detected
# (e.g. a bug in the distraction engine, or the user leaving the
# desk). See desktop_pet/cat_window.py's timeout handling.
CAT_MAX_INTERVENTION_SECONDS = 90

# --- Learning Roadmap ---
# Single JSON file, same atomic-overwrite-in-place pattern as
# live_state.json (see live_status.py / roadmap_store.py) -- one file,
# shared by the dashboard (which owns roadmap CRUD) and main.py's
# distraction monitor (which only ever reads the current topic's
# keywords, never writes here).
ROADMAP_DATA_FILE = data_path("roadmap_data.json")

# How long a topic's cached resource list is considered fresh before
# roadmap_resources.get_resources() re-derives it. Resource lookups
# are cheap/local right now (see roadmap_resources.py's INTEGRATION
# BOUNDARY note for wiring in a real web-search backend later), but
# this cache is what keeps a future real backend from being hit on
# every dashboard rerun.
RESOURCE_CACHE_TTL_DAYS = 14

# Whether an in-progress roadmap topic's name/keywords are folded into
# the active study session's study_keywords, so opening a resource
# that matches the topic you're actively working through (e.g. a
# YouTube search result for that topic) isn't auto-flagged as a
# distraction. Does NOT add the site/app itself to allowed_apps --
# only content-dependent apps (see CONTENT_DEPENDENT_APPS) are
# affected, exactly like the existing YouTube-title heuristic.
ROADMAP_DISTRACTION_INTEGRATION_ENABLED = True

# Whether the cat is allowed to attempt the OS-level media play/pause
# key as part of its escalation (see media_control/media_controller.py
# for exactly what this can and can't do -- it never targets a
# specific app/site, and never attempts rewind/forward, regardless of
# this setting). False disables CatController's media-action level
# entirely; the cat still performs the *visual* gesture, just without
# ever touching the keyboard.
MEDIA_INTERFERENCE_ENABLED = True
