from fastapi import APIRouter

from app.api.v1 import (
    auth,
    catalog,
    estimates,
    events,
    feedback,
    health,
    inventory,
    maintenance,
    organization,
    reports,
    requests,
    scheduling,
    sla,
    users,
    work,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(catalog.router)
api_router.include_router(reports.router)
api_router.include_router(requests.router)
api_router.include_router(scheduling.router)
api_router.include_router(work.router)
api_router.include_router(estimates.router)
api_router.include_router(inventory.router)
api_router.include_router(sla.router)
api_router.include_router(maintenance.router)
api_router.include_router(feedback.router)
api_router.include_router(users.router)
api_router.include_router(events.router)
api_router.include_router(organization.router)
