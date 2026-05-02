from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["demo"])

ROUTE_DIR = Path(__file__).parent
API_PLAYGROUND_PATH = ROUTE_DIR / "api_playground.html"
CALENDAR_DEMO_PATH = ROUTE_DIR / "calendar_demo.html"
USER_FLOW_DEMO_PATH = ROUTE_DIR / "user_flow_demo.html"


def _read_html(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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
