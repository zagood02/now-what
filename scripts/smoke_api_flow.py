from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import sys
from typing import Any
from uuid import uuid4

import httpx


KST = timezone(timedelta(hours=9), "KST")
DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/v1"
DEFAULT_PASSWORD = "SmokeTest123!"


@dataclass
class StepResult:
    name: str
    detail: str = ""


class SmokeApiClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=timeout)
        self.results: list[StepResult] = []

    def close(self) -> None:
        self.client.close()

    def set_token(self, token: str) -> None:
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    def step(self, name: str, detail: str = "") -> None:
        self.results.append(StepResult(name=name, detail=detail))
        suffix = f" - {detail}" if detail else ""
        print(f"[OK] {name}{suffix}")

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self.client.request(method, path, **kwargs)
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Could not connect to {self.base_url}. Start the backend first, for example: "
                ".\\.venv\\Scripts\\uvicorn.exe backend.main:app --reload"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"{method} {path} failed before receiving a response: {exc}") from exc

        if response.status_code >= 400:
            body = response.text
            raise RuntimeError(
                f"{method} {path} returned {response.status_code}.\n"
                f"Response body:\n{body}"
            )
        return response


def iso_at(days_from_now: int, hour: int, minute: int = 0) -> str:
    target_day = datetime.now(KST).date() + timedelta(days=days_from_now)
    return datetime(
        target_day.year,
        target_day.month,
        target_day.day,
        hour,
        minute,
        tzinfo=KST,
    ).isoformat()


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def create_or_login_user(api: SmokeApiClient, email: str, password: str) -> dict[str, Any]:
    payload = {
        "email": email,
        "name": "Smoke Test User",
        "password": password,
        "timezone": "Asia/Seoul",
    }
    response = api.client.post("/users", json=payload)
    if response.status_code == 409:
        api.step("signup", "user already exists; logging in")
    elif response.status_code >= 400:
        raise RuntimeError(f"POST /users returned {response.status_code}.\n{response.text}")
    else:
        api.step("signup", f"user_id={response.json()['id']}")

    login = api.request(
        "POST",
        "/users/login",
        json={"email": email, "password": password},
    ).json()
    api.set_token(login["access_token"])
    api.step("login", f"user_id={login['user']['id']}")
    return login["user"]


