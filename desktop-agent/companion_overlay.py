"""
The cat companion's actual on-screen window.

Built with tkinter (Python's standard-library GUI toolkit -- no new
dependency, and it ships with the standard Windows Python installer,
which this project already targets exclusively via pygetwindow). A
borderless, always-on-top, click-through-ish little window near a
screen corner, showing a cat + a short message in a speech bubble.

Threading note: tkinter widgets may only be touched from the thread
that's running their Tk root's mainloop. This class runs its own
dedicated thread with its own Tk root, and every other thread talks to
it through a thread-safe queue (show/hide/stop commands), polled from
inside that thread via root.after(). Nothing here talks directly to
the distraction/session logic -- that's intervention_manager.py's job;
this module only knows how to display and hide itself.

Failure handling: if tkinter isn't importable, or window creation
fails for any reason (no display server, restricted environment,
etc.), `self.available` stays False and every method becomes a silent
no-op. Callers (intervention_manager.py) check `.available` and fall
back to a plain desktop notification instead -- the app must keep
running either way.

DEBUGGING NOTE (Day 2 bugfix): the overlay was silently failing to
appear because every exception path in this file swallowed its error
with no logging at all -- if _build_window() raised for any reason,
`available` quietly became False and the app fell back to plain
notifications with zero trace of why. Every except-block below now
logs via OVERLAY_ERROR (see _log()) instead. A second, independent bug
was also found and fixed: the alpha-fade line in _show_now() had the
condition backwards and was setting the window fully transparent
(alpha=0.0) on any platform where -transparentcolor isn't supported --
i.e. exactly the "window exists but is invisible" failure mode.
"""

import queue
import threading
import traceback

try:
    import tkinter as tk
    _TK_AVAILABLE = True
except Exception:
    _TK_AVAILABLE = False

from config import (
    COMPANION_WIDTH,
    COMPANION_HEIGHT,
    COMPANION_POSITION,
    COMPANION_ANIMATION_STEP_MS,
    INTERVENTION_DISPLAY_SECONDS,
    COMPANION_DEBUG,
)

CAT_EMOJI = "\U0001F431"
_BUBBLE_BG = "#FFF8E7"
_BUBBLE_BORDER = "#D8C9A3"
_TRANSPARENT_KEY = "#FF00FE"  # an unlikely color, used as the "see-through" key
_SLIDE_STEPS = 14


def _log(event: str, log_event_fn=None, session_id=None, **details):
    """
    Temporary diagnostic logging for the Day 2 overlay bugfix.
    Always prints to the console (cheap -- this only fires a handful of
    times per session, never per poll). Also writes to session_log.csv
    via the given log_event function when COMPANION_DEBUG is on, so the
    overlay's lifecycle shows up next to everything else in the log.
    """
    detail_str = " ".join(f"{k}={v}" for k, v in details.items())
    print(f"[companion_overlay] {event} {detail_str}".rstrip())
    if COMPANION_DEBUG and log_event_fn is not None and session_id is not None:
        try:
            value = ",".join(f"{k}={v}" for k, v in details.items())[:200]
            log_event_fn(session_id, event, value=value)
        except Exception:
            pass  # diagnostic logging must never itself crash the app


