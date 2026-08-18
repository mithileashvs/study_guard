"""
Pose-landmark posture/presence tracker (v3 -- nose + shoulders only).

REPLACES the old Haar-cascade "face vertical position" heuristic.
That approach could report GOOD POSTURE for a face that was detected
in frame while the user's shoulders were badly slouched, or even
while the user was effectively away and only a face-shaped region (or
noise) happened to trip the cascade -- it had no concept of the body
at all, only a face box.

This version uses MediaPipe Pose to find actual body landmarks, but
deliberately uses ONLY three of them: nose, left shoulder, right
shoulder. Hip landmarks (and any torso/hip-angle calculation) are
intentionally NOT used anywhere in this module -- posture is judged
purely from where the head sits relative to the shoulder line, and
from shoulder geometry itself (tilt), normalized by shoulder width so
it works regardless of how close the user sits to the camera, and
compared against a per-user calibrated baseline rather than one
universal threshold.

DECISION ORDER (never violated):

    1. Is a person reliably present?           NO  -> AWAY
    2. Are nose + both shoulders visible?       NO  -> UNKNOWN, trending AWAY if sustained
    3. Compare current posture to baseline      ->  GOOD / SLIGHT_SLOUCH / SLOUCH

A detected landmark is never, by itself, treated as "good posture" --
step 3 only runs once steps 1 and 2 have already passed.

Two layers of smoothing/debouncing:
  - A rolling median of the raw per-frame deviation score absorbs
    single-frame jitter (a blink, a momentary tracking glitch) before
    any thresholding happens.
  - A consecutive-frame streak on the resulting state absorbs brief
    real movements (a shrug, reaching for something) so the state
    doesn't flicker GOOD/SLIGHT_SLOUCH/SLOUCH every couple of frames,
    and lets the state step down gradually (SLOUCH -> SLIGHT_SLOUCH ->
    GOOD) as posture improves rather than jumping straight to GOOD.
"""

import math
import statistics
import time
from collections import deque

import cv2
from config import (
    POSTURE_SENSITIVITY,
    POSTURE_CONSECUTIVE_FRAMES,
    POSTURE_SMOOTHING_WINDOW,
    POSTURE_CALIBRATION_SAMPLES,
    POSTURE_MIN_LANDMARK_VISIBILITY,
    POSTURE_AWAY_GRACE_SECONDS,
)

# Posture states -- kept as plain strings (not an enum), same as
# before, so the rest of the codebase and the CSV log stay simple.
GOOD = "GOOD"
SLIGHT_SLOUCH = "SLIGHT_SLOUCH"
SLOUCH = "SLOUCH"
AWAY = "AWAY"
UNKNOWN = "UNKNOWN"

# PERF: same idea as the old Haar-cascade downscale -- MediaPipe's own
# cost scales with pixel count, and a study-desk webcam frame is far
# larger than pose estimation needs. Longest edge capped here; the
# returned normalized (0..1) landmark coordinates are resolution-
# independent, so no rescale-back-up step is needed (unlike the old
# pixel-box Haar code).
_DETECT_MAX_DIM = 480

_mp_pose = None  # lazily constructed -- see _get_pose()


def _get_pose():
    """
    Lazily imports and constructs the MediaPipe Pose model. Deferred
    (rather than a top-level import) so any code path that doesn't
    touch the webcam -- tests, the web API, etc. -- never pays the
    mediapipe import cost or requires it installed.
    """
    global _mp_pose
    if _mp_pose is None:
        import mediapipe as mp

        _mp_pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=0,  # lightest model -- runs on a laptop CPU alongside everything else
            smooth_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
    return _mp_pose


# Landmark indices this module cares about (MediaPipe Pose's 33-point
# topology). Only these three are ever read -- no hips, no face-mesh,
# no hands. Hip indices (23, 24) are deliberately not referenced
# anywhere in this file.
_NOSE = 0
_L_SHOULDER, _R_SHOULDER = 11, 12


class _Landmarks:
    """A single frame's worth of the landmarks this module cares
    about, already reduced to plain (x, y, visibility) tuples in
    normalized [0, 1] image coordinates. `ok` is True only when nose
    and both shoulders cleared the visibility floor -- callers should
    not use anything from a not-`ok` instance."""

    __slots__ = ("ok", "nose", "l_shoulder", "r_shoulder")

    def __init__(self):
        self.ok = False
        self.nose = None
        self.l_shoulder = None
        self.r_shoulder = None


