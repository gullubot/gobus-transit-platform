"""
Transit Platform — FastAPI Application Entry Point.

BUILD 0: Infrastructure foundation only.
No domain routes, business logic, or product features.
"""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.operator import router as operator_router
from app.api.routes.tracking import router as tracking_router
from app.core.config import settings
from app.core.logging import logger, request_id_ctx


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info(
        "Starting %s v%s [env=%s]",
        settings.app_name,
        settings.app_version,
        settings.app_env,
    )
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title="Transit Platform API",
    description="Intelligent Transit Platform — Backend API (BUILD 2 Telemetry Foundation)",
    version=settings.app_version,
    lifespan=lifespan,
)

# ── CORS Middleware ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request ID Middleware ────────────────────────────────────────────
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Attach a unique request ID to each request for correlation logging."""
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    request_id_ctx.set(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


# ── Routes ───────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(operator_router)
app.include_router(tracking_router)
