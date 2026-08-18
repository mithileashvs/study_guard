# Study Guard -- Desktop Agent

> This is the **desktop agent's** own documentation (webcam, posture,
> distraction detection, cat companion, and the local API/dashboard it
> serves at `127.0.0.1:8000`). For the overall web + desktop
> architecture, Vercel/backend deployment, and environment variables,
> see the [root README](../README.md).

A small automation system that watches over your study sessions using
your webcam and your active window, and nudges you back on track when
you slouch, get distracted, or forget to take a break.

## The problem

Long screen-based study sessions quietly go wrong in two ways: your
posture degrades and nobody tells you, and it's easy to drift onto
YouTube/Instagram/etc. without noticing how long you've been gone.
Study Guard automates the "sense -> decide -> act" loop that would
normally require a person watching over your shoulder.

## Features

- **Study session context**: at startup you define a subject, a study
  mode (STRICT / BALANCED / FLEXIBLE), and which apps/sites are
  allowed for the session -- distraction detection is judged against
  *this*, not a one-size-fits-all keyword list.
- **Context-aware distraction detection** with a configurable grace
  period, so a brief glance at a tab doesn't count as a distraction --
  only sustained time does. Content-dependent apps (YouTube) are
  judged by window title, not app name alone: "YouTube - Linked List
  Lecture" is treated as study, "YouTube - Funny Videos" is not.
- **Posture monitoring** via a calibrated baseline and a smoothed
  state machine (`GOOD` / `SLIGHT_SLOUCH` / `SLOUCHING`), so a single
  bad frame or a brief head turn can't trigger a false alert.
- **Presence detection** as a proper state machine (`PRESENT` ->
  `AWAY` -> `RETURNED`), logging each transition exactly once.
- **Playful desktop companion** (Day 2): a small cat overlay that
  slides onto the screen when a distraction is confirmed, escalates
  through a few short, non-nagging messages the longer it continues,
  and disappears the instant you're back on task. Falls back to a
  plain notification if it's disabled or can't run.
- **Desktop notifications** for posture and break reminders,
  rate-limited so the same alert can't spam you repeatedly.
- **Study session timer** tracking focus, distraction, away, and break
  time for the session.
- **Break reminders** on a configurable study/break interval.
- **Study Health Score** (0-100): one number summarizing the session,
  built from five weighted, explainable components.
- **Structured CSV event logging**, grouped by a unique session ID,
  storing only the minimum information needed.
- **Dashboard** (web UI at `http://127.0.0.1:8000`, built with
  React) showing the health score, session stats, live camera state,
  recent events, and a few simple charts.
- **Multithreading**: the window monitor and posture monitor run as
  independent background threads.
- **Local, privacy-first processing** end to end (see below).

## How it works

At startup, `session_context.py` asks for the study session's subject,
mode, and allowed apps (sensible defaults on every field -- just press
Enter). This builds a `StudySession` used by the distraction monitor
for the rest of the run.

Two monitors run in parallel as background threads and both report
into a small shared `SessionStats` object:

1. **Distraction monitor** (`window_tracker.py` + `session_context.py`
   + `distraction_engine.py`) polls the title of your currently
   focused window every few seconds and classifies it with a layered
   decision tree (`session_context.classify_window`): explicitly
   allowed apps pass immediately; content-dependent apps (YouTube) are
   judged by title against study/distraction keywords; known
   distraction apps (Instagram, Netflix, ...) are flagged; anything
   else falls back to a study-keyword check. A `DistractionStateMachine`
   (`distraction_engine.py`) turns sustained distraction into exactly
   one `DISTRACTION_STARTED` / `DISTRACTION_ENDED` + `FOCUS_RECOVERED`
   event per episode -- not one event per poll -- tagged only with the
   matched category/app label (e.g. `"Youtube"`), never the raw window
   title.

2. **Posture / presence monitor** (`posture_tracker.py`) grabs frames
   from your webcam and uses OpenCV's Haar cascade face detector to:
   - Calibrate a "normal posture" baseline at the start of a session.
   - Track your face's vertical drift from that baseline across
     several consecutive frames, smoothing it into one of `GOOD`,
     `SLIGHT_SLOUCH`, `SLOUCHING`, `AWAY`, or `UNKNOWN`.
   - Drive an explicit presence state machine (`PRESENT` -> `AWAY` ->
     `RETURNED`) so absence is logged as a single transition, not
     repeatedly every poll.
   - Trigger break reminders once continuous study time passes
     `BREAK_INTERVAL`, and track the break itself against
     `BREAK_DURATION`.

