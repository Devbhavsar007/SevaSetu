from __future__ import annotations

"""
FastAPI Application Entry Point.
Configures CORS, includes all routers, initializes DB on startup.
"""

import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .database import init_db
from .seeder import seed_database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

settings = get_settings()


# ============================================================
# LIFESPAN — startup / shutdown
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle events."""
    # STARTUP
    logger.info(f"🚀 Starting {settings.APP_NAME} ({settings.APP_ENV})")

    # Create upload directory
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    # Initialize database tables
    init_db()
    
    # Seed database with demo data
    seed_database()

    logger.info("✅ Database initialized")
    logger.info(f"📁 Uploads directory: {os.path.abspath(settings.UPLOAD_DIR)}")
    logger.info(f"🌐 CORS origins: {settings.cors_origins}")

    yield

    # SHUTDOWN
    logger.info("👋 Shutting down...")


# ============================================================
# APP CREATION
# ============================================================
app = FastAPI(
    title="Smart Resource Allocation API",
    description=(
        "Data-Driven Volunteer Coordination for Social Impact. "
        "Digitize field surveys with OCR, visualize needs on a crisis map, "
        "and smart-match volunteers using a weighted scoring algorithm."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ============================================================
# MIDDLEWARE
# ============================================================

# CORS

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,  # ✅ Ab kaam karega
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

# Rate limiter (Task 3.1)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc) if settings.DEBUG else "Something went wrong"},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
    )


# ============================================================
# INCLUDE ROUTERS
# ============================================================
from .routes import auth, needs, volunteers, matching, analytics, ocr, broadcast, realtime
from .routes import predictions, inventory

app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(needs.router, prefix=settings.API_V1_PREFIX)
app.include_router(volunteers.router, prefix=settings.API_V1_PREFIX)
app.include_router(matching.router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics.router, prefix=settings.API_V1_PREFIX)
app.include_router(ocr.router, prefix=settings.API_V1_PREFIX)
app.include_router(broadcast.router, prefix=settings.API_V1_PREFIX)
app.include_router(realtime.router)  # WebSocket — no prefix needed
app.include_router(predictions.router, prefix=settings.API_V1_PREFIX)
app.include_router(inventory.router, prefix=settings.API_V1_PREFIX)


# ============================================================
# STATIC FILES (uploaded images)
# ============================================================
upload_path = Path(settings.UPLOAD_DIR)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")


# ============================================================
# ROOT & HEALTH ENDPOINTS
# ============================================================

@app.get("/", tags=["System"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "api_prefix": settings.API_V1_PREFIX,
    }


@app.get("/health", tags=["System"])
async def health_check():
    """Health check for monitoring and load balancers."""
    from .database import SessionLocal, get_database_engine_name
    from sqlalchemy import text
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "database_engine": get_database_engine_name(),
        "environment": settings.APP_ENV,
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "firebase_configured": Path(settings.FIREBASE_CREDENTIALS_PATH).exists(),
    }
