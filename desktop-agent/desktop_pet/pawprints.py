"""
Paw print effect -- a separate visual layer from the cat sprite
itself, per the integration spec (section 10). Draws small marks on a
Tk Canvas at a given (x, y), then fades and removes each one on its
own timer. Purely cosmetic and temporary: nothing here ever writes to
disk or persists between appearances, so there's no risk of "leaving
marks" on the user's screen after the cat is gone.

Must be driven from the same Tk thread as the canvas it draws on
(root.after is not thread-safe to call from elsewhere).
"""

# Fill color steps used to fade a print out without real alpha
# blending (Tk canvas items don't support partial transparency
# directly) -- interpolates from an ink-brown toward the window's own
# background color over a few steps, which reads as a fade against a
# flat colorkey background.
_FADE_STEPS = 5


class PawprintLayer:
    def __init__(self, canvas, colorkey_hex, lifetime_ms=1400, base_opacity_steps=_FADE_STEPS):
        self.canvas = canvas
        self.colorkey_hex = colorkey_hex
        self.lifetime_ms = lifetime_ms
        self.steps = max(2, base_opacity_steps)
        self._active = []  # list of canvas item ids, for bulk clear()

    def spawn(self, x: int, y: int, flip: int = 1, rotation_deg: float = 0.0):
        """Draws one paw print centered at (x, y). flip=-1 mirrors it
        (so prints look consistent with the direction the cat is
        currently facing). rotation_deg is a small cosmetic tilt so a
        line of prints doesn't look perfectly mechanical."""
        r = 5
        toe_offsets = [(-4, -6), (0, -8), (4, -6)]
        pad_color = self._blend(0)
        item_ids = [self.canvas.create_oval(x - r, y - r * 0.7, x + r, y + r * 0.7,
                                             fill=pad_color, outline="")]
        for ox, oy in toe_offsets:
            ox *= flip
            item_ids.append(self.canvas.create_oval(
                x + ox - 2, y + oy - 2, x + ox + 2, y + oy + 2,
                fill=pad_color, outline=""))
        self._active.append(item_ids)
        self._schedule_fade(item_ids, step=0)

    def _blend(self, step: int) -> str:
        # step 0 = full ink color, step == self.steps = fully background
        ink = (95, 74, 58)
        bg = self._hex_to_rgb(self.colorkey_hex)
        t = min(1.0, step / self.steps)
        rgb = tuple(int(ink[i] + (bg[i] - ink[i]) * t) for i in range(3))
        return "#%02x%02x%02x" % rgb

    @staticmethod
    def _hex_to_rgb(hexcolor: str):
        hexcolor = hexcolor.lstrip("#")
        return tuple(int(hexcolor[i:i + 2], 16) for i in (0, 2, 4))

    def _schedule_fade(self, item_ids, step: int):
        interval = max(30, self.lifetime_ms // self.steps)
        self.canvas.after(interval, self._fade_step, item_ids, step)

    def _fade_step(self, item_ids, step: int):
        step += 1
        color = self._blend(step)
        try:
            for iid in item_ids:
                self.canvas.itemconfigure(iid, fill=color)
        except Exception:
            return  # canvas/window already gone -- nothing to clean up
        if step >= self.steps:
            self._remove(item_ids)
        else:
            self._schedule_fade(item_ids, step)

    def _remove(self, item_ids):
        try:
            for iid in item_ids:
                self.canvas.delete(iid)
        except Exception:
            pass
        if item_ids in self._active:
            self._active.remove(item_ids)

    def clear_all(self):
        """Immediately removes every active print -- used when the
        cat exits so nothing lingers after CAT MODE ends."""
        for item_ids in list(self._active):
            self._remove(item_ids)