3. **Intervention manager** (`intervention_manager.py`) reacts to the
   distraction monitor's confirmed/recovered events -- it does not
   detect distraction itself. On a confirmed distraction it sends up
   to `MAX_NOTIFICATIONS` (3) plain desktop notifications, one every
   `NOTIFICATION_INTERVAL` seconds the user remains distracted. Only
   if the user is *still* distracted after all of those does the cat
   companion (`companion_overlay.py`) appear, with a message from
   `companion_messages.py`; if it stays distracted long enough after
   that, the cat can reappear, gated by `CAT_COOLDOWN_SECONDS` so it
   never spams. It hides the cat and resets to stage 0 the instant Day
   1's engine reports recovery -- switching between two different
   distracting windows does NOT reset escalation, only actually
   returning to an allowed/study window does. If the overlay is
   disabled or fails, everything (including the final "cat" stage)
   falls back to a plain desktop notification, and monitoring keeps
   running either way.

All events are timestamped, tagged with a session ID, and appended to
`session_log.csv` (`logger.py`). `scoring.py` re-derives session
totals from that log and computes the Study Health Score, and
`api_server.py` exposes it to the web frontend (`frontend/`), which
visualizes all of it.

```
                 MAIN
                  |
        +---------+-----------------+
        |                           |
 Window Monitor             Posture Monitor
    Thread                      Thread
        |                           |
 Distraction Engine                 |
        |                           |
 Intervention Manager                |
        |                           |
   Companion Overlay                |
        |                           |
        +-------------+-------------+
                       |
                Session Engine (SessionStats)
                       |
        +---------+---------+
        |         |         |
     Alerts    Logger    Scoring
                  |
                  v
              Dashboard
```

## Why this design

- **Keyword/geometry based, not deep learning** -- easy to run on a
  laptop with no GPU, and every decision the system makes can be
  explained in one sentence.
- **State machines over raw thresholds** -- posture and presence both
  go through an explicit, named state rather than a bare boolean, so
  behavior (and bugs) are easy to reason about and describe.
- **Threaded, not sequential** -- the two monitors are independent
  concerns (what you're looking at vs. how you're sitting) and run
  concurrently so neither blocks the other.
- **CSV logging over a database** -- kept intentionally simple for a
  single-user local tool; swapping in SQLite later is a natural next
  step (see below).
- **Study Health Score is linear and inspectable** -- every component
  is a plain ratio or a fixed penalty per event, not a trained model,
  so it can be fully explained during a presentation.
- **Companion is a reactor, not a second detector** -- the intervention
  manager only ever responds to the existing distraction state machine's
  events; there is exactly one place distraction is decided, so the
  companion and the log can never disagree with each other.
- **tkinter for the overlay, not Electron/a web framework** -- it's
  part of the Python standard library (ships with the standard Windows
  installer this project already targets), so the companion adds zero
  new dependencies.

## Setup

```bash
pip install -r requirements.txt
python launcher.py
```

The first run also builds the web frontend automatically (`npm
install` + `npm run build` inside `frontend/`, so Node.js/npm need to
be installed) and opens the dashboard in your browser at
`http://127.0.0.1:8000` once it's ready. On startup it will ask you to
set up your study session (subject, mode, allowed apps -- press Enter
to accept the defaults), then spend a couple of seconds calibrating
your posture baseline -- sit normally and look at the camera.

Press `Ctrl+C` to stop. Shutdown is handled cleanly: all threads stop,
the camera and companion overlay are released, and the session totals
(including the Study Health Score) are printed and saved.

`python main.py` also still works directly (skips the frontend
build/auto-open step, useful if the frontend is already built or
you're running headless) -- `launcher.py` is a thin convenience wrapper
around it.

### Frontend development

The dashboard lives in `../frontend` (repo root, a Vite + React app --
also the same source Vercel deploys) and talks to `api_server.py`'s
local HTTP API. For frontend-only iteration with hot reload:

```bash
cd ../frontend
npm install
npm run dev
```

This serves the UI on `http://127.0.0.1:5173` and talks to the API on
`:8000` (`main.py`/`launcher.py` needs to be running separately for
live data). For normal use, `npm run build` (or `launcher.py`, which
does this for you) produces the static `../frontend/dist/` that
`api_server.py` serves directly on `:8000` -- no separate frontend
server needed.

### Testing the companion overlay in isolation

```bash
python main.py --test-overlay
```

Creates the overlay and shows a test message immediately, with no
session setup, no distraction detection, and no webcam involved --
just the cat window itself. Watch the console: it prints
`OVERLAY_CREATE` / `OVERLAY_POSITION` / `OVERLAY_SHOW` / `OVERLAY_HIDE`
as they happen, and if anything fails, the exact exception + full
traceback (this used to fail silently -- see "Day 2 debugging notes"
below). Use this to confirm the overlay itself works before trusting
it end-to-end with real distraction detection.

## Day 2 debugging notes

Two bugs were found and fixed after Day 2:

**The cat overlay wasn't appearing (notifications were, the cat wasn't).**
The root cause: `CompanionOverlay.show()` never raised on failure --
if the Tk window had failed to initialize, it just silently did
nothing, so `intervention_manager.py` had no way to know it needed to
fall back to a plain notification... except it *did* still fall back,
which was the tell: that only happens when `overlay.available` is
already `False`, which only happens when window construction raised
an exception during startup -- and every except-block in the file was
swallowing that exception with no logging at all. So the overlay was
failing to build, silently, for some Tk/Tcl-level reason specific to
that machine, with zero trace of why. Fixed by:
- Every exception path now prints a full traceback and logs an
  `OVERLAY_ERROR` event (console always; CSV when `COMPANION_DEBUG`
  is on) instead of swallowing it.
