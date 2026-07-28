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
