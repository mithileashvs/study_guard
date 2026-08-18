# Study Guard — Frontend

React + Vite frontend for Study Guard. Talks to the Study Guard API
(`src/data/api.js`) — see the [root README](../README.md) for the
full web + desktop architecture and deployment instructions
(Vercel, `VITE_API_BASE`, etc).

`src/data/mockData.js` is still used by a couple of not-yet-wired
pages/components; check each page for whether it currently calls
`api.js` or still reads mock data before assuming a given screen shows
live data.

## Run it

```bash
npm install
npm run dev
```

Then open the local URL Vite prints (usually http://localhost:5173).
This talks to a Study Guard API at `http://127.0.0.1:8000` by default
in dev mode — run the desktop agent (`cd ../desktop-agent && python
launcher.py`) or the standalone backend (`cd ../backend && python
app.py`) alongside it for live data. Override with `VITE_API_BASE` —
see `.env.example`.

## Structure

- `src/components/` — reusable UI pieces (Sidebar, StatCard, LiveFocusMonitor, FocusBreakdown, TimelineCard, RecentAlerts, etc.)
- `src/pages/` — one file per route (Overview, Roadmap, LiveSession, Sessions, Analytics, History, Companion, Settings)
- `src/data/mockData.js` — single source of mock data for the whole app
- `src/styles/index.css` — design tokens (colors, radii, shadows, fonts) and global styles

## Companions

Companions are modeled as a plain array in `mockData.js` (`companions`), each with `id`, `name`, `emoji`, `tagline`, `description`, `mood`, `bond`, and `active`. To add a new companion (e.g. "Study Owl"), just add an entry to that array — no component changes needed. The sidebar card and `/companion` page both read from this list.

## Notes

- All data is mocked. Nothing here talks to a backend.
- No existing Study Guard files were touched — this is a fully separate project.
- Routing is done with `react-router-dom`.
- The donut on the Overview page is a plain SVG circle (no chart library) per the design brief. Analytics uses Recharts for the weekly bar chart.
