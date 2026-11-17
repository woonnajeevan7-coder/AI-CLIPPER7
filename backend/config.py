"""
Backend Configuration & Settings
Environment-backed configuration for database, Redis, JWT, and Cloudflare R2 storage.
"""

import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "AI Clipper Pro"
    API_V1_PREFIX: str = "/api/v1"
    
    # Auth & Tokens
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    JWT_SECRET_KEY: str
    TOKEN_ENCRYPTION_KEY: str = os.getenv("TOKEN_ENCRYPTION_KEY", "ReuO4DTAmNr_e0_B5Q4bi-A0yiU2nRp38Lua542Q4bs=")

    # Twitch Integration & EventSub
    TWITCH_CLIENT_ID: str = os.getenv("TWITCH_CLIENT_ID", "")
    TWITCH_CLIENT_SECRET: str = os.getenv("TWITCH_CLIENT_SECRET", "")
    TWITCH_REDIRECT_URI: str = os.getenv("TWITCH_REDIRECT_URI", "http://localhost:8000/api/v1/twitch/callback")
    TWITCH_EVENTSUB_SECRET: str = os.getenv("TWITCH_EVENTSUB_SECRET", "default_test_eventsub_secret_32b")
    TWITCH_WEBHOOK_CALLBACK_URL: str = os.getenv("TWITCH_WEBHOOK_CALLBACK_URL", "")

    # Live Streaming & Ingest Settings
    LIVE_ENABLED: bool = os.getenv("LIVE_ENABLED", "true").lower() in ("true", "1", "yes")
    RTMP_BASE_URL: str = os.getenv("RTMP_BASE_URL", "rtmp://localhost:1935/live")
    LIVE_SEGMENT_DURATION_SECONDS: float = float(os.getenv("LIVE_SEGMENT_DURATION_SECONDS", "6.0"))
    LIVE_ROLLING_BUFFER_MINUTES: int = int(os.getenv("LIVE_ROLLING_BUFFER_MINUTES", "15"))
    MIN_DISK_FREE_GB: float = float(os.getenv("MIN_DISK_FREE_GB", "5.0"))

    # Groq Engine Brain
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # CORS Configuration (Restricted to known origins)
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8501,http://127.0.0.1:8501"
        ).split(",")
        if origin.strip()
    ]

    def __init__(self):
        jwt_key = os.getenv("JWT_SECRET_KEY")
        if not jwt_key:
            raise RuntimeError(
                "CRITICAL: JWT_SECRET_KEY environment variable is required but not set. "
                "Set JWT_SECRET_KEY in your environment or .env file before starting the server."
            )
        self.JWT_SECRET_KEY = jwt_key
    
    # Database (PostgreSQL with SQLite local dev fallback)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{Path(__file__).parent.parent / 'ai_clipper.db'}"
    )

    # Redis & Celery
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
    CELERY_CONCURRENCY: int = int(os.getenv("CELERY_CONCURRENCY", "3"))

    # Cloudflare R2 / S3 Storage
    R2_ACCOUNT_ID: str = os.getenv("R2_ACCOUNT_ID", "mock_r2_account")
    R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID", "mock_r2_key")
    R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY", "mock_r2_secret")
    R2_BUCKET_NAME: str = os.getenv("R2_BUCKET_NAME", "ai-clipper-storage")
    R2_ENDPOINT_URL: str = os.getenv(
        "R2_ENDPOINT_URL",
        f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    )

    # Tiered Plans & Limits
    PLAN_LIMITS: Dict[str, Dict[str, Any]] = {
        "free": {
            "monthly_clip_limit": 5,
            "max_video_duration_minutes": 15,
            "max_concurrent_jobs": 1,
            "watermark": True,
            "can_export_1080p": True
        },
        "pro": {
            "monthly_clip_limit": 100,
            "max_video_duration_minutes": 90,
            "max_concurrent_jobs": 3,
            "watermark": False,
            "can_export_1080p": True
        },
        "agency": {
            "monthly_clip_limit": 500,
            "max_video_duration_minutes": 180,
            "max_concurrent_jobs": 8,
            "watermark": False,
            "can_export_1080p": True
        }
    }


settings = Settings()
