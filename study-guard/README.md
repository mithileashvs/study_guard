# Study Guard

Study Guard watches over your study sessions using your webcam and
your active window, and nudges you back on track when you slouch, get
distracted, or forget to take a break. It also has a Learning Roadmap
generator, session history/analytics, an AI study coach, and a playful
desktop cat companion.

This repo is split into three parts, deployed independently:

```
                          INTERNET
                             │
                             ▼
                    ┌──────────────────┐
                    │  Vercel Frontend │   frontend/  (React + Vite)
                    └────────┬─────────┘
                             │  VITE_API_BASE
                 ┌───────────┴────────────┐
                 ▼                        ▼
     http://127.0.0.1:8000     https://your-backend.example
   (your own machine, only         (backend/, e.g. Render --
   while the desktop agent     optional, cloud-hosted, no local
        is running)             hardware access, see below)
                 │
                 ▼
      ┌───────────────────────┐
      │   WINDOWS DESKTOP PC   │
      │                        │
      │   Study Guard Agent    │   desktop-agent/  (python launcher.py)
      │  ┌─────┬────────┬────┐ │
      │  ▼     ▼        ▼    │ │
      │ Webcam Window   Cat   │ │
      │      Tracking  Overlay│ │
      └───────────────────────┘
```

| Folder           | What it is                                          | Deployed to        |
|-------------------|------------------------------------------------------|---------------------|
| `frontend/`       | React/Vite web UI                                    | Vercel              |
| `backend/`        | Thin wrapper around the same Flask API, cloud-safe subset | Render / Railway / Fly.io (optional) |
| `desktop-agent/`  | Full local app: webcam, posture, window tracking, cat companion, media controls, **and** the same Flask API embedded in-process | Your Windows PC |

## Why this split (read this before changing the architecture)

Everything in this project was audited file-by-file. The result:

- **Desktop-only** (real hardware/OS access, can never run in the
  cloud): `main.py`, `window_tracker.py` (uses `pygetwindow`),
  `posture_tracker.py` (uses `cv2`/`mediapipe`, opens the webcam),
  `companion_overlay.py` and `desktop_pet/` (tkinter overlays),
  `media_control/` (OS media keys), `notifier.py` (native OS
  notifications), `intervention_manager.py`, `distraction_engine.py`,
  `session_context.py`. None of these are imported by the cloud
  backend.
- **Cloud-safe** (pure Python/Flask, only reads/writes small local
  JSON/CSV files, no OS/hardware calls): `api_server.py`,
  `roadmap_store.py` + `roadmap_models.py` + `roadmap_generator.py` +
  `roadmap_resources.py` + `roadmap_bridge.py`, `runtime_settings.py`,
  `session_bridge.py`, `live_status.py`, `scoring.py`, `logger.py`,
  `ai_coach.py`, `companion_messages.py`, `config.py`. Verified by
  inspection and by import-testing them with none of
  `cv2`/`tkinter`/`mediapipe`/`pygetwindow`/`pywin32` present.

Because `api_server.py` was **already** written this way (its one
webcam-touching route, `/api/session/readiness`, wraps `import cv2` in
a `try/except` and only uses it for a non-blocking camera-availability
probe), it did not need to be rewritten -- only reorganized and made
deployment-aware:

- `backend/app.py` is a ~20-line wrapper that adds `desktop-agent/` to
  `sys.path` and imports `api_server.app` directly. **It is not a
  second copy of the API** -- both deployments always run identical
  code, so there's nothing to keep in sync.
- `config.py` gained a `DATA_DIR` environment variable (default `.`,
  i.e. unchanged behavior) so the same file-backed storage works both
  on your desktop and on a cloud host with a persistent disk.
- CORS became configurable via `FRONTEND_URL` instead of a hardcoded
  wildcard (wildcard is still the default, since the desktop agent
  only ever binds to `127.0.0.1`).
- The React frontend moved out to the repo root (`frontend/`) as the
  single source Vercel builds, and that the desktop agent also builds
  locally to serve itself -- previously there was only one copy nested
  inside the desktop app; now there's still only one copy, just moved
  so it isn't tied to one deployment target.

