# AI Planner - Full Stack Application

시간표 제작 및 스케줄 수행 보조 프로그램

## Overview

This project combines a **Next.js frontend** with a **FastAPI backend** to provide an AI-powered planning and scheduling system.

### Frontend (Next.js)
- Modern React-based UI for schedule management
- Calendar views and task planning interface

### Backend (FastAPI)
- REST API for managing users, schedules, tasks, and goals
- AI-powered plan generation using Gemini API
- Automatic time allocation algorithms
- PostgreSQL database with SQLAlchemy ORM

## Tech Stack

### Frontend
- Next.js 15+
- React
- TypeScript
- Tailwind CSS

### Backend
- Python 3.12+
- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL
- Gemini API with template fallback

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.12+
- Docker (for PostgreSQL)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd now-what
```

### 2. Backend Setup

```powershell
# Create virtual environment
py -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
Copy-Item .env.example .env

# Start PostgreSQL
docker compose up -d

# Run migrations
.\.venv\Scripts\alembic.exe upgrade head

# Start the API
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

API will be available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 3. Frontend Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend will be available at [http://localhost:3000](http://localhost:3000)

## Features

### Backend Features
- User creation and lookup
- Fixed schedule CRUD
- Flexible task CRUD
- Goal intake from natural language
- Goal question generation
- Goal save + plan generation
- Greedy auto-allocation into free time
- Unified calendar view

### Frontend Features
- Interactive calendar interface
- Schedule management
- Task planning and allocation
- Goal setting and tracking

## Database Schema

The application uses PostgreSQL with the following main tables:
- `users` - User accounts
- `fixed_schedules` - Fixed calendar events
- `flexible_tasks` - Tasks that can be scheduled flexibly
- `goals` - User goals with AI-generated plans
- `ai_plans` - AI-generated planning data
- `allocated_tasks` - Scheduled task allocations
- `ai_plan_items` - Individual plan items

## API Endpoints

### Main Endpoints
- `POST /api/v1/users` - Create user
- `GET /api/v1/users` - List users
- `POST /api/v1/schedules/fixed` - Create fixed schedule
- `GET /api/v1/schedules/fixed` - List fixed schedules
- `POST /api/v1/tasks/flexible` - Create flexible task
- `GET /api/v1/tasks/flexible` - List flexible tasks
- `POST /api/v1/goals/intake` - Start goal intake process
- `POST /api/v1/planner/allocate` - Allocate tasks to schedule
- `GET /api/v1/calendar` - Get unified calendar view

## Deployment

### Using Supabase
The backend can use Supabase as its PostgreSQL provider:

1. Replace `DATABASE_URL` in `.env` with your Supabase connection string
2. Run migrations: `alembic upgrade head`
3. Start API: `uvicorn app.main:app --reload`

### Frontend Deployment
Deploy to Vercel or any static hosting service:

```bash
npm run build
npm run start
```

## Notes

- Production defaults: `AUTO_CREATE_TABLES=false` and `SEED_DEMO_USER=false`
- Set `ALLOWED_ORIGINS` explicitly for your frontend
- `recurrence_rule` supports `daily`, `weekly`, and `biweekly`
- All operations require `user_id` for proper scoping
- Gemini API fallback to template-based responses when unavailable