def _extract_landmarks(frame) -> "_Landmarks":
    """
    Runs MediaPipe Pose on one frame and returns a _Landmarks with
    nose + both shoulders, or an `ok=False` instance if the model
    found no person, or found one but couldn't confidently place all
    three required points (e.g. partially out of frame, heavy
    occlusion). Confidence is judged per-landmark via MediaPipe's own
    visibility score, not just "did the model return coordinates at
    all" -- it always returns *some* coordinate even when it's
    guessing. Hip landmarks are never read here.
    """
    result = _Landmarks()

    h, w = frame.shape[:2]
    longest_edge = max(h, w)
    scale = min(1.0, _DETECT_MAX_DIM / longest_edge) if longest_edge else 1.0
    small = frame if scale == 1.0 else cv2.resize(
        frame, (max(1, int(w * scale)), max(1, int(h * scale))),
        interpolation=cv2.INTER_AREA,
    )
    rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
    rgb.flags.writeable = False

    output = _get_pose().process(rgb)
    if not output.pose_landmarks:
        return result

    lm = output.pose_landmarks.landmark

    def _pt(idx):
        p = lm[idx]
        return (p.x, p.y, p.visibility)

    nose = _pt(_NOSE)
    l_sh = _pt(_L_SHOULDER)
    r_sh = _pt(_R_SHOULDER)

    required = (nose, l_sh, r_sh)
    if any(p[2] < POSTURE_MIN_LANDMARK_VISIBILITY for p in required):
        return result

    result.ok = True
    result.nose = nose
    result.l_shoulder = l_sh
    result.r_shoulder = r_sh
    return result


def _posture_metrics(pts: "_Landmarks") -> dict:
    """
    Turns raw nose/shoulder landmark positions into the scale-
    independent geometric measurements posture is judged on. Both are
    normalized by shoulder width (a stable per-user, per-distance
    reference -- the same physical slouch reads the same whether the
    user is close to or far from the camera, unlike normalizing by
    frame size). No hip landmark is read or used anywhere in this
    calculation.
    """
    lx, ly, _ = pts.l_shoulder
    rx, ry, _ = pts.r_shoulder
    nx, ny, _ = pts.nose

    shoulder_mid = ((lx + rx) / 2, (ly + ry) / 2)
    shoulder_width = max(1e-6, ((lx - rx) ** 2 + (ly - ry) ** 2) ** 0.5)

    # Forward/downward head displacement: how far the nose has moved
    # below the shoulder line, normalized by shoulder width. This is
    # what a slouch/hunch actually looks like from a webcam -- the
    # head drops and/or pushes forward relative to the shoulders.
    head_drop = (ny - shoulder_mid[1]) / shoulder_width

    # Shoulder tilt: are the shoulders level, or is one noticeably
    # higher (leaning to one side)? atan2 in degrees.
    shoulder_tilt_deg = math.degrees(math.atan2(ry - ly, rx - lx))

    return {
        "head_drop": head_drop,
        "shoulder_tilt_deg": shoulder_tilt_deg,
    }


