# Backend API List

This document is the backend-facing API inventory for the capstone demo.
The priority is a stable demo flow: login, create schedules/tasks/goals, allocate, and show the calendar.

Base URL:

- Local API: `http://127.0.0.1:8000/api/v1`
- Frontend default target: `http://localhost:8000/api/v1`

Generated reference:

- [api-reference.md](api-reference.md)
- Regenerate with `.\.venv\Scripts\python.exe scripts\generate_api_reference.py`
- Check freshness with `.\.venv\Scripts\python.exe scripts\generate_api_reference.py --check`

Authentication:

- Most user data APIs should use `Authorization: Bearer <access_token>`.
- The token is issued by `/users/login` or `/auth/google`.
- User-owned write APIs derive ownership from the authenticated token. Request bodies do not expose `user_id`.

## Demo-Critical Flow

Use this as the main presentation path.

1. Login or create a user.
2. Create fixed schedules.
3. Create flexible tasks.
4. Create or complete a goal.
5. Run planner allocation.
6. Read the calendar range and show the result in the frontend.

Smoke test script:

```powershell
.\.venv\Scripts\uvicorn.exe backend.main:app --reload
```

In another terminal:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_api_flow.py
```

Use a different API URL if needed:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_api_flow.py --base-url http://localhost:8000/api/v1
```

## Current Implemented APIs

### Auth

| Method | Path | Auth | Purpose | Status |
| --- | --- | --- | --- | --- |
| `GET` | `/auth/me` | Required | Get current logged-in user | OK |
| `POST` | `/auth/google` | Public | Login/signup with Google credential | OK |

### Users

| Method | Path | Auth | Purpose | Status |
| --- | --- | --- | --- | --- |
| `POST` | `/users/register` | Public | Email/password signup | Duplicate with `/users` |
| `POST` | `/users/login` | Public | Email/password login | OK |
| `POST` | `/users` | Public | Email/password signup | OK, used by frontend |
| `GET` | `/users` | Required | List current user only | Protected; no cross-user listing |
| `GET` | `/users/{user_id}` | Required | Get current user by id | Protected; other user ids return 404 |

Recommended capstone stance:

- Keep `/users` and `/users/login` for the frontend.
- Treat `/users/register` as a compatibility alias.
- Do not use `/users` as an admin-style user listing; it only returns the authenticated user.

### Fixed Schedules

| Method | Path | Auth | Purpose | Status |
| --- | --- | --- | --- | --- |
| `POST` | `/schedules/fixed` | Required | Create fixed schedule | OK |
| `GET` | `/schedules/fixed` | Required | List fixed schedules, optional `start` and `end` query | OK |
| `GET` | `/schedules/fixed/{schedule_id}` | Required | Get fixed schedule | OK |
| `PATCH` | `/schedules/fixed/{schedule_id}` | Required | Update fixed schedule | OK |
| `DELETE` | `/schedules/fixed/{schedule_id}` | Required | Delete fixed schedule | OK |

### Flexible Tasks

| Method | Path | Auth | Purpose | Status |
| --- | --- | --- | --- | --- |
| `POST` | `/tasks/flexible` | Required | Create flexible task | OK |
| `GET` | `/tasks/flexible` | Required | List flexible tasks | OK |
| `GET` | `/tasks/flexible/{task_id}` | Required | Get flexible task | OK |
| `PATCH` | `/tasks/flexible/{task_id}` | Required | Update flexible task | OK |
| `DELETE` | `/tasks/flexible/{task_id}` | Required | Delete flexible task | OK |
| `DELETE` | `/tasks/flexible/allocations/{allocation_id}` | Required | Remove one auto-allocated flexible task calendar block | OK |

Deletion behavior:

- Deleting a flexible task removes the task source and its allocated calendar blocks.
- Deleting an allocation removes only that scheduled block. The original flexible task remains and can be allocated again later.

### Goals and AI Plans

| Method | Path | Auth | Purpose | Status |
| --- | --- | --- | --- | --- |
| `POST` | `/goals` | Required | Manual goal creation without AI plan generation | OK |
| `GET` | `/goals` | Required | List current user's goals | OK |
| `GET` | `/goals/{goal_id}` | Required | Get goal detail with plans/items | OK |
| `PATCH` | `/goals/{goal_id}` | Required | Update goal fields | OK |
| `DELETE` | `/goals/{goal_id}` | Required | Delete goal with generated plans and plan items | OK |
| `POST` | `/goals/intake` | Required | Parse freeform goal and return questions | Protected to avoid unauthenticated LLM use |
| `POST` | `/goals/complete` | Required | Save parsed goal and generate plan | OK |

Recommended capstone stance:

- Primary demo path should use `/goals/intake` then `/goals/complete`.
- Manual goal creation is available through `POST /goals` when the AI Q&A flow is not needed.

### Planner

| Method | Path | Auth | Purpose | Status |
| --- | --- | --- | --- | --- |
| `POST` | `/planner/allocate` | Required | Allocate flexible tasks and AI plan items into free time | OK, basic stability cleanup applied |
| `DELETE` | `/planner/plan-items/{item_id}/schedule` | Required | Remove one AI plan item from the calendar but keep it suggested | OK |
| `POST` | `/planner/plan-items/{item_id}/skip` | Required | Mark an AI plan item as skipped and clear its schedule | OK |

Current request shape:

```json
{
  "range_start": "2026-05-08T00:00:00+09:00",
  "range_end": "2026-05-15T00:00:00+09:00",
  "day_start": "09:00",
  "day_end": "22:00",
  "buffer_minutes": 30,
  "max_auto_minutes_per_day": 360,
  "clear_existing": true
}
```