class CompanionOverlay:
    """One companion instance for the whole app -- main.py creates a
    single instance and shares it, so there's never more than one
    overlay window regardless of how many interventions fire."""

    def __init__(self, session_id=None):
        self.available = _TK_AVAILABLE
        self.session_id = session_id
        self._queue = queue.Queue()
        self._thread = None
        self._ready = threading.Event()
        self._started_ok = False
        self._root = None
        self._win = None
        self._msg_var = None
        self._hide_after_id = None
        self._can_fade = False
        self._transparent = False

        if not _TK_AVAILABLE:
            _log("OVERLAY_ERROR", self._log_event, session_id, reason="tkinter_not_importable")

    # ---- lifecycle (safe to call from any thread) ----

    def start(self) -> bool:
        """Launches the dedicated Tk thread. Returns True if the
        overlay is actually usable. Never raises -- any failure just
        leaves `self.available` False."""
        if not self.available:
            return False
        if self._thread is not None:
            return self._started_ok
        self._thread = threading.Thread(target=self._run, daemon=True, name="companion-overlay")
        self._thread.start()
        ready = self._ready.wait(timeout=5)
        if not ready:
            _log("OVERLAY_ERROR", self._log_event, self.session_id, reason="init_timed_out_after_5s")
            self.available = False
            self._started_ok = False
        return self._started_ok

    def stop(self):
        if not self.available or self._thread is None:
            return
        self._queue.put(("stop", None))
        self._thread.join(timeout=2)
        _log("OVERLAY_DESTROY")

    def show(self, message: str):
        """Thread-safe: queue a "show" command, processed on the
        overlay's own thread. IMPORTANT: this method used to be able to
        silently no-op (return with no error) if the window had never
        actually finished initializing, which let callers believe the
        companion was showing when it wasn't. It now raises RuntimeError
        in that case so intervention_manager.py's fallback-to-notify
        logic actually triggers, instead of silently doing nothing."""
        if not self.available:
            raise RuntimeError("overlay not available (tkinter missing or init failed)")
        if not self._started_ok:
            raise RuntimeError("overlay not started (call start() first, or it failed to start)")
        self._queue.put(("show", message))

    def hide(self):
        """Thread-safe immediate hide -- used both for the auto-hide
        timeout and for instant hide on focus recovery. Unlike show(),
        this stays a silent no-op when unavailable: hiding something
        that was never shown isn't an error worth surfacing."""
        if not (self.available and self._started_ok):
            return
        self._queue.put(("hide", None))

    # ---- Tk-thread internals ----

    def _log_event(self, session_id, event_name, **kwargs):
        # Lazy import to avoid a circular import at module load time
        # (logger.py has no dependency on this module, so this is safe).
        from logger import log_event
        log_event(session_id, event_name, **kwargs)

    def _run(self):
        _log("OVERLAY_CREATE", self._log_event, self.session_id, thread=threading.current_thread().name)
        try:
            self._root = tk.Tk()
            self._root.withdraw()  # the default root window is never shown
            self._build_window()
            self._started_ok = True
        except Exception:
            self._started_ok = False
            self.available = False
            _log("OVERLAY_ERROR", self._log_event, self.session_id, where="build_window")
            traceback.print_exc()
            self._ready.set()
            return

        _log("OVERLAY_CREATE", self._log_event, self.session_id, status="ok")
        self._ready.set()
        self._root.after(50, self._poll_queue)
        try:
            self._root.mainloop()
        except Exception:
            self.available = False
            _log("OVERLAY_ERROR", self._log_event, self.session_id, where="mainloop")
            traceback.print_exc()

    def _build_window(self):
        win = tk.Toplevel(self._root)
        win.withdraw()
        win.overrideredirect(True)   # no title bar/border
        win.attributes("-topmost", True)

        # -transparentcolor sets Windows' color-key layered-window
        # transparency. On some setups this attribute needs the window
        # to already have a real HWND to take effect reliably, so we
        # force realization first with update_idletasks() -- without
        # this, the call can silently no-op on some Windows machines
        # (the window would then just render as a solid magenta block,
        # or in the worst case fail to composite at all).
        win.update_idletasks()

        transparent = True
        try:
            win.attributes("-transparentcolor", _TRANSPARENT_KEY)
            win.configure(bg=_TRANSPARENT_KEY)
        except tk.TclError:
            # -transparentcolor isn't supported on every platform/WM
            # (mainly a Windows feature) -- fall back to a plain
            # opaque background rather than failing outright.
            transparent = False
            win.configure(bg=_BUBBLE_BG)
            _log("OVERLAY_ERROR", self._log_event, self.session_id,
                 where="transparentcolor", note="falling back to opaque background")

        frame = tk.Frame(win, bg=_BUBBLE_BG, highlightbackground=_BUBBLE_BORDER, highlightthickness=2)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        cat_label = tk.Label(frame, text=CAT_EMOJI, font=("Segoe UI Emoji", 34), bg=_BUBBLE_BG)
        cat_label.pack(side="left", padx=(12, 6), pady=12)

        self._msg_var = tk.StringVar(value="")
        msg_label = tk.Label(
            frame, textvariable=self._msg_var, font=("Segoe UI", 11),
            bg=_BUBBLE_BG, fg="#2B2B2B", wraplength=COMPANION_WIDTH - 90, justify="left",
        )
        msg_label.pack(side="left", padx=(6, 14), pady=12)

        try:
            win.attributes("-alpha", 1.0)
            self._can_fade = True
        except tk.TclError:
            self._can_fade = False

        self._transparent = transparent
        self._win = win

    def _poll_queue(self):
        try:
            while True:
                cmd, payload = self._queue.get_nowait()
                if cmd == "show":
                    self._show_now(payload)
                elif cmd == "hide":
                    self._hide_now()
                elif cmd == "stop":
                    self._root.quit()
                    return
        except queue.Empty:
            pass
        except Exception:
            _log("OVERLAY_ERROR", self._log_event, self.session_id, where="poll_queue")
            traceback.print_exc()
        self._root.after(50, self._poll_queue)

    def _target_xy(self, w, h):
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        margin = 24
        if COMPANION_POSITION == "bottom-left":
            return margin, sh - h - margin
        if COMPANION_POSITION == "top-right":
            return sw - w - margin, margin
        if COMPANION_POSITION == "top-left":
            return margin, margin
        return sw - w - margin, sh - h - margin  # bottom-right (default)

    def _show_now(self, message):
        try:
            if self._hide_after_id:
                try:
                    self._root.after_cancel(self._hide_after_id)
                except Exception:
                    pass
                self._hide_after_id = None

            self._msg_var.set(message)
            w, h = COMPANION_WIDTH, COMPANION_HEIGHT
            target_x, target_y = self._target_xy(w, h)
            _log("OVERLAY_POSITION", self._log_event, self.session_id, x=target_x, y=target_y, w=w, h=h)

            # Slide in from just off the corresponding screen edge -- a
            # small, deliberately simple animation (reliability over polish).
            sw = self._root.winfo_screenwidth()
            start_x = sw if target_x > sw / 2 else -w

            self._win.geometry(f"{w}x{h}+{start_x}+{target_y}")

            # BUGFIX: this used to read
            #   attributes("-alpha", 1.0 if self._transparent else 0.0)
            # which set alpha to 0.0 (fully invisible) on exactly the
            # platforms where -transparentcolor ISN'T supported -- i.e.
            # the overlay would "succeed" at showing a window with zero
            # opacity. There is no fade-in animation implemented, so the
            # only correct value here is always fully opaque.
            if self._can_fade:
                try:
                    self._win.attributes("-alpha", 1.0)
                except tk.TclError:
                    pass

            # Re-apply topmost/transparentcolor on every show, not just at
            # build time: Windows can silently drop layered-window
            # attributes across a withdraw()/deiconify() cycle, which
            # would otherwise make the SECOND appearance invisible even
            # though the FIRST one worked.
            if self._transparent:
                try:
                    self._win.attributes("-transparentcolor", _TRANSPARENT_KEY)
                except tk.TclError:
                    pass

            self._win.deiconify()
            self._win.lift()
            self._win.attributes("-topmost", True)

            _log("OVERLAY_SHOW", self._log_event, self.session_id, message=message[:40])

            self._animate_slide(start_x, target_x, target_y, w, h, step=0)

            self._hide_after_id = self._root.after(
                int(INTERVENTION_DISPLAY_SECONDS * 1000), self._hide_now
            )
        except Exception:
            _log("OVERLAY_ERROR", self._log_event, self.session_id, where="show_now")
            traceback.print_exc()

    def _animate_slide(self, start_x, target_x, y, w, h, step):
        if self._win is None:
            return
        progress = min(1.0, (step + 1) / _SLIDE_STEPS)
        x = int(start_x + (target_x - start_x) * progress)
        try:
            self._win.geometry(f"{w}x{h}+{x}+{y}")
        except tk.TclError:
            return
        if progress < 1.0:
            self._root.after(COMPANION_ANIMATION_STEP_MS, self._animate_slide, start_x, target_x, y, w, h, step + 1)

    def _hide_now(self):
        try:
            if self._hide_after_id:
                try:
                    self._root.after_cancel(self._hide_after_id)
                except Exception:
                    pass
                self._hide_after_id = None
            if self._win is None:
                return
            self._win.withdraw()
            _log("OVERLAY_HIDE", self._log_event, self.session_id)
        except Exception:
            _log("OVERLAY_ERROR", self._log_event, self.session_id, where="hide_now")
            traceback.print_exc()

