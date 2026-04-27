# AI Planner Backend

FastAPI backend for managing users, fixed schedules, flexible tasks, goals, AI-generated plans, and automatic time allocation.

## Features

- User creation and lookup
- Fixed schedule CRUD
- Flexible task CRUD
- Goal intake from natural language
- Goal question generation
- Goal save + plan generation
- Greedy auto-allocation into free time
- Unified calendar view

## Tech Stack

- Python 3.12+
- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL
- Gemini API with template fallback

## Quick Start (Local Postgres)

1. Create a virtual environment

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Install dependencies

```powershell
pip install -r requirements.txt
```

3. Copy environment variables

```powershell
Copy-Item .env.example .env
```

4. Start PostgreSQL

```powershell
docker compose up -d
```

5. Run migrations

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

6. Start the API

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Use With Supabase

This project can use Supabase as its PostgreSQL provider without changing the overall FastAPI or SQLAlchemy structure.

1. Copy environment variables

```powershell
Copy-Item .env.example .env
```

2. Replace `DATABASE_URL` in `.env` with your Supabase connection string

- Persistent backend with IPv6 support: use the `Direct connection` string.
- Persistent backend on IPv4-only networks: use the `Session pooler` string.
- Add `?sslmode=require` to the connection string.

3. Run migrations against Supabase

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

4. Start the API

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

5. Verify the database connection

- `GET /health`
- `GET /health/db`

Notes:

- This backend does not have login/auth yet, so Supabase is currently used as the database layer only.
- For this long-running FastAPI app, avoid the Supabase transaction pooler. It is intended for short-lived/serverless traffic.
- Local Docker Postgres can still be used for offline development by keeping the default `DATABASE_URL`.

## Notes

- Production defaults are conservative: `AUTO_CREATE_TABLES=false` and `SEED_DEMO_USER=false`.
- Set `ALLOWED_ORIGINS` explicitly for your frontend.
- `recurrence_rule` supports `daily`, `weekly`, and `biweekly`.
- Item-level goal, fixed schedule, and flexible task operations require `user_id` so requests stay scoped to the correct owner.
- If Gemini is unavailable, the app falls back to template-based questions and plans.

## Main Endpoints

- `POST /api/v1/users`
- `GET /api/v1/users`
- `GET /api/v1/users/{user_id}`
- `POST /api/v1/schedules/fixed`
- `GET /api/v1/schedules/fixed`
- `PATCH /api/v1/schedules/fixed/{schedule_id}?user_id=...`
- `DELETE /api/v1/schedules/fixed/{schedule_id}?user_id=...`
- `POST /api/v1/tasks/flexible`
- `GET /api/v1/tasks/flexible`
- `PATCH /api/v1/tasks/flexible/{task_id}?user_id=...`
- `DELETE /api/v1/tasks/flexible/{task_id}?user_id=...`
- `GET /api/v1/goals`
- `GET /api/v1/goals/{goal_id}?user_id=...`
- `PATCH /api/v1/goals/{goal_id}?user_id=...`
- `POST /api/v1/goals/intake`
- `POST /api/v1/goals/complete`
- `POST /api/v1/planner/allocate`
- `GET /api/v1/calendar`
