"""
FastAPI Platform Application Entry Point
REST API (/api/v1) with JWT auth, SSRF protection, Celery tasks, Sentry, Request IDs, and real-time SSE telemetry.
"""

import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .database import init_db
from .telemetry import init_sentry, logger
from .routes import auth, projects, jobs, clips, usage, legal

# Initialize Sentry & database tables
init_sentry()
init_db()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


# Add Middlewares
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(projects.router, prefix=settings.API_V1_PREFIX)
app.include_router(jobs.router, prefix=settings.API_V1_PREFIX)
app.include_router(clips.router, prefix=settings.API_V1_PREFIX)
app.include_router(usage.router, prefix=settings.API_V1_PREFIX)
app.include_router(legal.router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
def health_check():
    import subprocess
    import shutil
    from ffmpeg_utils import get_ffmpeg_bin, get_ffprobe_bin

    ffmpeg_path = get_ffmpeg_bin()
    ffprobe_path = get_ffprobe_bin()
    ffmpeg_ok = bool(ffmpeg_path and (shutil.which(str(ffmpeg_path)) or ffmpeg_path.exists()))
    ffprobe_ok = bool(ffprobe_path and (shutil.which(str(ffprobe_path)) or ffprobe_path.exists()))

    # Real NVENC probe
    nvenc_ok = False
    if ffmpeg_ok:
        try:
            cmd = [str(ffmpeg_path), "-encoders"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2)
            nvenc_ok = "h264_nvenc" in res.stdout
        except Exception:
            nvenc_ok = False

    # Real face tracking probe
    face_tracking_ok = False
    try:
        import cv2
        face_tracking_ok = True
    except Exception:
        face_tracking_ok = False

    # Real database ping
    db_ok = False
    try:
        from backend.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        db_ok = False

    # Real Groq key configuration
    groq_ok = bool(settings.GROQ_API_KEY and len(settings.GROQ_API_KEY) > 5)

    # Storage type
    storage_type = "r2" if (settings.R2_ACCOUNT_ID and settings.R2_ACCESS_KEY_ID) else "local"

    overall_status = "healthy" if (ffmpeg_ok and db_ok) else "degraded"

    return {
        "status": overall_status,
        "service": settings.PROJECT_NAME,
        "api_version": "v1",
        "capabilities": {
            "ffmpeg": ffmpeg_ok,
            "ffprobe": ffprobe_ok,
            "gpu_nvenc": nvenc_ok,
            "face_tracking": face_tracking_ok,
            "database": db_ok,
            "groq_api": groq_ok,
            "storage": storage_type,
            "ssrf_guard": True
        },
        "features": {
            "gpu_nvenc": nvenc_ok,
            "face_tracking": face_tracking_ok,
            "ssrf_guard": True,
            "ffmpeg": ffmpeg_ok,
            "ffprobe": ffprobe_ok,
            "database": db_ok
        }
    }
