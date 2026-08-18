"""
Study session context: what the user is studying, which apps/sites are
allowed, and the layered decision system that classifies the current
window as ALLOWED / LIKELY STUDY / POTENTIAL DISTRACTION.

This replaces the old flat "if 'youtube' in title: distraction = True"
logic in window_tracker.py. That logic is intentionally gone -- YouTube,
and any other CONTENT_DEPENDENT_APPS, are judged by window title, not
by app name alone.

Decision tree (see README/DAY1 notes for the full picture):

    Is the window an explicitly-allowed, non-content-dependent app?
        YES -> ALLOW
    Is it a content-dependent app (e.g. YouTube)?
        YES -> does the title look like entertainment?    -> DISTRACTION
             -> does the title look study-related?          -> ALLOW (study)
             -> neither (ambiguous)                          -> POTENTIAL DISTRACTION
    Is it a known-distraction app (Instagram, Netflix, ...)?
        YES -> POTENTIAL DISTRACTION
    Does the title look study-related anyway?
        YES -> ALLOW (study)
        NO  -> POTENTIAL DISTRACTION (unknown window)

This is a transparent heuristic, not a perfect classifier -- it can be
fooled by a misleading window title, same as the old logic could.
"""

from dataclasses import dataclass, field

from config import (
    DISTRACTION_KEYWORDS,
    DISTRACTION_CONTENT_KEYWORDS,
    CONTENT_DEPENDENT_APPS,
    STUDY_KEYWORDS,
    DEFAULT_ALLOWED_APPS,
    ALLOWED_APP_ALIASES,
    STUDY_MODES,
    DEFAULT_STUDY_MODE,
)
from window_tracker import get_app_label

DEFAULT_SUBJECT = "General Study"


@dataclass
class StudySession:
    """
    Immutable-ish record of what the current session is about. Built
    once at startup (interactively or programmatically) and read by
    the distraction monitor on every poll.
    """

    subject: str
    mode: str
    allowed_apps: list = field(default_factory=list)   # lowercase strings
    study_keywords: list = field(default_factory=list)  # lowercase strings
    grace_period: int = STUDY_MODES[DEFAULT_STUDY_MODE]["grace_period"]

    def describe(self) -> str:
        return (
            f"Subject: {self.subject} | Mode: {self.mode} | "
            f"Allowed: {', '.join(self.allowed_apps) or '(none)'}"
        )


@dataclass
class ClassificationResult:
    is_distraction: bool
    label: str      # what to log/notify with -- app name or matched category
    reason: str      # short internal tag, useful for debugging/tests


def _match_any(text_lower: str, keywords) -> str:
    """Returns the first keyword found in text_lower, or "" if none match."""
    for kw in keywords:
        if kw and kw in text_lower:
            return kw
    return ""


def _default_study_keywords(subject: str, extra_keywords=None) -> list:
    """
    Builds the effective study-keyword list for a session: the generic
    defaults in config.py, plus every word in the subject name (so
    "Data Structures & Algorithms" alone contributes "data",
    "structures", "algorithms"), plus anything the user added.
    """
    words = set(STUDY_KEYWORDS)
    for token in subject.lower().replace("&", " ").replace("/", " ").split():
        token = token.strip(",.-")
        if len(token) > 2:
            words.add(token)
    if extra_keywords:
        words.update(k.strip().lower() for k in extra_keywords if k.strip())
    return sorted(words)


def create_session(subject=None, mode=None, allowed_apps=None, extra_keywords=None) -> StudySession:
    """
    Pure/programmatic session builder (no input() calls) -- used by
    prompt_for_session() below and directly by anything that wants to
    construct a session without a TTY (e.g. tests).
    """
    subject = (subject or DEFAULT_SUBJECT).strip() or DEFAULT_SUBJECT
    mode = (mode or DEFAULT_STUDY_MODE).strip().upper()
    if mode not in STUDY_MODES:
        mode = DEFAULT_STUDY_MODE

    apps = allowed_apps if allowed_apps else list(DEFAULT_ALLOWED_APPS)
    allowed_apps_lower = []
    for a in apps:
        a = a.strip().lower()
        if not a:
            continue
        # Expand each typed/short app name to every real window-title
        # variant it should also match (see ALLOWED_APP_ALIASES) -- a
        # plain substring match against just what the user typed missed
        # real title bars like "...- Visual Studio Code" for "VS Code".
        for variant in ALLOWED_APP_ALIASES.get(a, [a]):
            if variant not in allowed_apps_lower:
                allowed_apps_lower.append(variant)

    study_keywords = _default_study_keywords(subject, extra_keywords)

    return StudySession(
        subject=subject,
        mode=mode,
        allowed_apps=allowed_apps_lower,
        study_keywords=study_keywords,
        grace_period=STUDY_MODES[mode]["grace_period"],
    )


