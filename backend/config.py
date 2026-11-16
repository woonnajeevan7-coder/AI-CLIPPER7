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