**What a cloud backend deployment can and can't do:** Roadmap,
Settings, session History/Analytics (once the agent has produced a
`session_log.csv`), and the AI Coach's rule engine all work standalone
in the cloud. Live camera, posture, presence, distraction detection,
and the desktop cat companion **cannot** run in the cloud -- they need
your actual webcam and Windows desktop, so they only ever run inside
`desktop-agent/`. A cloud-only deployment's `/api/status` will always
report `"running": false`, honestly, because nothing is monitoring
there.

No database was introduced. The existing app is single-user and
file-backed (CSV/JSON) with no accounts/auth; adding
Postgres/Supabase now would mean also adding multi-tenant auth just to
have somewhere to point it, which is a real rewrite the brief asked to
avoid. If you want the cloud backend to be genuinely multi-user later,
that's the natural next step -- see **Known limitations** below.

## Local development

### Frontend
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, talks to http://127.0.0.1:8000 automatically
```

### Desktop agent (full functionality: webcam, posture, cat, etc.)
```bash
cd desktop-agent
pip install -r requirements.txt
python launcher.py     # builds frontend/ if needed, opens http://127.0.0.1:8000
```
`python main.py` still works too (same as before), it just won't
auto-build the frontend or open a browser tab.

### Cloud backend, run locally (optional -- only useful for testing
the cloud deployment path; the desktop agent's embedded API already
covers local development)
```bash
cd backend
pip install -r requirements.txt
DATA_DIR=./data python app.py    # http://127.0.0.1:8000
```

## Environment variables

See `.env.example` (root), `frontend/.env.example`, and the comments
in `backend/app.py` / `desktop-agent/config.py`. Summary:

| Variable       | Used by            | Purpose                                             | Default |
|----------------|---------------------|------------------------------------------------------|---------|
| `VITE_API_BASE`| `frontend/`         | Which Study Guard API the web app calls              | dev: `http://127.0.0.1:8000`, prod build: relative `/api/...` |
| `FRONTEND_URL` | `backend/`, `desktop-agent/` | Comma-separated allowed CORS origins        | `*` |
| `DATA_DIR`     | `backend/`, `desktop-agent/` | Where local state files (session log, roadmap data, settings) are read/written | `.` |
| `HOST`, `PORT` | `backend/`, `desktop-agent/` | Bind address for `python app.py` / `api_server.py` | `127.0.0.1:8000` (desktop), `0.0.0.0:$PORT` (cloud) |

Never commit a real `.env` file -- see `.gitignore`.

## GitHub setup
```bash
git init
git add .
git commit -m "Study Guard: web + desktop split"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```
`session_log.csv`, `live_state.json`, `live_frame.jpg`,
`roadmap_data.json`, and `runtime_settings.json` are gitignored --
they're personal runtime data generated by the desktop agent, not
source code. A stale `session_log.csv` that shipped with the original
project was removed before this restructuring.

## Vercel deployment (frontend)
1. Import this repo into Vercel.
2. Set **Root Directory** to `frontend`.
3. Framework preset: Vite (auto-detected). Build command
   `npm run build`, output directory `dist` (Vercel defaults, no
   change needed).
4. Add environment variable `VITE_API_BASE` (see table above) if you
   want this deployment to reach a specific backend by default. Leave
   it unset if every visitor is expected to run their own local
   desktop agent.
5. Deploy.

## Backend deployment (optional cloud API)

**Recommended: Render**, over Railway/Fly.io, because this is a small
single-process Flask app with no background workers, no queues, and
(without a database) no need for managed infra beyond a persistent
disk for `DATA_DIR` -- Render's free/starter web-service tier plus one
persistent disk covers this with the least configuration. Railway or
Fly.io would work equally well if you already use them; nothing here
is Render-specific beyond the exact dashboard steps below.

1. New **Web Service** on Render, pointed at this repo.
2. **Root Directory**: `backend`
3. **Build command**: `pip install -r requirements.txt`
4. **Start command**: `gunicorn app:app --bind 0.0.0.0:$PORT` (same as
   `backend/Procfile`)
