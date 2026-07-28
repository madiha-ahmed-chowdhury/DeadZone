# DeadZone

> **"The Internet Is a Privilege. Survival Isn't."**

A dual-interface crisis coordination platform for Bangladesh. Civilians send
"I'm Alive" pulses in Bangla via a Telegram bot; coordinators (NGOs, relief
workers, journalists, families) watch a live crisis map showing active pulses
and a **Dead Zone heatmap** of areas that have gone silent.

This repository hosts the thin-slice MVP: a Telegram bot, FastAPI backend,
Supabase database, and Next.js dashboard rendered with Leaflet + an h3 hex-grid
over Bangladesh.

## Monorepo structure

```
.
├── backend/        # FastAPI + python-telegram-bot
│   ├── api/        # HTTP + WebSocket routes
│   ├── bot/        # Telegram bot handlers + entrypoint
│   ├── db/         # Supabase schema + client wrapper
│   └── services/   # Pulse parser, geocoder, h3 indexer, pulse service
├── frontend/       # Next.js + Tailwind + react-leaflet dashboard
└── infra/          # render.yaml, environment notes
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

```bash
cd frontend
npm install
cp .env.example .env.local # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Open <http://localhost:3000>.

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
| `NEXT_PUBLIC_API_URL` | frontend | Public URL of the FastAPI backend |

## Deploy (Render)

`render.yaml` at the repo root defines two services:

- `deadzone-api` — Python web service running uvicorn + the Telegram bot
- `deadzone-web` — Static Node service serving the Next.js export

Render reads env vars from the blueprint and the dashboard. After linking
the repo, hit **Apply** to provision.

## License

MIT — see `LICENSE`.
