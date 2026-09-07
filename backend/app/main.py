"""
Transit Platform — FastAPI Application Entry Point.

BUILD 0: Infrastructure foundation only.
No domain routes, business logic, or product features.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.admin import router as admin_router
from app.api.routes.admin_network import router as admin_network_router
from app.api.routes.admin_fleet import router as admin_fleet_router
from app.api.routes.admin_live import router as admin_live_router
from app.api.routes.admin_alerts import router as admin_alerts_router
from app.api.routes.admin_fare import router as admin_fare_router
from app.api.routes.admin_insights import router as admin_insights_router
from app.api.routes.admin_service_schedules import router as admin_service_schedules_router
from app.api.routes.admin_users import router as admin_users_router
from app.api.routes.crowding import router as crowding_router
from app.api.routes.health import router as health_router
from app.api.routes.operator import router as operator_router
from app.api.routes.passenger import router as passenger_router
from app.api.routes.tracking import router as tracking_router
from app.core.config import settings
from app.core.logging import logger, request_id_ctx
from app.db.database import engine
from sqlalchemy.orm import Session
from app.services.alert_engine import AlertEngine


def _run_alert_evaluation():
    with Session(engine) as session:
        engine_eval = AlertEngine(session)
        engine_eval.run_all()

async def alert_evaluation_loop():
    """Background task to evaluate alerts periodically."""
    while True:
        try:
            await asyncio.to_thread(_run_alert_evaluation)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in alert_evaluation_loop: {e}", exc_info=True)
        
        await asyncio.sleep(60)



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info(
        "Starting %s v%s [env=%s]",
        settings.app_name,
        settings.app_version,
        settings.app_env,
    )
    
    alert_task = asyncio.create_task(alert_evaluation_loop())
    
    yield
    
    alert_task.cancel()
    try:
        await alert_task
    except asyncio.CancelledError:
        pass
        
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


# ── API Routes ───────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(admin_network_router, prefix="/api/admin", tags=["admin"])
app.include_router(admin_service_schedules_router, prefix="/api/admin/services", tags=["admin", "schedules"])
app.include_router(admin_fleet_router, prefix="/api/admin", tags=["admin", "fleet"])
app.include_router(admin_live_router, prefix="/api/admin", tags=["admin", "live"])
app.include_router(admin_alerts_router, prefix="/api/admin", tags=["admin", "alerts"])
app.include_router(admin_fare_router, prefix="/api/admin/fares", tags=["admin", "fares"])
app.include_router(admin_insights_router, prefix="/api/admin/insights", tags=["admin", "insights"])
app.include_router(admin_users_router, prefix="/api/admin/users", tags=["admin", "users"])
app.include_router(operator_router)
app.include_router(tracking_router)
app.include_router(crowding_router)
app.include_router(passenger_router)