5. **Environment variables**:
   - `FRONTEND_URL` = your Vercel URL (e.g.
     `https://study-guard.vercel.app`)
   - `DATA_DIR` = `/opt/render/project/src/data` (or wherever you
     mount a persistent disk -- without one, data is lost on every
     redeploy/restart, since Render's default filesystem is ephemeral)
6. Add a **Persistent Disk** if you want Roadmap/history data to
   survive redeploys, mounted at the path used for `DATA_DIR` above.
7. Deploy, then set `VITE_API_BASE` on the Vercel project to this
   service's URL if you want the hosted frontend to use it by default.

## Desktop agent setup (Windows)
```bash
cd desktop-agent
pip install -r requirements.txt
python launcher.py
```
First run downloads a small MediaPipe pose-landmark model
(~5-10MB, needs internet once). Requires a webcam for
posture/presence detection; everything else in the desktop agent
still runs without one (distraction detection, roadmap, companion
notifications for non-posture events).

## Web functionality
- Roadmap: create a learning roadmap for any goal, track topic
  progress, get resources, take generated quizzes.
- Settings: allowed apps/keywords for distraction detection.
- Session history and weekly analytics, once the desktop agent has
  logged sessions.
- AI Coach: a local rule-based study coach.
- Live Session page, Live Focus Monitor, and camera preview -- these
  render fully in the browser but only show real data when
  `VITE_API_BASE` points at a **running desktop agent**, since that's
  the only place webcam/window data ever exists.

## Desktop functionality
- Webcam-based posture and presence monitoring (calibrated baseline,
  smoothed `GOOD`/`SLIGHT_SLOUCH`/`SLOUCHING`/`AWAY` state machine).
- Active-window-based distraction detection with a configurable grace
  period and content-aware YouTube classification.
- Playful desktop cat companion + plain companion overlay, escalating
  through notifications before it appears.
- OS media key control (as part of the cat's escalation, opt-out via
  `MEDIA_INTERFERENCE_ENABLED` in `config.py`).
- Native desktop notifications for posture/break reminders.
- Everything above is also reachable through the same web UI when
  it's opened on the same machine the agent is running on (embedded
  Flask server at `127.0.0.1:8000`).

## Known limitations
- **Single user, no auth.** Every deployment (desktop or cloud) is a
  single user's own data on their own disk/host. There is no login
  system. If you deploy `backend/` publicly, anyone with the URL can
  read/write that instance's roadmap and settings -- put it behind
  your own auth/proxy if that matters to you, or keep it private.
- **Cloud backend has no live session data**, by design -- see the
  architecture section above.
- **Render's default disk is ephemeral.** Without a persistent disk
  correctly mounted at `DATA_DIR`, roadmap/history data does not
  survive a redeploy or restart.
- **`npm install`/`npm run build` and `gunicorn` were not runnable in
  the sandbox this change was made in** (no network egress). See
  "Tests performed" below for exactly what was and wasn't verified.
- Posture/distraction thresholds may need re-tuning per webcam/desk
  setup -- see `POSTURE_DEBUG_MODE` in `desktop-agent/config.py`
  (unchanged from the original project).

## Tests performed
- `python3 -m py_compile` on every file in `desktop-agent/` (including
  `desktop_pet/` and `media_control/`) -- all compile cleanly.
- Imported `backend/app.py` directly and confirmed, via
  `sys.modules`, that none of `cv2`, `tkinter`, `mediapipe`,
  `pygetwindow`, `win32api`, `win32gui` are ever loaded.
- Exercised the cloud backend through Flask's test client:
  `/api/status`, `/api/session/status`, `/api/settings`,
  `/api/roadmap/active`, `/api/roadmap/create`,
  `/api/sessions/history`, `/api/analytics/weekly`,
  `/api/coach/greeting`, and `/` (correctly returns 503 with a "build
  the frontend" message when no build exists) -- all returned expected
  responses.
- Confirmed `DATA_DIR` is honored end-to-end: `config.LOG_FILE` /
  `config.ROADMAP_DATA_FILE` resolved under the given directory, and
  `roadmap_data.json` was actually written there after
  `/api/roadmap/create`.
- `node --check` on `frontend/src/data/api.js` (the only frontend file
  whose logic changed) -- valid syntax.
- **Not run** (no network access in this environment):
  `npm install` / `npm run build` in `frontend/`, and installing/
  running `gunicorn` for `backend/`. The Flask `app` object itself was
  verified via its test client, which exercises the same route/view
  code gunicorn would serve -- only the WSGI server process itself is
  unverified. Please run `npm install && npm run build` and `gunicorn
  app:app` yourself before your first real deploy.