- `show()` now raises `RuntimeError` if the window never finished
  initializing, so the intervention manager's existing fallback logic
  actually triggers instead of assuming success.
- A second, independent bug was also fixed while auditing this file:
  the alpha-fade line in `_show_now()` had its condition backwards and
  set the window fully transparent (`alpha=0.0`) on any platform where
  `-transparentcolor` isn't supported -- i.e. exactly a "window exists
  but is invisible" failure mode, separate from the swallowed-exception
  one above.
- `-topmost`/`-transparentcolor` are now re-applied on every `show()`,
  not just at window creation, since Windows can silently drop
  layered-window attributes across a withdraw/deiconify cycle.
- Added `python main.py --test-overlay` (see above) to test the
  overlay in isolation.

If the overlay still doesn't appear on your machine after this fix,
`--test-overlay` will now print the actual reason -- please check that
output first.

**Posture detection wasn't reliably catching slight/slow slouching.**
Three concrete causes, all in `posture_tracker.py`:
1. `calibrate()` used only the *first* successful frame as the
   baseline, even though `main.py` calls it in a loop -- one noisy
   frame (a blink, a momentary tilt) permanently skewed the whole
   session. Fixed: it now accumulates `POSTURE_CALIBRATION_SAMPLES`
   valid readings and uses their median.
2. Only the discrete *state* was smoothed (via consecutive-frame
   confirmation) -- the raw y-position was thresholded every frame
   with no averaging, so a slow slouch's per-frame jitter near the
   threshold kept resetting the confirmation streak before it could
   accumulate. Fixed: the y-position itself is now smoothed with a
   rolling median (`POSTURE_SMOOTHING_WINDOW`) before thresholding.
3. Displacement was normalized by *frame* height, not *face* height,
   so the same physical slouch read differently depending on how close
   you sat to the camera. Fixed: `displacement_ratio = (smoothed_y -
   baseline_y) / current_face_height`.

A `POSTURE_DEBUG_MODE` config flag (off by default) prints the exact
numbers behind each decision -- baseline, current, face height ratio,
displacement, state -- once per check, useful for tuning the
thresholds against your own webcam and desk setup.

## Escalation model

The final intervention flow is three plain notifications, THEN the
cat -- not the cat escalating through its own message tiers:

```
DISTRACTION_STARTED (Day 1 engine, existing grace period)
        |
DISTRACTION_DETECTED                                   -- logged once
        |
Notification #1  (immediate)          -- NOTIFICATION_SENT stage=1
        | still distracted, NOTIFICATION_INTERVAL later
Notification #2                        -- NOTIFICATION_SENT stage=2
        | still distracted, NOTIFICATION_INTERVAL later
Notification #3                        -- NOTIFICATION_SENT stage=3
        | still distracted (no extra delay)
🐱 Cat appears                          -- INTERVENTION_TRIGGERED
        | still distracted, CAT_COOLDOWN_SECONDS later
🐱 Cat can reappear                     -- INTERVENTION_TRIGGERED (repeat)
        |
        v  (from ANY stage above, the moment the window is
        |   classified as allowed/study -- not just "a different
        |   distraction")
FOCUS_RECOVERED                        -- logged once, state resets to 0
```

Switching between two different distracting windows (e.g. Instagram
to a different distracting site) does **not** reset this -- only an
actual recovery event from the Day 1 engine does, since the escalation
manager only ever reacts to that engine's own events rather than
re-deriving distraction state itself. A brand new distraction episode
(after a real recovery) always restarts at Notification #1.