def run_smoke_flow(api: SmokeApiClient, email: str, password: str) -> None:
    api.request("GET", "/health")
    api.step("health")

    user = create_or_login_user(api, email, password)

    me = api.request("GET", "/auth/me").json()
    expect(me["id"] == user["id"], "GET /auth/me returned a different user.")
    api.step("auth/me", f"user_id={me['id']}")

    fixed_schedule = api.request(
        "POST",
        "/schedules/fixed",
        json={
            "title": "Smoke fixed schedule",
            "description": "Created by scripts/smoke_api_flow.py",
            "location": "Capstone lab",
            "start_at": iso_at(1, 10),
            "end_at": iso_at(1, 11),
            "is_all_day": False,
        },
    ).json()
    schedule_id = fixed_schedule["id"]
    api.step("create fixed schedule", f"schedule_id={schedule_id}")

    fixed_list = api.request(
        "GET",
        "/schedules/fixed",
        params={"start": iso_at(1, 0), "end": iso_at(2, 0)},
    ).json()
    expect(any(item["id"] == schedule_id for item in fixed_list), "Created fixed schedule was not listed.")
    api.step("list fixed schedules", f"count={len(fixed_list)}")

    fixed_detail = api.request("GET", f"/schedules/fixed/{schedule_id}").json()
    expect(fixed_detail["id"] == schedule_id, "Fixed schedule detail returned the wrong id.")
    api.step("get fixed schedule", f"schedule_id={schedule_id}")

    api.request(
        "PATCH",
        f"/schedules/fixed/{schedule_id}",
        json={"location": "Updated capstone lab"},
    )
    api.step("update fixed schedule", f"schedule_id={schedule_id}")

    flexible_task = api.request(
        "POST",
        "/tasks/flexible",
        json={
            "title": "Smoke flexible task",
            "description": "Verify planner allocation.",
            "estimated_minutes": 60,
            "min_session_minutes": 30,
            "preferred_session_minutes": 60,
            "max_minutes_per_day": 90,
            "priority": 3,
            "due_at": iso_at(1, 18),
            "details_json": {"source": "smoke"},
        },
    ).json()
    task_id = flexible_task["id"]
    api.step("create flexible task", f"task_id={task_id}")

    task_list = api.request("GET", "/tasks/flexible").json()
    expect(any(item["id"] == task_id for item in task_list), "Created flexible task was not listed.")
    api.step("list flexible tasks", f"count={len(task_list)}")

    task_detail = api.request("GET", f"/tasks/flexible/{task_id}").json()
    expect(task_detail["id"] == task_id, "Flexible task detail returned the wrong id.")
    api.step("get flexible task", f"task_id={task_id}")

    api.request(
        "PATCH",
        f"/tasks/flexible/{task_id}",
        json={"description": "Verify planner allocation after update."},
    )
    api.step("update flexible task", f"task_id={task_id}")

    goal = api.request(
        "POST",
        "/goals",
        json={
            "title": "Smoke capstone goal",
            "description": "Manual goal creation smoke test.",
            "category": "work",
            "status": "active",
            "target_date": (datetime.now(KST).date() + timedelta(days=7)).isoformat(),
            "details_json": {"source": "smoke"},
            "answers_json": {"weekly_available_hours": 5},
        },
    ).json()
    goal_id = goal["id"]
    api.step("create goal", f"goal_id={goal_id}")

    goals = api.request("GET", "/goals").json()
    expect(any(item["id"] == goal_id for item in goals), "Created goal was not listed.")
    api.step("list goals", f"count={len(goals)}")

    goal_detail = api.request("GET", f"/goals/{goal_id}").json()
    expect(goal_detail["id"] == goal_id, "Goal detail returned the wrong id.")
    api.step("get goal", f"goal_id={goal_id}")

    allocation = api.request(
        "POST",
        "/planner/allocate",
        json={
            "range_start": iso_at(1, 9),
            "range_end": iso_at(1, 18),
            "day_start": "09:00",
            "day_end": "18:00",
            "clear_existing": False,
        },
    ).json()
    expect(
        len(allocation["allocated_tasks"]) + len(allocation["scheduled_plan_items"]) > 0,
        "Planner did not allocate any task or plan item.",
    )
    api.step(
        "planner allocate",
        f"allocated_tasks={len(allocation['allocated_tasks'])}, plan_items={len(allocation['scheduled_plan_items'])}",
    )

    calendar = api.request(
        "GET",
        "/calendar",
        params={"start": iso_at(1, 0), "end": iso_at(2, 0)},
    ).json()
    events = calendar["events"]
    expect(
        any(event["source_type"] == "fixed_schedule" and event["source_id"] == schedule_id for event in events),
        "Calendar did not include the created fixed schedule.",
    )
    expect(
        any(event["source_type"] == "allocated_task" for event in events),
        "Calendar did not include an allocated task.",
    )
    api.step("calendar", f"events={len(events)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the capstone backend API smoke flow.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"API base URL. Default: {DEFAULT_BASE_URL}")
    parser.add_argument("--email", default=None, help="User email to create/login. Defaults to a unique smoke email.")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Password for the smoke user.")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    email = args.email or f"smoke-{datetime.now(KST):%Y%m%d%H%M%S}-{uuid4().hex[:8]}@example.com"

    api = SmokeApiClient(base_url=args.base_url, timeout=args.timeout)
    try:
        run_smoke_flow(api, email=email, password=args.password)
    except RuntimeError as exc:
        print("")
        print("[FAIL] Smoke API flow failed")
        print(str(exc))
        return 1
    finally:
        api.close()

    print("")
    print("[PASS] Smoke API flow completed")
    print(f"base_url={args.base_url.rstrip('/')}")
    print(f"email={email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