Notes:

- Planner inputs are normalized to the same Asia/Seoul local time policy as calendar and schedule APIs.
- By default, allocation preserves fixed schedules and rebuilds existing auto-allocated flexible tasks / AI plan item slots inside the requested range.
- Default allocation hours are `09:00` to `22:00`.
- `buffer_minutes` defaults to `30` and is applied around occupied time so auto blocks are not packed back-to-back.
- `max_auto_minutes_per_day` defaults to `360` to keep daily auto allocation from overwhelming the timetable.
- Slot selection is score-based now: it prefers fuller session chunks, lighter days/time buckets, and mid-day candidates over simple first-fit scheduling.

### Calendar

| Method | Path | Auth | Purpose | Status |
| --- | --- | --- | --- | --- |
| `GET` | `/calendar?start=...&end=...` | Required | Return unified calendar events | OK |

Expected event sources:

- `fixed_schedule`
- `allocated_task`
- `ai_plan_item`

### Health and Demo

| Method | Path | Auth | Purpose | Status |
| --- | --- | --- | --- | --- |
| `GET` | `/health` | Public | API liveness check | OK |
| `GET` | `/health/db` | Public | DB connectivity check | OK |
| `GET` | `/demo/api-playground` | Public | HTML demo page | Demo-only |
| `GET` | `/demo/goal-intake` | Public | HTML demo page alias | Demo-only |
| `GET` | `/demo/calendar` | Public | HTML demo page | Demo-only |
| `GET` | `/demo/calendar-view` | Public | HTML demo page alias | Demo-only |
| `GET` | `/demo/user-flow` | Public | HTML demo page | Demo-only |

## Cleanup Priority

### Must Fix Before Demo

1. Verify that frontend calls use the documented API list.
2. Run the demo-critical flow manually before presentation.
3. Improve planner quality after the baseline allocation flow is stable.

### Nice to Fix Before Demo

1. Replace broken Korean error messages with clean Korean or English.
2. Add admin-only user management only if the product actually needs it.
3. Add rate limiting for login, Google auth, and AI planning calls.
4. Make calendar errors visible in development logs.

### Can Defer

1. Rate limiting.
2. Full OAuth account-linking hardening.
3. Production-grade migration cleanup.
4. Pagination for large datasets.
5. Planner algorithm improvements.

## Timezone Policy Proposal

For this project, the simplest stable policy is:

> The backend stores and returns all schedule datetimes as Asia/Seoul local wall-clock time without timezone info, and the frontend sends Asia/Seoul ISO datetimes consistently.

Why this fits the capstone:

- The app appears Korea-focused.
- It avoids confusing UTC conversion during presentation.
- Calendar display becomes easier to reason about.
- The current fixed schedule table already moved toward naive datetimes.

Recommended backend rules:

1. Treat every incoming datetime as Asia/Seoul.
2. If the input has timezone info, convert it to Asia/Seoul first.
3. Store the converted value as timezone-naive datetime.
4. Return datetimes consistently as the stored local value.
5. Use the same normalization helper in:
   - fixed schedules
   - flexible task due dates
   - calendar start/end query params
   - calendar response event times
   - planner range start/end
   - AI plan item scheduled times generated by allocation

Recommended helper behavior:

```python
KST = timezone(timedelta(hours=9))

def normalize_to_kst_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(KST).replace(tzinfo=None)
```

Important:

- Do not mix timezone-aware and timezone-naive datetimes inside allocation or calendar comparisons.
- Planner, calendar, fixed schedule, flexible task due dates, allocated tasks, and AI plan item scheduled times now follow this policy in code.
- Apply Alembic migration `e8f2a4c9d013` before relying on this policy in a shared Postgres database.

Alternative production policy:

- Store everything in UTC with timezone-aware columns.
- Convert to the user's timezone only at the API boundary.

That is cleaner for a real multi-timezone app, but it is more work and not necessary for this capstone unless multi-region users are part of the requirement.

## Final Backend API Shape To Aim For

This is the clean list I would present as the backend API surface.

### Public

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/users` | Signup |
| `POST` | `/users/login` | Login |
| `POST` | `/auth/google` | Google login |
| `GET` | `/health` | Health check |

### Authenticated

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/auth/me` | Current user |
| `POST` | `/schedules/fixed` | Create fixed schedule |
| `GET` | `/schedules/fixed` | List fixed schedules |
| `GET` | `/schedules/fixed/{schedule_id}` | Get fixed schedule |
| `PATCH` | `/schedules/fixed/{schedule_id}` | Update fixed schedule |
| `DELETE` | `/schedules/fixed/{schedule_id}` | Delete fixed schedule |
| `POST` | `/tasks/flexible` | Create flexible task |
| `GET` | `/tasks/flexible` | List flexible tasks |
| `GET` | `/tasks/flexible/{task_id}` | Get flexible task |
| `PATCH` | `/tasks/flexible/{task_id}` | Update flexible task |
| `DELETE` | `/tasks/flexible/{task_id}` | Delete flexible task |
| `POST` | `/goals/intake` | Parse goal input |
| `POST` | `/goals/complete` | Save goal and generate plan |
| `POST` | `/goals` | Manual goal creation, if needed |
| `GET` | `/goals` | List goals |
| `GET` | `/goals/{goal_id}` | Goal detail |
| `PATCH` | `/goals/{goal_id}` | Update goal |
| `POST` | `/planner/allocate` | Auto-allocate schedule |
| `GET` | `/calendar` | Unified calendar |
