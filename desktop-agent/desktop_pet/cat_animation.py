"""
Frame-sequence loading and playback for the cat sprite.

Each state under assets/cat/<state>/ is a numbered PNG sequence
(frame_000.png, frame_001.png, ...) extracted from the reference cat's
sprite sheet, all real frames of the same cat (see the extraction
notes in assets/cat/ -- idle, walk, enter, exit, stare, peek, paw,
block, expressions/annoyed, expressions/smug, satisfied, and
media/{pause,play,rewind,forward} all have real frames). If a
particular state's folder is ever missing or emptied (e.g. someone
deletes a folder, or a future state gets added without art yet), this
falls back to the idle sequence rather than crashing or drawing
nothing -- CatWindow logs a CAT_ASSET_FALLBACK event when that
happens so it's visible, not silent.

Frames must be composited onto the SAME colorkey used by the overlay
window's -transparentcolor (see cat_window.py) before being handed to
Tk -- Tk's PhotoImage does not do real alpha blending against an
arbitrary desktop background, only against a flat window background,
so a PNG with soft/anti-aliased alpha edges needs its edge pixels
pre-blended onto that colorkey or they'll show a faint fringe.

Must be constructed on the same thread as the Tk root that will
display the resulting PhotoImages (Tk's rule, not this module's).
"""

import os
import glob

try:
    from PIL import Image, ImageTk, ImageFilter
    _PIL_AVAILABLE = True
except Exception:
    _PIL_AVAILABLE = False

ASSETS_ROOT = os.path.join(os.path.dirname(__file__), "assets", "cat")
FALLBACK_STATE = "idle"


def _fit_and_composite(im: "Image.Image", canvas_size, colorkey_rgb, alpha_threshold=140) -> "Image.Image":
    """Scales im to FIT inside canvas_size preserving aspect ratio
    (never distorting the cat -- the source frames have real,
    differing aspect ratios: walking poses are wide/short, sitting
    poses are narrower/taller, peek crops are odd shapes), centers it
    on a canvas_size canvas, then flattens onto a solid background
    color so the window's -transparentcolor color-key can key it out.

    The source PNGs have soft, anti-aliased edges (partial alpha, not
    just 0/255). Tk's -transparentcolor is a binary chroma-key: only
    pixels that are an EXACT match to the key color become
    transparent. A naive alpha_composite() straight onto the key color
    blends those soft edge pixels toward the key color without fully
    replacing them, leaving a visible fringe of the key color around
    the whole silhouette. Fix: snap each pixel's alpha to fully-opaque
    or fully-transparent before flattening, and erode the opaque
    region by 1px so no partially-blended rim pixel can slip through
    right at the threshold boundary. This trades a barely-visible 1px
    of edge softness for a clean silhouette with no colored halo."""
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    cw, ch = canvas_size
    scale = min(cw / im.width, ch / im.height)
    new_w = max(1, int(im.width * scale))
    new_h = max(1, int(im.height * scale))
    resized = im.resize((new_w, new_h), Image.LANCZOS)

    r, g, b, a = resized.split()
    lut = [255 if i >= alpha_threshold else 0 for i in range(256)]
    a_hard = a.point(lut)
    a_eroded = a_hard.filter(ImageFilter.MinFilter(3))
    hardened = Image.merge("RGBA", (r, g, b, a_eroded))

    bg = Image.new("RGBA", canvas_size, colorkey_rgb + (255,))
    offset = ((cw - new_w) // 2, (ch - new_h))  # bottom-anchored: paws sit on the same ground line across every frame/state
    bg.alpha_composite(hardened, dest=offset)
    return bg.convert("RGB")


def _frame_paths(state: str):
    parts = state.split("/")  # allows nested states like "media/pause"
    folder = os.path.join(ASSETS_ROOT, *parts)
    return sorted(glob.glob(os.path.join(folder, "frame_*.png")))


def state_has_real_frames(state: str) -> bool:
    return len(_frame_paths(state)) > 0


class CatAnimation:
    """Loads and holds one state's frame sequence as Tk PhotoImages.
    Cheap to construct per-state and cache -- 40 frames at 160px wide
    is a small amount of memory, no need for lazy per-frame decoding."""

    def __init__(self, state: str, colorkey_rgb, size=None, master=None):
        self.state = state
        self.used_fallback = False
        self.frames = []  # list[ImageTk.PhotoImage]
        self.available = False

        if not _PIL_AVAILABLE:
            return

        paths = _frame_paths(state)
        if not paths:
            paths = _frame_paths(FALLBACK_STATE)
            self.used_fallback = state != FALLBACK_STATE
        if not paths:
            return  # no idle frames either -- caller must handle gracefully

        try:
            canvas_size = size or (200, 200)
            for p in paths:
                im = Image.open(p)
                flat = _fit_and_composite(im, canvas_size, colorkey_rgb)
                # master= ties each PhotoImage to the specific Tk
                # interpreter it will be drawn on. CatWindow runs its
                # own Tk() root on a dedicated background thread,
                # separate from any other Tk/Toplevel in the process --
                # without master=, PhotoImage binds to whatever
                # default root tkinter finds (which may be the wrong
                # interpreter, or none yet), and frames silently fail
                # to render even though loading itself doesn't raise.
                self.frames.append(ImageTk.PhotoImage(flat, master=master))
            self.available = len(self.frames) > 0
        except Exception as e:
            self.frames = []
            self.available = False
            print(f"[cat_animation] CatAnimation load FAILED for state={state!r}: {e!r}")
            import traceback
            traceback.print_exc()

    def frame_count(self) -> int:
        return len(self.frames)

    def frame_at(self, index: int):
        if not self.frames:
            return None
        return self.frames[index % len(self.frames)]
