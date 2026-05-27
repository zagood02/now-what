# Frontend Test Flow

## 1. Seed sample data

```powershell
.\.venv\Scripts\python.exe scripts\seed_frontend_sample_data.py
```

The script creates:

- one sample user
- three fixed schedules
- three flexible tasks
- one goal
- one AI plan with plan items
- auto-allocation results for the next 7 days

## 2. Start the backend

```powershell
docker compose up -d
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe backend.main:app --reload
```

Open:

- http://127.0.0.1:8000/docs

## 3. Suggested API order

1. `GET /api/v1/health`
2. `POST /api/v1/users/login` with `frontend-sample@example.com` and `sample-password`
3. Add `Authorization: Bearer {access_token}` to protected requests
4. `GET /api/v1/users`
5. `GET /api/v1/schedules/fixed`
6. `GET /api/v1/tasks/flexible`
7. `GET /api/v1/goals`
8. `GET /api/v1/goals/{GOAL_ID}`
9. `GET /api/v1/calendar?start={ISO_START}&end={ISO_END}`

## 4. Good frontend screens to validate

- user selector
- fixed schedule list
- flexible task list with remaining time
- goal detail with AI plan items
- calendar merged from all event sources
