"""
The cat's actual on-screen window.

Built with tkinter, deliberately -- NOT a new PySide6/Qt dependency.
The project's existing companion_overlay.py already solved transparent,
frameless, always-on-top, layered-window overlays on Windows with
tkinter (see its docstring for the two bugs that took real effort to
fix: -transparentcolor needing update_idletasks() first, and the
inverted alpha-fade condition). Bringing in a second GUI toolkit would
duplicate that solved problem, add a heavy new dependency, and risk two
competing event loops for no behavioral benefit -- exactly what
section 28 of the integration spec ("do not overengineer... do not
introduce unnecessary frameworks") asks not to do. This module reuses
the same thread/queue pattern as CompanionOverlay and IS the cat's
window; companion_overlay.py's plain message bubble is unchanged and
still used for nothing but the moment before this module takes over
at the "all 3 notifications sent" escalation point.

Threading model (same rule as companion_overlay.py): this class runs
its own dedicated thread with its own Tk root. Every other thread
talks to it only through a thread-safe queue, polled via root.after().

Choreography model: start_intervention() enqueues a single "start"
command. The Tk-thread handler then runs the whole multi-step sequence
itself (enter -> walk -> pawprints -> stop & stare -> level action ->
idle hold) using chained root.after() calls -- no cross-thread
step-by-step calls are needed for a single sequence. Every scheduled
step is tagged with a "generation" counter; if a new command
(escalate, or stop for return-to-study) arrives, the generation is
bumped and any in-flight stale step silently no-ops instead of
fighting the new one. This is the same idea InterventionManager
already uses for the 3-stage notification cadence, applied to a
window's internal timers instead of wall-clock elapsed time.
"""

import queue
import random
import threading
import traceback

try:
    import tkinter as tk
    _TK_AVAILABLE = True
except Exception:
    _TK_AVAILABLE = False

from desktop_pet.cat_animation import CatAnimation
from desktop_pet.pawprints import PawprintLayer
from desktop_pet import cat_state as cs

_TRANSPARENT_KEY = "#FF00FE"
# Canvas big enough for the widest real frame (walk poses, ~172x151 at
# native res) with headroom -- every state's frames are aspect-fit and
# bottom-anchored onto this same canvas by CatAnimation, so paws land
# on a consistent ground line no matter which state is playing.
_SPRITE_SIZE = (200, 200)
_FRAME_MS = 140          # playback speed for multi-frame sequences (all real states have 4-6 frames now, not a smooth 40-frame loop, so this is slower than a video-style fps -- more like a held-pose flipbook)
_WALK_STEP_MS = 16
_WALK_SPEED_PX = 6
_PAWPRINT_EVERY_PX = 26
_GROUND_MARGIN = 40

# BUGFIX (cat entering/leaving between every media action): this used
# to be a pool of random 1-2 action combos, one of which was picked
# per escalation trigger -- so each re-trigger (a fresh enter->exit
# cycle) only ever did ONE of pause/rewind/forward, which is exactly
# what made it look like the cat entered, did a single action, left,
# then re-entered for the next one. The required behavior is ONE
# continuous on-screen visit that runs pause -> rewind -> forward ->
# next in order, then leaves once. "next" reuses the "forward" gesture
# artwork (no separate next-video frames exist) but fires
# MediaController.next_video() for real, logged distinctly.
_ACTION_SEQUENCES = [
    ["pause", "rewind", "forward", "next"],
]
_ANIM_FOR_ACTION = {
    "pause": "media/pause",
    "play": "media/play",
    "rewind": "media/rewind",
    "forward": "media/forward",
    "next": "media/forward",
}
_HOLD_BEFORE_EXIT_MS = 2200  # WAIT step: a few seconds before the cat leaves


def _log(event: str, log_event_fn=None, session_id=None, **details):
    detail_str = " ".join(f"{k}={v}" for k, v in details.items())
    print(f"[cat_window] {event} {detail_str}".rstrip())
    if log_event_fn is not None and session_id is not None:
        try:
            value = ",".join(f"{k}={v}" for k, v in details.items())[:200]
            log_event_fn(session_id, event, value=value)
        except Exception:
            pass


