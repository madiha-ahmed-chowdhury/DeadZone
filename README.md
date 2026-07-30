# DeadZone

> **"The Internet Is a Privilege. Survival Isn't."**

A dual-interface crisis coordination platform for Bangladesh. Civilians send
"I'm Alive" pulses in Bangla via a Telegram bot; coordinators (NGOs, relief
workers, journalists, families) watch a live crisis map showing active pulses
and a **Dead Zone heatmap** of areas that have gone silent.

This repository hosts the thin-slice MVP: a Telegram bot, FastAPI backend,
Supabase database, and a coordinator dashboard rendered with Leaflet + an h3
hex-grid over Bangladesh.

## Monorepo structure

```
.
├── backend/        # FastAPI + python-telegram-bot
│   ├── api/        # HTTP + WebSocket routes
│   ├── bot/        # Telegram bot handlers + entrypoint
│   ├── db/         # Supabase schema + client wrapper
│   └── services/   # Pulse parser, geocoder, h3 indexer, pulse service
├── frontend/       # Static HTML/CSS/JS dashboard (Leaflet + h3-js, no build step)
└── render.yaml     # One-click Render blueprint (api + static site + bot worker)
```

## Quick start (local development)

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in SUPABASE_URL, SUPABASE_SERVICE_KEY, TELEGRAM_BOT_TOKEN
uvicorn main:app --reload --port 8000
```

Health check: `curl http://localhost:8000/healthz` → `{"ok": true}`

### 2. Apply the database schema

In the Supabase SQL editor, paste and run `backend/db/schema.sql`.

Or via the Supabase CLI:

```bash
supabase db reset          # local
supabase db push           # linked project
```

### 3. Frontend

No build step — it's plain HTML/CSS/JS (Leaflet + h3-js from CDN).

```bash
cd frontend
python -m http.server 8080
```

Open <http://localhost:8080>. On first load it'll prompt for the API base
URL (defaults to `http://localhost:8000` on localhost) and, optionally, a
coordinator key (`BACKEND_API_KEY`) if you've set one on the backend —
without it the map and needs queue are still viewable, but status-update
buttons stay disabled since updating a need's status is a coordinator-only
action.

### 4. Telegram bot

Create a bot with [@BotFather](https://t.me/BotFather), copy the token into
`backend/.env` as `TELEGRAM_BOT_TOKEN`, then run alongside the FastAPI server:

```bash
cd backend
python -m bot.telegram_bot
```

Send the bot: `আমি ঠিক আছি, ঢাকা`. The pulse should appear on the dashboard
within ~1 second.

The bot tries every message against the "I'm alive" pulse parser first, then
falls back to the need-broadcast parser below. It talks to the FastAPI
backend over HTTP (`API_BASE_URL`, default `http://localhost:8000`) rather
than sharing memory, since it runs as a separate process.

## Coordinator dashboard

`frontend/` is a static Leaflet + h3-js map (dark, low-bandwidth-friendly —
no framework, no build step, no bundle to download beyond two small CDN
libraries):

- **Dead Zone heatmap** — every h3 hex is colored by time since its last
  pulse: green (< 15 min), amber (15–60 min), red (> 60 min — a "dead
  zone"). This is the core signal the whole platform exists to surface.
- **Live pulse dots** — individual "I'm alive" reports plotted on the map.
- **Need Broadcast queue** — the sidebar, sorted by priority then recency,
  filterable by category/status, with one-click status updates
  (open → acknowledged → dispatched → fulfilled) gated behind a coordinator
  key so only authorized responders can move a request through the queue.
- **Polls every 5s** by default, and opportunistically upgrades to the
  `/ws/pulses` WebSocket for push updates when the backend has Supabase
  Realtime configured — falls back to polling seamlessly if not.

## Need Broadcast Engine

Anyone can report a need in plain Bangla and have it auto-categorized and
priority-scored for the coordinator dashboard:

```
পানি দরকার, মিরপুর ১০          -> category: water,   priority: 4
জরুরি ঔষধ লাগবে, সিলেট          -> category: medical, priority: 5 (urgent)
একটা তাঁবু চাই, কক্সবাজার        -> category: shelter, priority: 3
```

Categories: `water`, `food`, `medical`, `shelter`, `other`. Priority is 1
(lowest) to 5 (highest); mentions of urgency, children, pregnancy, or the
elderly bump the score up a notch. See `backend/services/need_parser.py` for
the full keyword lists.

API surface (mirrors the pulses API):

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/v1/needs` | `POST` | Parse + persist a need report |
| `/api/v1/needs` | `GET` | List needs, sorted by priority then recency (filter by `category`/`status`) |
| `/api/v1/needs/{id}/status` | `PATCH` | Coordinator marks `open` / `acknowledged` / `dispatched` / `fulfilled` |

The `status` field here is intentionally minimal — full aid dispatch
bookkeeping (which coordinator, which resources, an immutable audit trail)
is the next feature to build on top of it, not part of this engine.

## Local development without Supabase

Every service falls back to an in-memory store (`backend/db/memory_store.py`)
when `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` aren't set, or when
`DEADZONE_DRY_RUN=true`. This lets you run the whole pulse + need flow with
`uvicorn main:app --reload --port 8000` and `curl` before wiring up a real
Supabase project. Data in this mode does not persist across restarts and
isn't shared between the API process and the bot process.

## Environment variables

See `backend/.env.example` for the complete contract. Required:

| Variable | Where | Purpose |
|---|---|---|
| `SUPABASE_URL` | backend | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | backend | Service-role key (server only) |
| `TELEGRAM_BOT_TOKEN` | backend | Bot token from @BotFather |
| `ALLOWED_ORIGINS` | backend | Comma-separated CORS origins for the frontend |
| `BACKEND_API_KEY` | backend + bot | Shared secret gating write endpoints (create pulse/need, update need status). Leave blank for local dev; **set it before any public deployment** — without it, anyone with the URL can forge safety signals or mark real aid requests "fulfilled". |
| API base URL | frontend | Entered in the dashboard's settings panel (⚙), stored in the browser only — no build-time env var since there's no build step |

## Deploy (Render)

`render.yaml` at the repo root defines three services:

- `deadzone-api` — Python web service running uvicorn
- `deadzone-web` — Static site serving the `frontend/` dashboard as-is (no build)
- `deadzone-bot` — Background worker running the Telegram bot in long-polling mode

Render reads env vars from the blueprint and the dashboard; fill in
`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and `TELEGRAM_BOT_TOKEN` there
(`BACKEND_API_KEY` is auto-generated). After linking the repo, hit
**Apply** to provision, then narrow `ALLOWED_ORIGINS` on `deadzone-api`
from `*` to the deployed `deadzone-web` URL once you have it.

## Security notes

A few things worth knowing if you extend this beyond the MVP:

- **`users` is not publicly readable.** It stores `telegram_id`; exposing
  it would let anyone with the anon key deanonymize which real person sent
  which pulse. Only `pulses`, `needs`, and `h3_hexes` (aggregates, no
  identity) are public-read.
- **Write endpoints require `BACKEND_API_KEY`** once it's set (see
  Environment variables above). Unset, auth is skipped for frictionless
  local dev — always set it before deploying anywhere public.
- **Hex pulse counts increment atomically** via a Postgres function
  (`increment_hex` in `schema.sql`) rather than a read-then-write round
  trip from Python, so concurrent pulses during a real spike don't lose
  counts to a race condition.

## License

MIT — see `LICENSE`.
