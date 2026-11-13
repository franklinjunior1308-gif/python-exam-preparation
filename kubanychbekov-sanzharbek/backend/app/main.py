from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.body_limit import BodyLimitMiddleware
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.request_context import RequestIdMiddleware, configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="FixFlow API", version="0.1.0")
    configure_logging()
    register_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)  # outermost: also times CORS and error responses
    app.include_router(api_router)
    return app


app = create_app()