`FOCUS_RECOVERED` is written to `session_log.csv` exactly once per
recovery, by the intervention manager -- `main.py`'s own distraction
monitor loop deliberately skips logging it directly (even though the
Day 1 engine's event is also named `"FOCUS_RECOVERED"`) specifically
to avoid a duplicate row for the same moment. `DISTRACTION_STARTED`
and `DISTRACTION_ENDED` are unrelated event names and are still logged
directly by `main.py` as before, since `scoring.py` and `api_server.py`
depend on those two for the distraction count and session timeline.

## Configuration

All thresholds and keyword lists live in `config.py` --
`DISTRACTION_KEYWORDS` (known-distraction apps), `CONTENT_DEPENDENT_APPS`
and `DISTRACTION_CONTENT_KEYWORDS` (for apps like YouTube that need
title inspection), `STUDY_KEYWORDS`, `DEFAULT_ALLOWED_APPS`,
`STUDY_MODES` / `DISTRACTION_GRACE_STRICT` / `_BALANCED` / `_FLEXIBLE`,
`POSTURE_SENSITIVITY`, `POSTURE_CONSECUTIVE_FRAMES`,
`POSTURE_SMOOTHING_WINDOW`, `POSTURE_CALIBRATION_SAMPLES`,
`POSTURE_DEBUG_MODE`, `AWAY_TIMEOUT`, `BREAK_INTERVAL`,
`BREAK_DURATION`, `CAMERA_INDEX`, `COMPANION_ENABLED`,
`MAX_NOTIFICATIONS`, `NOTIFICATION_INTERVAL`, `CAT_COOLDOWN_SECONDS`,
`INTERVENTION_DISPLAY_SECONDS`, `COMPANION_POSITION`,
`COMPANION_DEBUG`, and more -- nothing important is hardcoded
elsewhere in the project.

**Recommended posture thresholds** (`POSTURE_SENSITIVITY`, as a
fraction of face height): `slight = 0.15`, `full = 0.30`, with
`POSTURE_SMOOTHING_WINDOW = 5` and `POSTURE_CONSECUTIVE_FRAMES = 4`.
These are reasoned starting points, not measured against a real
webcam -- use `POSTURE_DEBUG_MODE` to watch the actual
`displacement_ratio` your setup produces while sitting normally vs.
slouching, and nudge the thresholds to sit cleanly between the two.

## Privacy

Study Guard processes webcam data locally. Webcam frames are not
recorded, stored, or uploaded. Window activity is processed locally
and only minimal classified events are stored in the local session
log.

Concretely, the webcam pipeline is:

```
Webcam -> OpenCV -> Face detection -> Numerical measurements
       -> Posture / presence state -> Local event log
```

No webcam frame ever leaves the process, and no image is ever written
to disk. Similarly, window titles are only ever reduced to a matched
keyword category (e.g. `"Youtube"`) before logging -- the raw title
(which can contain search terms, video names, or chat contents) is
never stored. The project has no network calls, no cloud services, no
accounts, and no face recognition (faces are detected, not identified).
The companion overlay (Day 2) is purely a local GUI window -- it does
not record the screen, capture input beyond its own click-through
display, or send anything anywhere.

## Limitations

- Posture detection is a geometric proxy (smoothed, face-height-
  normalized vertical drift from a calibrated baseline), not true pose
  estimation -- it can still be fooled by leaning sideways rather than
  down, or by a significant camera-angle change mid-session (the
  baseline only ever reflects the angle at calibration time).
- The recommended posture thresholds in `config.py` are reasoned
  defaults, not measured against a real webcam -- use
  `POSTURE_DEBUG_MODE` to tune them for your own setup.
- Distraction detection relies on window titles, so it can't
  understand actual webpage content -- only what's in the title bar.
- Windows-only currently, due to the active-window-title library used
  (the companion overlay itself is cross-platform via tkinter, but
  there's nothing to trigger it without window tracking).
- Study Health Score is a productivity metric for self-reflection, not
  a medical or scientifically validated measurement.
- The companion's "slide-in" animation is intentionally simple (linear
  movement, no easing) -- reliability was prioritized over polish.
- Multi-monitor placement is not monitor-aware; the companion always
  appears relative to the primary display's resolution.

## Possible extensions (not built, intentionally)

- Publish alerts over MQTT so a smart light or phone could react too.
- Swap the posture proxy for a proper pose-estimation model.
- Move logging to SQLite.
- Cross-platform window tracking (Linux/macOS support).
- Additional companion characters, animations, gamification (XP,
  badges, streaks) -- deliberately out of scope for Day 2.
- True multi-monitor-aware placement (currently falls back to the
  primary display).

## Tech used

Python, OpenCV (Haar cascade face detection), multithreading, CSV-based
structured event logging, Windows active-window tracking, tkinter
(desktop companion overlay), Flask (local HTTP API), React + Vite
(web dashboard).
