from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["health"])

DbDep = Annotated[Session, Depends(get_db)]


@router.get("/live")
def live() -> dict[str, str]:
    """Liveness: the process is up. Does not touch the database."""
    return {"status": "ok"}


@router.get("/ready", response_model=None)
def ready(db: DbDep) -> dict[str, str] | JSONResponse:
    """Readiness: the database answers. Non-2xx when it does not."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "down"})
    return {"status": "ok", "database": "up"}
