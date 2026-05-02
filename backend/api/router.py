from fastapi import APIRouter

from backend.api.routes import calendar, demo, fixed_schedules, flexible_tasks, goals, health, planner, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(users.router)
api_router.include_router(fixed_schedules.router)
api_router.include_router(flexible_tasks.router)
api_router.include_router(goals.router)
api_router.include_router(planner.router)
api_router.include_router(calendar.router)
api_router.include_router(demo.router)