class CatWindow:
    def __init__(self, session_id=None, log_event_fn=None, media_controller=None,
                 max_intervention_seconds=90):
        self.available = _TK_AVAILABLE
        self.session_id = session_id
        self._log_event_fn = log_event_fn
        self.media_controller = media_controller
        self.max_intervention_ms = int(max_intervention_seconds * 1000)

        self._queue = queue.Queue()
        self._thread = None
        self._ready = threading.Event()
        self._started_ok = False

        self._root = None
        self._win = None
        self._canvas = None
        self._pawprints = None
        self._sprite_item = None

        self._anims = {}          # state name -> CatAnimation (lazy, cached)
        self._gen = 0              # generation counter for interruption
        self._facing = 1           # 1 = right, -1 = left
        self._x = 0
        self._y = 0
        self._playing_state = None
        self._timeout_after_id = None

        if not _TK_AVAILABLE:
            _log("CAT_WINDOW_ERROR", self._log_event, self.session_id, reason="tkinter_not_importable")

    # ---- lifecycle (safe to call from any thread) ----

    def start(self) -> bool:
        if not self.available:
            return False
        if self._thread is not None:
            return self._started_ok
        self._thread = threading.Thread(target=self._run, daemon=True, name="cat-window")
        self._thread.start()
        ready = self._ready.wait(timeout=5)
        if not ready:
            _log("CAT_WINDOW_ERROR", self._log_event, self.session_id, reason="init_timed_out_after_5s")
            self.available = False
            self._started_ok = False
        return self._started_ok

    def stop(self):
        """Full shutdown -- used when Study Guard itself is exiting."""
        if not self.available or self._thread is None:
            return
        self._queue.put(("shutdown", None))
        self._thread.join(timeout=2)

    # ---- thread-safe command API used by CatController ----

    def command(self, name: str, payload=None):
        if not (self.available and self._started_ok):
            raise RuntimeError("cat window not available/started")
        self._queue.put((name, payload))

    # ---- Tk-thread internals ----

    def _log_event(self, session_id, event_name, **kwargs):
        from logger import log_event
        log_event(session_id, event_name, **kwargs)

    def _run(self):
        try:
            self._root = tk.Tk()
            self._root.withdraw()
            self._build_window()
            self._started_ok = True
        except Exception:
            self._started_ok = False
            self.available = False
            _log("CAT_WINDOW_ERROR", self._log_event, self.session_id, where="build_window")
            traceback.print_exc()
            self._ready.set()
            return

        self._ready.set()
        self._root.after(30, self._poll_queue)
        try:
            self._root.mainloop()
        except Exception:
            self.available = False
            _log("CAT_WINDOW_ERROR", self._log_event, self.session_id, where="mainloop")
            traceback.print_exc()

    def _build_window(self):
        win = tk.Toplevel(self._root)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.update_idletasks()

        try:
            win.attributes("-transparentcolor", _TRANSPARENT_KEY)
            win.configure(bg=_TRANSPARENT_KEY)
            self._transparent = True
        except tk.TclError:
            self._transparent = False
            win.configure(bg="#1a1a1a")
            _log("CAT_WINDOW_ERROR", self._log_event, self.session_id,
                 where="transparentcolor", note="falling back to opaque background")

        w, h = _SPRITE_SIZE
        canvas = tk.Canvas(win, width=w, height=h, bg=_TRANSPARENT_KEY, highlightthickness=0)
        canvas.pack()
        self._pawprints = PawprintLayer(canvas, _TRANSPARENT_KEY)

        self._win = win
        self._canvas = canvas

    def _get_anim(self, state: str) -> CatAnimation:
        if state not in self._anims:
            anim = CatAnimation(state, colorkey_rgb=(255, 0, 254), size=_SPRITE_SIZE, master=self._root)
            self._anims[state] = anim
            if anim.available and anim.used_fallback:
                _log("CAT_ASSET_FALLBACK", self._log_event, self.session_id,
                     requested_state=state, using="idle")
        return self._anims[state]

    def _screen_size(self):
        return self._root.winfo_screenwidth(), self._root.winfo_screenheight()

    def _place(self, x, y):
        self._x, self._y = x, y
        w, h = _SPRITE_SIZE
        try:
            self._win.geometry(f"{w}x{h}+{int(x)}+{int(y)}")
        except tk.TclError:
            pass

    def _draw_frame(self, state: str, frame_idx: int, scale_bump=1.0, tilt_deg=0):
        anim = self._get_anim(state)
        if not anim.available:
            return
        img = anim.frame_at(frame_idx)
        self._canvas.delete("sprite")
        w, h = _SPRITE_SIZE
        cx, cy = w // 2, h // 2
        # Horizontal flip is done by mirroring the canvas draw, not the
        # source image, so we only ever decode each PNG once.
        anchor_img = img
        item = self._canvas.create_image(cx, cy, image=anchor_img, tags="sprite")
        if self._facing < 0:
            self._canvas.scale(item, cx, cy, -1, 1)
        if scale_bump != 1.0:
            self._canvas.scale(item, cx, cy, scale_bump, scale_bump)

    def _bump_generation(self) -> int:
        self._gen += 1
        return self._gen

    # ---- queue dispatch ----

    def _poll_queue(self):
        try:
            while True:
                cmd, payload = self._queue.get_nowait()
                if cmd == "shutdown":
                    self._shutdown_now()
                    return
                elif cmd == "start_intervention":
                    self._start_intervention(payload)
                elif cmd == "stop_intervention":
                    self._stop_intervention()
                elif cmd == "peek":
                    self._do_peek(payload)
                elif cmd == "show_expression":
                    self._show_expression(payload)
                elif cmd == "hard_hide":
                    self._hard_hide()
        except queue.Empty:
            pass
        except Exception:
            _log("CAT_WINDOW_ERROR", self._log_event, self.session_id, where="poll_queue")
            traceback.print_exc()
        self._root.after(30, self._poll_queue)

    # ---- choreography ----

    def _start_intervention(self, payload):
        # BUGFIX (duplicate intervention threads/callbacks): if the cat
        # is already visible and mid-choreography, ignore a duplicate
        # start_intervention command instead of bumping the generation
        # and restarting -- that restart is exactly what could cut an
        # in-flight enter/media sequence and immediately begin a new
        # one, producing overlapping enter/exit cycles. One physical
        # visit stays fully owned by the run already in progress; nothing
        # re-enters until that run's own auto-exit/stop_intervention
        # completes and the window is withdrawn again.
        if self._win is not None and self._win.state() != "withdrawn":
            _log("CAT_INTERVENTION_ALREADY_ACTIVE_IGNORED", self._log_event, self.session_id)
            return

        level = payload.get("level", 1)
        message = payload.get("message", "")
        gen = self._bump_generation()

        if self._timeout_after_id:
            try:
                self._root.after_cancel(self._timeout_after_id)
            except Exception:
                pass
        self._timeout_after_id = self._root.after(self.max_intervention_ms, self._on_timeout, gen)

        sw, sh = self._screen_size()
        ground_y = sh - _SPRITE_SIZE[1] - _GROUND_MARGIN

        # Every call to start_intervention() runs the FULL choreography
        # (enter -> walk -> stare -> paw -> media action -> wait ->
        # repeat) for a single physical visit, only ending when
        # stop_intervention()/_on_timeout() plays the exit -- see
        # _hold_then_continue()/_continue_intervention() below. There used to be a
        # "continuing" fast-path here that skipped straight to
        # _run_level_action() for a re-trigger within the same
        # episode, on the assumption the cat was still on screen from
        # a previous call. In practice CAT_COOLDOWN_SECONDS (config.py,
        # 60s by default) is far longer than one full sequence
        # (~10-15s), so the cat has always already auto-exited and
        # hidden itself by the time a re-trigger arrives -- taking the
        # "continuing" branch against a hidden/withdrawn window was
        # exactly why the cat could end up appearing to freeze in an
        # idle pose instead of actually pawing at / interacting with
        # anything. Always doing a fresh entrance is simpler and
        # matches what actually happens at these timings.

        # STRICT movement rule: the cat always enters from the RIGHT
        # and always exits toward the LEFT, every single time -- no
        # alternating by level/parity. (Previously this alternated
        # edge by level%2, which meant a re-trigger could enter from
        # the LEFT, and the paired exit -- which mirrors self._facing
        # -- would then leave through the RIGHT. Both violate the
        # required RIGHT->ENTER / LEFT->EXIT contract.) facing=-1 means
        # "moving/looking toward the left", which is what a cat that
        # just walked in from the right edge should do.
        edge = "left"
        start_x = -_SPRITE_SIZE[0]
        self._facing = 1
        self._place(start_x, ground_y)
        self._playing_state = "enter"
        self._win.deiconify()
        # Re-assert -transparentcolor and force a geometry/paint pass
        # right before showing. On Windows, a Toplevel that was
        # withdrawn can lose the color-key transparency attribute (or
        # just not have it fully applied yet) by the time it's shown
        # again -- companion_overlay.py hit the same thing (see its
        # docstring). Cheap and idempotent, so just always do it here.
        if self._transparent:
            try:
                self._win.attributes("-transparentcolor", _TRANSPARENT_KEY)
            except tk.TclError:
                pass
        self._win.update_idletasks()
        self._win.lift()
        self._win.attributes("-topmost", True)
        _log("CAT_ENTERED", self._log_event, self.session_id, edge=edge, level=level)

        # Always entering from the left now, so the intervention/stare
        # position is always the same spot near center-left.
        target_x = sw * 0.42
        self._walk_to(target_x, ground_y, gen, state="enter",
                      on_done=lambda: self._stop_and_stare(gen, level, message))

    def _walk_to(self, target_x, y, gen, on_done, state="walk", dist_since_print=0, step_count=0):
        if gen != self._gen or self._win is None:
            return
        anim = self._get_anim(state)
        n = max(1, anim.frame_count())
        # Advance the walk-cycle frame roughly every 90ms of real time,
        # independent of the 16ms position-step rate -- these sequences
        # only have 4-6 frames, so stepping the frame every position
        # tick would flicker through the whole cycle in under 100ms.
        cycle_frame = (step_count * _WALK_STEP_MS // 90) % n
        self._draw_frame(state, cycle_frame)
        if step_count == 0:
            _log("CAT_WALKED", self._log_event, self.session_id, state=state)

        step = _WALK_SPEED_PX if self._facing >= 0 else -_WALK_SPEED_PX
        new_x = self._x + step
        arrived = (self._facing >= 0 and new_x >= target_x) or (self._facing < 0 and new_x <= target_x)
        if arrived:
            new_x = target_x
        self._place(new_x, y)

        dist_since_print += abs(step)
        if dist_since_print >= _PAWPRINT_EVERY_PX:
            dist_since_print = 0
            paw_x = self._x + _SPRITE_SIZE[0] // 2
            paw_y = self._y + _SPRITE_SIZE[1] - 14
            self._pawprints.spawn(paw_x, paw_y, flip=self._facing)

        if arrived:
            if on_done:
                on_done()
            return
        self._root.after(_WALK_STEP_MS, self._walk_to, target_x, y, gen, on_done,
                          state, dist_since_print, step_count + 1)

    def _play_sequence_once(self, state, gen, on_done, frame_delay=180, frame_idx=0):
        """Plays every frame of `state` in order, once, then calls
        on_done. Used for held-pose actions (stare, paw, block, media
        gestures, satisfied) where the real asset is a short flipbook
        rather than a smooth loop."""
        if gen != self._gen:
            return
        anim = self._get_anim(state)
        n = anim.frame_count()
        if n == 0:
            if on_done:
                on_done()
            return
        self._draw_frame(state, frame_idx)
        if frame_idx >= n - 1:
            if on_done:
                self._root.after(frame_delay, on_done)
            return
        self._root.after(frame_delay, self._play_sequence_once, state, gen, on_done,
                          frame_delay, frame_idx + 1)

    def _stop_and_stare(self, gen, level, message):
        if gen != self._gen:
            return
        _log("CAT_STARED", self._log_event, self.session_id, level=level)
        self._facing *= -1  # turn toward the (assumed-centered) user
        # frame_delay=380 (stare has 6 real frames) holds this pose for
        # roughly 2.3s -- within the "stare 2-4s" pacing this state is
        # meant to have, not just a blink-and-it's-gone flash.
        self._play_sequence_once("stare", gen, on_done=lambda: self._run_level_action(level, gen, message),
                                  frame_delay=380)

    def _run_level_action(self, level, gen, message):
        """STARE has already played by the time this runs. From here
        every level goes through PAW -> MEDIA_ACTION -> (occasional
        ANNOYED/SMUG) -> WAIT -> EXIT -- levels only vary the flavor
        (double-paw, an extra "block" prelude, which expression is
        more likely), never whether the cat actually interacts. That
        was the bug: the old version had levels 1-2 fall straight
        through to an idle hold with no paw/media action at all, which
        is what made the cat look permanently stuck once it arrived."""
        if gen != self._gen:
            return
        _log("CAT_LEVEL_ACTION", self._log_event, self.session_id, level=level)

        def to_media():
            self._do_media_action(gen, level)

        if level >= cs.LEVEL_BLOCK_SCREEN:
            _log("CAT_BLOCKED", self._log_event, self.session_id)
            self._play_sequence_once("block", gen,
                                      on_done=lambda: self._paw_then(gen, to_media, double=True),
                                      frame_delay=220)
        else:
            double = level >= cs.LEVEL_PAW_AT_SCREEN
            self._paw_then(gen, to_media, double=double)

    def _paw_then(self, gen, on_done, double=False):
        if gen != self._gen:
            return
        _log("CAT_PAWED", self._log_event, self.session_id, double=double)
        if double:
            self._play_sequence_once("paw", gen, on_done=lambda: self._play_sequence_once(
                "paw", gen, on_done=on_done, frame_delay=180))
        else:
            self._play_sequence_once("paw", gen, on_done=on_done, frame_delay=200)

    def _media_target_active(self) -> bool:
        """Re-verify, right before sending any real key, that the
        window currently in focus still looks like the YouTube tab
        that triggered this intervention. The distraction-monitor poll
        loop (main.py, every WINDOW_CHECK_INTERVAL seconds) already
        cancels the whole intervention via a generation bump as soon
        as it sees a recovered/different window, but that poll can be
        a couple of seconds stale relative to the exact moment a
        gesture's key press fires -- this is the direct, immediate
        check the integration spec asks for ("before performing ANY
        media action, verify the active window is still the
        distracting YouTube/browser activity"). Fails safe (False) on
        any error, including if pygetwindow isn't available at all."""
        try:
            from window_tracker import get_active_window_title
            return "youtube" in get_active_window_title().lower()
        except Exception:
            return False

    def _do_media_action(self, gen, level=1):
        if gen != self._gen:
            return
        sequence = random.choice(_ACTION_SEQUENCES)
        _log("CAT_ACTION_SEQUENCE", self._log_event, self.session_id, sequence="+".join(sequence))
        self._run_action_sequence(gen, sequence, 0, level)

    def _run_action_sequence(self, gen, sequence, idx, level):
        if gen != self._gen:
            return
        if idx >= len(sequence):
            self._maybe_react_then_wait(gen, level)
            return

        action = sequence[idx]
        anim_state = _ANIM_FOR_ACTION[action]
        mc = self.media_controller
        target_ok = self._media_target_active()
        available = mc is not None and mc.is_available() and target_ok

        def after_gesture():
            self._run_action_sequence(gen, sequence, idx + 1, level)

        if not available:
            reason = "target_mismatch" if (mc is not None and mc.is_available() and not target_ok) else "unavailable"
            _log("CAT_MEDIA_SKIPPED", self._log_event, self.session_id, action=action, reason=reason)
            self._play_sequence_once(anim_state, gen, on_done=after_gesture, frame_delay=200)
            return

        # Fire the (best-effort, unconfirmed -- see MediaController's
        # docstring) real action partway through the gesture rather
        # than before/after it, so the visual and the actual key press
        # land together.
        def fire_and_finish():
            if action == "pause":
                ok = mc.pause()
                _log("CAT_PAUSE_ACTION", self._log_event, self.session_id, sent=ok)
            elif action == "play":
                ok = mc.play()
                _log("CAT_PLAY_ACTION", self._log_event, self.session_id, sent=ok)
            elif action == "rewind":
                ok = mc.rewind(5)
                _log("CAT_REWIND_ACTION" if ok else "CAT_MEDIA_SKIPPED", self._log_event,
                     self.session_id, action=action, sent=ok)
            elif action == "forward":
                ok = mc.forward(5)
                _log("CAT_FORWARD_ACTION" if ok else "CAT_MEDIA_SKIPPED", self._log_event,
                     self.session_id, action=action, sent=ok)
            elif action == "next":
                ok = mc.next_video()
                _log("CAT_NEXT_VIDEO_ACTION" if ok else "CAT_MEDIA_SKIPPED", self._log_event,
                     self.session_id, action=action, sent=ok)
            after_gesture()

        self._play_sequence_once(anim_state, gen, on_done=fire_and_finish, frame_delay=200)

    def _maybe_react_then_wait(self, gen, level):
        """ANNOYED/SMUG step: shows up more often (and leans "smug",
        as if pleased with itself) the further this episode has
        escalated; lower levels are more likely to skip straight to
        the WAIT hold."""
        if gen != self._gen:
            return
        which = None
        if level >= cs.LEVEL_PAW_AT_SCREEN and random.random() < 0.6:
            which = "smug" if level >= cs.LEVEL_MEDIA_ACTION else "annoyed"
        if which:
            self._play_sequence_once(f"expressions/{which}", gen,
                                      on_done=lambda: self._hold_then_continue(gen, level), frame_delay=240)
        else:
            self._hold_then_continue(gen, level)

    def _hold_then_continue(self, gen, level, hold_ms=_HOLD_BEFORE_EXIT_MS):
        """WAIT step: a brief idle hold, then the cat stays on screen
        and keeps performing/annoying (loops back into the media
        action sequence) as long as this generation is still current --
        i.e. as long as nothing external (stop_intervention on
        return-to-study, or the max-duration timeout) has interrupted
        it. The cat must NOT leave on its own after one pass through
        pause/rewind/forward/next; only stop_intervention()/_on_timeout
        ever plays the EXIT animation."""
        if gen != self._gen:
            return
        self._playing_state = "idle"
        self._draw_frame("idle", 0)
        self._root.after(hold_ms, self._continue_intervention, gen, level)

    def _continue_intervention(self, gen, level):
        """One physical visit, indefinitely repeating its action
        sequence -- ONE enter already happened, and there is no exit
        here. The window only closes via _stop_intervention() (called
        externally the moment the distraction detector reports the
        user is back to studying) or the safety-net _on_timeout()."""
        if gen != self._gen or self._win is None:
            return
        self._do_media_action(gen, level)

    def _show_expression(self, payload):
        """Manual/test-only action (see CatController.annoyed()/smug()).
        Not part of the automatic escalation ladder -- the escalation
        levels use the pose sequences (stare/paw/block/media) directly,
        which already carry their own expression. This is for a caller
        that wants to show an expression on its own, independent of any
        movement, e.g. from a future non-cat-triggered UI hook."""
        payload = payload or {}
        which = payload.get("which", "annoyed")  # "annoyed" or "smug"
        gen = self._bump_generation()
        if self._win is None:
            return
        was_hidden = self._win.state() == "withdrawn"
        if was_hidden:
            self._win.deiconify()
            if self._transparent:
                try:
                    self._win.attributes("-transparentcolor", _TRANSPARENT_KEY)
                except tk.TclError:
                    pass
            self._win.update_idletasks()
            self._win.lift()
            self._win.attributes("-topmost", True)

        def restore():
            if was_hidden:
                self._win.withdraw()
            elif gen == self._gen:
                self._playing_state = "idle"
                self._draw_frame("idle", 0)

        self._play_sequence_once(f"expressions/{which}", gen, on_done=restore, frame_delay=250)

    def _do_peek(self, payload):
        """Manual/test-only action (see CatController.peek()) -- not
        part of the automatic escalation ladder. Slides partway in
        from an edge using the peek frames, holds, then retreats."""
        payload = payload or {}
        direction = payload.get("direction", "left")
        gen = self._bump_generation()
        sw, sh = self._screen_size()
        ground_y = sh - _SPRITE_SIZE[1] - _GROUND_MARGIN
        self._facing = 1 if direction == "left" else -1
        off_x = -_SPRITE_SIZE[0] if direction == "left" else sw
        peek_x = -_SPRITE_SIZE[0] * 0.45 if direction == "left" else sw - _SPRITE_SIZE[0] * 0.55
        self._place(off_x, ground_y)
        self._win.deiconify()
        if self._transparent:
            try:
                self._win.attributes("-transparentcolor", _TRANSPARENT_KEY)
            except tk.TclError:
                pass
        self._win.update_idletasks()
        self._win.lift()
        self._win.attributes("-topmost", True)

        def slide_in(step=0, steps=10):
            if gen != self._gen:
                return
            t = (step + 1) / steps
            x = off_x + (peek_x - off_x) * t
            self._place(x, ground_y)
            frames = self._get_anim("peek").frame_count()
            if frames:
                self._draw_frame("peek", min(step, frames - 1))
            if step < steps - 1:
                self._root.after(40, slide_in, step + 1, steps)
            else:
                self._root.after(1200, lambda: self._retreat(gen, off_x, ground_y))

        slide_in()

    def _retreat(self, gen, off_x, y, step=0, steps=10):
        if gen != self._gen or self._win is None:
            return
        x = self._x + (off_x - self._x) / max(1, (steps - step))
        self._place(x, y)
        if step < steps - 1 and abs(x - off_x) > 2:
            self._root.after(40, self._retreat, gen, off_x, y, step + 1, steps)
        else:
            self._win.withdraw()

    def _stop_intervention(self):
        gen = self._bump_generation()  # invalidates any in-flight step above
        if self._timeout_after_id:
            try:
                self._root.after_cancel(self._timeout_after_id)
            except Exception:
                pass
            self._timeout_after_id = None
        if self._win is None:
            return
        if self._win.state() == "withdrawn":
            # The cat isn't currently showing (e.g. timeout already
            # closed it) -- nothing on screen to animate. Without this
            # guard the window would briefly pop back in just to
            # immediately play its exit sequence again, a visible
            # flicker for no reason.
            self._playing_state = None
            return
        _log("CAT_SATISFIED", self._log_event, self.session_id)
        sw, sh = self._screen_size()
        # STRICT movement rule: exit is ALWAYS toward the RIGHT (cat
        # enters from the LEFT, so it always leaves out the opposite,
        # RIGHT edge) -- set facing explicitly rather than deriving it
        # from whatever the cat was last facing.
        self._facing = 1
        exit_x = sw

        def begin_exit():
            self._pawprints.clear_all()
            self._walk_to(exit_x, self._y, gen, state="exit",
                          on_done=lambda: self._finish_exit(gen))

        self._play_sequence_once("satisfied", gen, on_done=begin_exit, frame_delay=200)

    def _finish_exit(self, gen):
        _log("CAT_INTERVENTION_ENDED", self._log_event, self.session_id)
        if self._timeout_after_id:
            try:
                self._root.after_cancel(self._timeout_after_id)
            except Exception:
                pass
            self._timeout_after_id = None
        if self._win is not None:
            self._win.withdraw()
        self._playing_state = None

    def _on_timeout(self, gen):
        if gen != self._gen:
            return
        _log("CAT_INTERVENTION_TIMEOUT", self._log_event, self.session_id)
        self._stop_intervention()

    def _hard_hide(self):
        self._bump_generation()
        if self._timeout_after_id:
            try:
                self._root.after_cancel(self._timeout_after_id)
            except Exception:
                pass
            self._timeout_after_id = None
        if self._pawprints:
            self._pawprints.clear_all()
        if self._win is not None:
            self._win.withdraw()
        self._playing_state = None

    def _shutdown_now(self):
        self._bump_generation()
        try:
            if self._win is not None:
                self._win.destroy()
        except Exception:
            pass
        try:
            self._root.quit()
        except Exception:
            pass
