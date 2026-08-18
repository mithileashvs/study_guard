"""
MediaController -- an honest abstraction over "can we nudge whatever
media the user is currently playing".

READ THIS BEFORE CHANGING is_available()/play()/pause()/rewind()/forward():

There is no cross-application, cross-website API for controlling
arbitrary media on someone's machine, and this module still doesn't
attempt one. What changed from the previous revision: this project has
exactly one call site for all of these methods -- CatWindow.
_run_action_sequence() in desktop_pet/cat_window.py -- and that call
site now verifies, right before every single call, that the active
window title still contains "youtube" (see CatWindow.
_media_target_active()). Given that guarantee, it's no longer honest
to say "we can't target anything" -- we CAN target the page that's
actually focused, using YouTube's own in-page keyboard shortcuts
(the same keys a person's hand would press): 'k' for play/pause,
Left/Right arrow for a 5-second seek, and Shift+N for "next video".
These are sent as OS-level key events (ctypes/user32, stdlib only, no
new dependency) precisely because the active window is already
confirmed to be the YouTube tab -- this is not a blind, unscoped
keyboard-shortcut spray at whatever happens to have focus.

What this can genuinely do (all via the same "send an OS key event"
mechanism, never website automation or simulated mouse clicks):
  - play()/pause(): send YouTube's own 'k' shortcut, which toggles
    play/pause within the page.
  - rewind(seconds)/forward(seconds): send YouTube's Left/Right arrow
    shortcut, which seeks 5 seconds per press. The `seconds` argument
    is accepted for API clarity but a single call always sends exactly
    one press (YouTube's own shortcut granularity, not a configurable
    one) -- callers that want a bigger seek should call again, not
    expect a bigger jump from a bigger seconds= value.
  - next_video(): sends YouTube's Shift+N shortcut. This only does
    anything if YouTube actually has a next video queued (autoplay or
    a playlist) -- there is no way to detect that from outside the
    page, so a True return means the shortcut WAS sent, not that the
    video actually changed. This is the "next video when technically
    possible" the integration spec asks for: it's a real shortcut, not
    a fake.

What none of this can do, and callers must not assume:
  - Confirm anything actually happened. is_playing() returns None
    (unknown) always -- there is no generic "is media playing" query
    across arbitrary apps/sites without a much heavier UWP/SMTC
    integration this project doesn't have. play()/pause()/rewind()/
    forward()/next_video() all report whether the key press was SENT,
    never whether playback/position/video actually changed.
  - Target anything other than whatever window is currently focused.
    This class has no window-awareness of its own by design (see
    is_available()) -- targeting is entirely the caller's job, and
    CatWindow is the only caller, which re-checks the active window
    immediately before every single call here.
  - Anything destructive: nothing here ever closes an app, kills a
    process, or sends any key other than the five described above.
"""

import platform
import time

_IS_WINDOWS = platform.system() == "Windows"

# YouTube's own in-page keyboard shortcuts (not OS media keys) -- see
# module docstring for why this is safe to target now.
_VK_K = 0x4B        # play/pause
_VK_LEFT = 0x25     # seek back 5s
_VK_RIGHT = 0x27    # seek forward 5s
_VK_N = 0x4E        # next video (with Shift)
_VK_SHIFT = 0x10
_KEYEVENTF_KEYUP = 0x0002

_MIN_SECONDS_BETWEEN_ACTIONS = 1.0  # don't hammer the same key repeatedly


class MediaController:
    def __init__(self):
        self._last_action_at = 0.0
        self._user32 = None
        if _IS_WINDOWS:
            try:
                import ctypes
                self._user32 = ctypes.windll.user32
            except Exception:
                self._user32 = None

    def is_available(self) -> bool:
        """True only if we can plausibly send an OS-level key event at
        all. This is NOT a promise that YouTube (or anything) is the
        focused window -- see module docstring; that check is the
        caller's job, done fresh immediately before each call."""
        return _IS_WINDOWS and self._user32 is not None

    def is_playing(self):
        """Always None: there is no reliable, generic way to read
        current playback state across arbitrary apps/sites without a
        much heavier platform integration this project doesn't have.
        Callers must treat None as genuinely unknown, not as False."""
        return None

    def _send_key(self, vk: int, shift: bool = False) -> bool:
        if not self.is_available():
            return False
        now = time.time()
        if now - self._last_action_at < _MIN_SECONDS_BETWEEN_ACTIONS:
            return False
        try:
            if shift:
                self._user32.keybd_event(_VK_SHIFT, 0, 0, 0)
            self._user32.keybd_event(vk, 0, 0, 0)
            self._user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)
            if shift:
                self._user32.keybd_event(_VK_SHIFT, 0, _KEYEVENTF_KEYUP, 0)
            self._last_action_at = now
            return True
        except Exception:
            return False

    def play(self) -> bool:
        """Sends YouTube's 'k' play/pause shortcut. Returns whether
        the key press was SENT -- not whether anything actually
        started playing (unknowable; see module docstring). Only
        meaningful when the caller has verified the active window is
        actually YouTube (CatWindow always does)."""
        return self._send_key(_VK_K)

    def pause(self) -> bool:
        """Same 'k' shortcut as play() -- YouTube uses one key to
        toggle both, not separate play/pause keys. Returns whether the
        key press was sent, not confirmed."""
        return self._send_key(_VK_K)

    def rewind(self, seconds: int = 5) -> bool:
        """Sends YouTube's Left-Arrow "seek back 5s" shortcut once.
        `seconds` is accepted for API clarity but does not change the
        seek amount -- that's YouTube's own shortcut granularity.
        Reliable only when the YouTube player itself has keyboard
        focus (not a search box or comment field); there's no way to
        confirm that from outside the page, so a True return means the
        key WAS pressed, not that the video actually moved."""
        return self._send_key(_VK_LEFT)

    def forward(self, seconds: int = 5) -> bool:
        """Sends YouTube's Right-Arrow "seek forward 5s" shortcut
        once. Same caveats as rewind()."""
        return self._send_key(_VK_RIGHT)

    def next_video(self) -> bool:
        """Sends YouTube's Shift+N "next video" shortcut. Only
        actually advances anything if YouTube has a next video queued
        (autoplay or a playlist) -- undetectable from outside the
        page, so True means the shortcut was sent, not that the video
        changed. If the caller needs a guaranteed video change, this
        is the honest limit of what's implementable without page-level
        automation (out of scope -- see the project's integration
        notes)."""
        return self._send_key(_VK_N, shift=True)
