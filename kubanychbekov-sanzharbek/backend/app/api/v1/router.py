from fastapi import APIRouter

from app.api.v1 import auth, catalog, health, reports, requests, scheduling, work

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(catalog.router)
api_router.include_router(reports.router)
api_router.include_router(requests.router)
api_router.include_router(scheduling.router)
api_router.include_router(work.router)
