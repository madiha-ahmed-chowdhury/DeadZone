# DeadZone

> **"The Internet Is a Privilege. Survival Isn't."**

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)
![Supabase](https://img.shields.io/badge/Supabase-Backend-3ECF8E)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4)
![License](https://img.shields.io/badge/License-MIT-yellow)

DeadZone is a disaster communication platform designed for regions where internet connectivity becomes unreliable during emergencies.

Citizens can report that they are **safe ("I'm Alive")** or request **urgent assistance** in Bangla through a Telegram bot. Reports are automatically parsed, geocoded, prioritized, and visualized on a live coordinator dashboard featuring an H3-powered **Dead Zone Heatmap**, enabling NGOs, volunteers, journalists, and families to identify silent regions and coordinate relief efforts efficiently.

---

# Features

- 🇧🇩 Bangla Natural Language Processing
- ✅ "I'm Alive" Pulse Engine
- 🚨 Need Broadcast Engine
- 📍 Automatic location extraction
- 🗺️ Interactive crisis map
- 🔥 Dead Zone Heatmap using Uber H3
- 🤖 Telegram Bot interface
- ⚡ FastAPI REST API
- 🧠 Automatic need categorization & priority scoring
- ☁️ Supabase database
- 🌐 Live coordinator dashboard
- 🔒 API-key protected write endpoints

---

# Screenshots

## Coordinator Dashboard


<img width="1520" height="710" alt="image" src="https://github.com/user-attachments/assets/e196c007-7724-46b0-8d4d-7e0b1b6f2c3d" />


---

## Telegram Bot
<img width="372" height="465" alt="image" src="https://github.com/user-attachments/assets/164e570f-8672-4322-acbd-620f780e7d74" />


---

# Architecture

```
                    Citizens

                        │
                        ▼

                Telegram Bot

                        │
                        ▼

                 FastAPI Backend

       ┌──────────┼───────────┐

       ▼          ▼           ▼

 Pulse Engine  Need Engine  Geocoder

       │          │

       └──────┬───┘

              ▼

         H3 Indexing

              ▼

          Supabase

              ▼

     Coordinator Dashboard
```

---

# Monorepo Structure

```
.
├── backend/
│   ├── api/
│   ├── bot/
│   ├── core/
│   ├── db/
│   ├── services/
│   ├── main.py
│   └── requirements.txt
│
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   └── assets/
│
├── docs/
│   ├── dashboard.png
│   └── telegram.png
│
├── render.yaml
├── README.md
└── LICENSE
```

---

# Example Messages

### ✅ I'm Alive

```
আমি ঠিক আছি, ঢাকা

আমি নিরাপদ, চট্টগ্রাম

I'm safe, Dhaka

I'm okay, Sylhet
```

---

### 🚨 Need Reports

```
পানি দরকার, চট্টগ্রাম

জরুরি ঔষধ লাগবে, সিলেট

খাবার চাই, কুমিল্লা

আশ্রয় দরকার, কক্সবাজার

Medical help needed, Dhaka
```

---

# Need Categories

| Category | Example |
|----------|---------|
| Water | পানি দরকার |
| Food | খাবার দরকার |
| Medical | ঔষধ লাগবে |
| Shelter | আশ্রয় দরকার |
| Other | Miscellaneous requests |

Urgency keywords automatically increase priority.

Examples:

```
জরুরি ঔষধ লাগবে, সিলেট
```

becomes

```
Category: Medical
Priority: 5
Urgent: Yes
```

---

# Coordinator Dashboard

The dashboard provides:

- 🟢 Live pulse locations
- 🔥 Dead Zone heatmap
- 🚨 Priority-sorted aid requests
- 📍 Interactive Leaflet map
- 🔍 Category & status filtering
- ✔️ Status updates

Need status workflow:

```
Open

↓

Acknowledged

↓

Dispatched

↓

Fulfilled
```

---

# REST API

## Health

```
GET /healthz
```

---

## Pulses

```
POST /api/v1/pulses

GET /api/v1/pulses

GET /api/v1/hexes
```

---

## Needs

```
POST /api/v1/needs

GET /api/v1/needs

PATCH /api/v1/needs/{id}/status
```

Interactive API documentation is available through Swagger:

```
http://localhost:8000/docs
```

---

# Tech Stack

## Backend

- Python 3.12
- FastAPI
- Uvicorn
- Supabase
- PostgreSQL
- H3
- python-telegram-bot
- Pydantic

---

## Frontend

- HTML5
- CSS3
- JavaScript
- Leaflet
- h3-js

---

## Infrastructure

- Render
- GitHub
- Telegram Bot API
- Supabase

---

# Quick Start

## Clone

```bash
git clone https://github.com/madiha-ahmed-chowdhury/DeadZone.git

cd DeadZone
```

---

## Backend

```bash
cd backend

python -m venv .venv

source .venv/bin/activate
```

Windows

```powershell
.venv\Scripts\activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Copy environment file

```bash
cp .env.example .env
```

Fill in

```
SUPABASE_URL

SUPABASE_SERVICE_KEY

TELEGRAM_BOT_TOKEN

BACKEND_API_KEY
```

Run

```bash
uvicorn main:app --reload
```

---

## Frontend

```bash
cd frontend

python -m http.server 8080
```

Open

```
http://localhost:8080
```

---

## Telegram Bot

```bash
cd backend

python -m bot.telegram_bot
```

---

# Local Development without Supabase

DeadZone automatically falls back to an in-memory database if Supabase credentials are not configured or if

```
DEADZONE_DRY_RUN=true
```

This allows the backend, frontend, and Telegram bot to be tested locally without any cloud infrastructure.

---

# Environment Variables

| Variable | Description |
|------------|-------------|
| SUPABASE_URL | Supabase project URL |
| SUPABASE_SERVICE_KEY | Service Role Key |
| TELEGRAM_BOT_TOKEN | Telegram Bot Token |
| BACKEND_API_KEY | Shared API key |
| ALLOWED_ORIGINS | CORS Origins |
| API_BASE_URL | Backend URL |

---

# Deployment

Render deployment is supported using the included

```
render.yaml
```

It provisions:

- FastAPI backend
- Static frontend
- Telegram bot worker

Environment variables can be configured directly from the Render dashboard.

---

# Security

- Telegram user IDs are stored securely.
- Public API only exposes pulse and need information.
- Write operations require an API key.
- H3 aggregation is performed atomically to avoid race conditions.
- Supabase Row Level Security protects sensitive tables.

---

# Roadmap

- SMS Gateway
- Offline mesh networking
- Duplicate need detection
- NGO authentication
- Push notifications
- Disaster analytics
- AI-assisted resource allocation

---

# Project Status

Current MVP

- ✅ Bangla Pulse Engine
- ✅ Need Broadcast Engine
- ✅ Telegram Bot
- ✅ FastAPI Backend
- ✅ Coordinator Dashboard
- ✅ Dead Zone Heatmap
- ✅ H3 Spatial Indexing
- ✅ Supabase Integration

Upcoming

- 🚧 SMS Integration
- 🚧 Mesh Networking
- 🚧 Offline Synchronization
- 🚧 NGO Portal
- 🚧 Volunteer Dispatch System

---



## Demo Video

*(Add YouTube or Drive link here)*

---


GitHub:
https://github.com/madiha-ahmed-chowdhury