def prompt_for_session() -> StudySession:
    """
    Interactively asks the user to define the study session, with
    sensible defaults on every field (just press Enter to accept).
    Falls back to full defaults if input isn't available (e.g. running
    non-interactively) -- this must never crash the app.
    """
    print("Set up your study session (press Enter to accept the default).\n")

    def ask(prompt_text, default):
        try:
            raw = input(f"{prompt_text} [{default}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            raw = ""
        return raw or default

    subject = ask("Subject", DEFAULT_SUBJECT)

    mode_default = DEFAULT_STUDY_MODE
    mode_raw = ask("Study mode (STRICT / BALANCED / FLEXIBLE)", mode_default)
    mode = mode_raw.strip().upper() if mode_raw.strip().upper() in STUDY_MODES else mode_default

    apps_default = ", ".join(DEFAULT_ALLOWED_APPS)
    apps_raw = ask("Allowed apps/sites (comma-separated)", apps_default)
    allowed_apps = [a.strip() for a in apps_raw.split(",") if a.strip()]

    keywords_raw = ask("Extra study keywords (comma-separated, optional)", "")
    extra_keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]

    session = create_session(
        subject=subject,
        mode=mode,
        allowed_apps=allowed_apps,
        extra_keywords=extra_keywords,
    )
    print(f"\n{session.describe()}")
    print(f"Grace period: {session.grace_period}s\n")
    return session


def sync_roadmap_keywords(session: StudySession, roadmap_keywords: list) -> None:
    """Folds the active roadmap topic's keywords into the session's
    study_keywords in place (spec items 27/28). Additive and
    idempotent -- safe to call every poll with the latest list from
    roadmap_bridge.get_active_topic_keywords(). Never touches
    allowed_apps, so this can't globally allow a site/app -- it only
    feeds the existing content-dependent-app title heuristic in
    classify_window() below.
    """
    if not roadmap_keywords:
        return
    existing = set(session.study_keywords)
    new_words = [w for w in roadmap_keywords if w not in existing]
    if new_words:
        session.study_keywords = sorted(existing.union(new_words))


def classify_window(title: str, session: StudySession) -> ClassificationResult:
    """
    Runs the layered decision tree against the current window title
    for the given session. Returns whether this window currently
    counts as a (potential) distraction, plus a label safe to log
    (app name or matched category -- never the raw title, same
    privacy rule as the rest of the project).
    """
    if not title:
        return ClassificationResult(False, "", "no_active_window")

    title_lower = title.lower()
    app_label = get_app_label(title)

    content_dependent_match = _match_any(title_lower, CONTENT_DEPENDENT_APPS)
    if content_dependent_match:
        # App name alone (e.g. "YouTube") is ambiguous -- inspect the title.
        if _match_any(title_lower, DISTRACTION_CONTENT_KEYWORDS):
            return ClassificationResult(True, app_label or content_dependent_match.capitalize(), "content_entertainment_keyword")
        if _match_any(title_lower, session.study_keywords):
            return ClassificationResult(False, app_label or content_dependent_match.capitalize(), "content_study_keyword")
        # No clear signal either way -- treated as a potential
        # distraction per the decision tree (unknown -> potential),
        # even if the app itself is on the allowed list.
        return ClassificationResult(True, app_label or content_dependent_match.capitalize(), "content_ambiguous")

    allowed_match = _match_any(title_lower, session.allowed_apps)
    if allowed_match:
        return ClassificationResult(False, app_label or allowed_match.capitalize(), "explicitly_allowed")

    distraction_match = _match_any(title_lower, DISTRACTION_KEYWORDS)
    if distraction_match:
        return ClassificationResult(True, app_label or distraction_match.capitalize(), "known_distraction_app")

    if _match_any(title_lower, session.study_keywords):
        return ClassificationResult(False, app_label, "study_keyword_match")

    return ClassificationResult(True, app_label or "Unknown", "unknown_window")
