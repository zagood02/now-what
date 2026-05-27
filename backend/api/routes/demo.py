import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from backend.core.config import settings

router = APIRouter(tags=["demo"])

ROUTE_DIR = Path(__file__).parent
API_PLAYGROUND_PATH = ROUTE_DIR / "api_playground.html"
CALENDAR_DEMO_PATH = ROUTE_DIR / "calendar_demo.html"
USER_FLOW_DEMO_PATH = ROUTE_DIR / "user_flow_demo.html"


def _read_html(path: Path) -> str:
    html = path.read_text(encoding="utf-8")
    defaults_script = (
        "<script>"
        f"window.__APP_DEFAULTS__ = {json.dumps(_allocation_defaults())};"
        "</script>"
    )
    return html.replace("</head>", f"    {defaults_script}\n  </head>", 1)


def _allocation_defaults() -> dict[str, int | str]:
    return {
        "dayStart": settings.default_day_start,
        "dayEnd": settings.default_day_end,
        "bufferMinutes": settings.default_buffer_minutes,
        "maxAutoMinutesPerDay": settings.default_max_auto_minutes_per_day,
    }


@router.get("/demo/api-playground", include_in_schema=False, response_class=HTMLResponse)
@router.get("/demo/goal-intake", include_in_schema=False, response_class=HTMLResponse)
def api_playground() -> str:
    return _read_html(API_PLAYGROUND_PATH)


@router.get("/demo/calendar", include_in_schema=False, response_class=HTMLResponse)
@router.get("/demo/calendar-view", include_in_schema=False, response_class=HTMLResponse)
def calendar_demo() -> str:
    return _read_html(CALENDAR_DEMO_PATH)


@router.get("/demo/user-flow", include_in_schema=False, response_class=HTMLResponse)
def user_flow_demo() -> str:
    return _read_html(USER_FLOW_DEMO_PATH)
