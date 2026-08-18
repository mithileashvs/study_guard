"""
Study Guard -- single-command launcher.

Run:
    python launcher.py

What this does, in order:
  1. If the frontend hasn't been built yet (frontend/dist is missing),
     runs `npm install` (first time only) and `npm run build` inside
     frontend/ so api_server.py has static files to serve.
  2. Opens the browser to the Study Guard web UI a couple seconds after
     starting main.py, once the API server has had time to come up.
  3. Runs main.py's own main() directly in this process -- there is
     still only ONE Python process, one webcam, one set of monitor
     threads; this file only adds "build the frontend first" and
     "open a browser tab" on top of what `python main.py` already does.

`python main.py` by itself still works exactly as before (it just
won't build the frontend for you or auto-open a browser tab) -- this
launcher is the convenience entry point STEP 16 asks for, not a
replacement requirement.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
# The frontend now lives at the repo root (../frontend, sibling of this
# desktop-agent/ folder) -- one shared source for both "Vercel builds
# and hosts it" and "the desktop agent builds it locally and serves it
# itself", instead of two separate copies.
FRONTEND_DIR = os.path.join(ROOT, "..", "frontend")
FRONTEND_DIST = os.path.join(FRONTEND_DIR, "dist")
FRONTEND_NODE_MODULES = os.path.join(FRONTEND_DIR, "node_modules")


def _npm_available() -> bool:
    from shutil import which
    return which("npm") is not None


def build_frontend() -> bool:
    """Builds the React frontend if it hasn't been built yet. Returns
    True if a built frontend is available (either just built, or
    already present) and False if it couldn't be built -- the caller
    still starts the backend either way (monitoring shouldn't be
    blocked on frontend tooling being available)."""
    if os.path.isfile(os.path.join(FRONTEND_DIST, "index.html")):
        return True

    if not _npm_available():
        print(
            "WARNING: npm not found -- cannot build the frontend automatically.\n"
            "Install Node.js/npm, then run:\n"
            f"    cd {FRONTEND_DIR} && npm install && npm run build\n"
            "Monitoring will still start, but the web UI won't be available "
            "until the frontend is built."
        )
        return False

    try:
        if not os.path.isdir(FRONTEND_NODE_MODULES):
            print("Installing frontend dependencies (first run only)...")
            subprocess.run(["npm", "install"], cwd=FRONTEND_DIR, check=True)

        print("Building frontend...")
        subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, check=True)
        return os.path.isfile(os.path.join(FRONTEND_DIST, "index.html"))
    except subprocess.CalledProcessError as e:
        print(f"WARNING: frontend build failed ({e}). Monitoring will still start, "
              "but the web UI won't be available until this is fixed.")
        return False


def open_browser_when_ready(url: str, frontend_built: bool, timeout: float = 15.0):
    """Waits for api_server's port to accept connections (main.py starts
    it in a background thread), then opens the browser. Runs in its own
    thread so it never blocks/delays monitoring startup. Skipped
    entirely if the frontend isn't built -- opening a browser tab to a
    "not built yet" message isn't useful."""
    if not frontend_built:
        return

    import socket

    host, port = "127.0.0.1", 8000
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.3)
    else:
        return  # API never came up in time -- don't force-open a dead tab

    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    frontend_built = build_frontend()

    if frontend_built:
        threading.Thread(
            target=open_browser_when_ready,
            args=("http://127.0.0.1:8000",),
            kwargs={"frontend_built": True},
            daemon=True,
        ).start()

    # Import here (not at module top) so `python launcher.py --help`-style
    # usage doesn't pay for pulling in cv2/mediapipe/etc. before the
    # frontend build step above has even run.
    import main as study_guard_main

    study_guard_main.main()


if __name__ == "__main__":
    main()