class PostureTracker:
    """
    Pose-landmark posture tracker using ONLY nose + left/right
    shoulder landmarks -- no hip landmarks anywhere. Calibrates a
    per-user baseline from real MediaPipe Pose readings, then scores
    every subsequent frame's deviation from that baseline -- never
    from one universal/hard-coded threshold that assumes identical
    body proportions/camera placement for every user.

    Public surface intentionally mirrors the previous version
    (calibrate(), update(), stable_state, last_debug) so main.py and
    everything else that already integrates with PostureTracker needs
    no changes beyond the import list at the top of the calling file.
    """

    def __init__(self):
        self.baseline = None  # dict of calibrated metric baselines, or None until calibrate() finishes
        self._streak_state = None
        self._streak_count = 0
        self.stable_state = UNKNOWN
        self._deviation_window = deque(maxlen=POSTURE_SMOOTHING_WINDOW)
        self._calibration_samples = []
        self._last_seen_at = None  # wall-clock time landmarks were last reliably found
        # Populated on every update() call -- read by the optional
        # debug mode in main.py, otherwise unused.
        self.last_debug = None

    # ---- calibration ----

    def calibrate(self, frame) -> bool:
        """
        Call once per frame at session start while the user sits in
        their normal good posture -- main.py calls this in a loop
        until it returns True (target 5-10s wall-clock, governed by
        POSTURE_CALIBRATION_SAMPLES and the caller's own poll cadence).
        Invalid/low-confidence frames are skipped, not counted, so a
        momentary tracking glitch during calibration doesn't skew the
        baseline. The baseline is the MEDIAN of the valid samples.
        """
        pts = _extract_landmarks(frame)
        if not pts.ok:
            return False

        self._calibration_samples.append(_posture_metrics(pts))
        if len(self._calibration_samples) < POSTURE_CALIBRATION_SAMPLES:
            return False

        self.baseline = {
            key: statistics.median(s[key] for s in self._calibration_samples)
            for key in ("head_drop", "shoulder_tilt_deg")
        }

        self._streak_state = None
        self._streak_count = 0
        self._deviation_window.clear()
        self._last_seen_at = time.time()
        self.stable_state = GOOD
        return True

    @property
    def calibration_progress(self) -> float:
        """0..1 fraction of calibration samples collected so far, for
        the web UI's calibration progress bar. 1.0 once baseline is
        locked in."""
        if self.baseline is not None:
            return 1.0
        return min(1.0, len(self._calibration_samples) / POSTURE_CALIBRATION_SAMPLES)

    def reset_calibration(self):
        """Discards any calibration in progress/completed so a new
        session can calibrate fresh. Does not touch debounce state --
        callers that want a fully clean tracker should just construct
        a new PostureTracker() instead; this exists for the narrower
        case of retrying calibration within the same session attempt."""
        self.baseline = None
        self._calibration_samples = []

    # ---- per-frame update ----

    def _deviation_score(self, metrics: dict) -> float:
        """
        Combines the two nose/shoulder-derived measurements into one
        deviation score against the calibrated baseline. Each term is
        expressed in "how far past a normal, comfortable range" units
        so they can be summed meaningfully:
          - head_drop is already shoulder-width-normalized, so its
            delta from baseline is compared directly against the
            configured sensitivity fractions.
          - shoulder_tilt delta is in degrees, scaled down to roughly
            the same units as head_drop so it can't dominate the score
            just because degrees are numerically larger than a
            shoulder-width ratio.
        """
        head_delta = metrics["head_drop"] - self.baseline["head_drop"]
        tilt_delta = metrics["shoulder_tilt_deg"] - self.baseline["shoulder_tilt_deg"]

        # Degrees-per-unit scaling: ~30 degrees of shoulder-tilt
        # deviation contributes roughly as much as the full "full
        # slouch" head-drop threshold does, so a bad-posture read can
        # come from a forward/dropped head OR a lopsided shoulder
        # line, not head position alone.
        DEG_SCALE = 30.0
        score = (
            max(0.0, head_delta)  # only forward/DOWN head movement counts as worse posture
            + abs(tilt_delta) / DEG_SCALE * POSTURE_SENSITIVITY["full"]
        )
        return score

    def _raw_state_for_score(self, score: float) -> str:
        if score > POSTURE_SENSITIVITY["full"]:
            return SLOUCH
        if score > POSTURE_SENSITIVITY["slight"]:
            return SLIGHT_SLOUCH
        return GOOD

    def update(self, frame) -> str:
        """
        Processes one frame and returns the current STABLE posture
        state (GOOD, SLIGHT_SLOUCH, SLOUCH, AWAY, UNKNOWN).

        Decision order, matching the required spec exactly:
          1. Person reliably present? (landmarks found this frame, OR
             found recently enough to still be within the away-grace
             window) -- if not, AWAY.
          2. Nose + both shoulders visible but no calibrated baseline
             yet? UNKNOWN.
          3. Compare smoothed deviation score to the calibrated
             baseline -> GOOD / SLIGHT_SLOUCH / SLOUCH.

        A detected person is NEVER, by itself, treated as good
        posture -- step 3 only ever runs after steps 1 and 2 pass. No
        hip landmark is read or used at any point in this method.
        """
        pts = _extract_landmarks(frame)
        now = time.time()

        if pts.ok:
            self._last_seen_at = now

        # --- Step 1: presence ---
        # Momentary tracking loss (one bad frame) must not immediately
        # flip to AWAY -- only sustained absence should. If landmarks
        # were seen recently enough (within the grace window), presence
        # still holds even though *this* frame's read failed.
        recently_seen = (
            self._last_seen_at is not None
            and (now - self._last_seen_at) <= POSTURE_AWAY_GRACE_SECONDS
        )

        if not pts.ok and not recently_seen:
            raw_state = AWAY
            self._deviation_window.clear()
        elif not pts.ok:
            # Landmarks missing this frame, but still within the grace
            # window -- not confidently present OR absent. Reported as
            # UNKNOWN rather than silently reusing the last posture
            # reading, so a sustained miss still visibly trends toward
            # AWAY once the grace window expires, per spec: never
            # assume GOOD just because we can't currently tell.
            raw_state = UNKNOWN
        elif self.baseline is None:
            # --- Step 2: landmarks fine, but never calibrated ---
            raw_state = UNKNOWN
        else:
            # --- Step 3: compare against calibrated baseline ---
            metrics = _posture_metrics(pts)
            raw_score = self._deviation_score(metrics)
            self._deviation_window.append(raw_score)
            smoothed_score = statistics.median(self._deviation_window)
            raw_state = self._raw_state_for_score(smoothed_score)

            self.last_debug = {
                "head_drop": round(metrics["head_drop"], 4),
                "shoulder_tilt_deg": round(metrics["shoulder_tilt_deg"], 2),
                "deviation_score": round(smoothed_score, 4),
                "state": raw_state,
            }

        # --- Debounce / hysteresis (two-tier: smoothing above +
        # consecutive-frame streak here) ---
        if raw_state == self._streak_state:
            self._streak_count += 1
        else:
            self._streak_state = raw_state
            self._streak_count = 1

        # AWAY is reported immediately once the grace window has
        # actually expired (presence is time-critical and, by that
        # point, already represents several seconds of sustained
        # absence -- see POSTURE_AWAY_GRACE_SECONDS). UNKNOWN and
        # GOOD/SLIGHT_SLOUCH/SLOUCH states still require the
        # consecutive-frame streak, so a single missed/noisy frame
        # can't flip the reported state on its own -- this is also
        # what makes SLOUCH -> SLIGHT_SLOUCH -> GOOD a gradual step-
        # down as posture improves, rather than an instant jump.
        if raw_state == AWAY:
            self.stable_state = raw_state
        elif self._streak_count >= POSTURE_CONSECUTIVE_FRAMES:
            self.stable_state = raw_state

        return self.stable_state
