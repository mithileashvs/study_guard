"""
Watches which window is currently in focus on Windows.

This module is deliberately narrow: it only knows how to (a) ask the
OS which window is focused, and (b) reduce a title down to a short,
display-safe app label. It used to also decide whether a window was a
"distraction" via flat keyword matching (e.g. "if 'youtube' in
title..."), but that logic wasn't context-aware -- YouTube used for a
lecture and YouTube used for entertainment looked identical to it.
That decision now lives in session_context.py, which knows about the
current study session (subject, allowed apps, study keywords) and can
tell the two apart. See session_context.classify_window().
"""

import pygetwindow as gw


def get_active_window_title() -> str:
    """
    Returns the title of the currently focused window, or an empty
    string if it can't be determined (e.g. desktop has focus).
    """
    try:
        active = gw.getActiveWindow()
        if active is not None and active.title:
            return active.title
    except Exception:
        # pygetwindow can occasionally throw on some window types;
        # fail safe rather than crashing the whole monitor.
        pass
    return ""


def get_app_label(window_title: str) -> str:
    """
    Reduces a window title down to a short, display-safe app label for
    the live dashboard (e.g. "Study Guard - main.py" -> "Study Guard").
    Same privacy rule as get_distraction_category: this is for on-screen
    display only, is never written to session_log.csv, and never
    includes search terms/document names/chat contents -- just the
    text before the first separator, which is almost always the app
    or window name most programs put first.
    """
    if not window_title:
        return ""
    for sep in (" - ", " | ", " \u2014 "):  # " - ", " | ", " — "
        if sep in window_title:
            return window_title.split(sep)[0].strip()[:40]
    return window_title.strip()[:40]
