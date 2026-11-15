"""
Cloudflare R2 / S3 Storage Engine
Manages presigned upload/download URLs, video caching, and asset persistence.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import boto3
from botocore.config import Config
from .config import settings


class StorageManager:
    """Provides Cloudflare R2 storage with seamless local filesystem fallback."""

    def __init__(self):
        self.is_configured = (
            settings.R2_ACCESS_KEY_ID != "mock_r2_key"
            and settings.R2_SECRET_ACCESS_KEY != "mock_r2_secret"
        )
        self.local_storage_dir = Path(__file__).parent.parent / "temp_media" / "r2_local"
        self.local_storage_dir.mkdir(parents=True, exist_ok=True)

        if self.is_configured:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=settings.R2_ENDPOINT_URL,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                config=Config(signature_version="s3v4")
            )
        else:
            self.s3_client = None

    def upload_file(self, local_path: Path, object_key: str) -> str:
        """Uploads a local video/asset and returns access URI."""
        if self.s3_client:
            self.s3_client.upload_file(str(local_path), settings.R2_BUCKET_NAME, object_key)
            return f"{settings.R2_ENDPOINT_URL}/{settings.R2_BUCKET_NAME}/{object_key}"
        
        # Local fallback
        dest = self.local_storage_dir / object_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(local_path, dest)
        return str(dest.resolve())

    def generate_presigned_upload_url(self, object_key: str, expiration_seconds: int = 3600) -> str:
        if self.s3_client:
            return self.s3_client.generate_presigned_url(
                "put_object",
                Params={"Bucket": settings.R2_BUCKET_NAME, "Key": object_key},
                ExpiresIn=expiration_seconds
            )
        return f"/api/v1/mock-upload/{object_key}"

    def generate_presigned_download_url(self, object_key: str, expiration_seconds: int = 3600) -> str:
        if self.s3_client:
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.R2_BUCKET_NAME, "Key": object_key},
                ExpiresIn=expiration_seconds
            )
        return f"/api/v1/clips/download/{object_key}"


storage = StorageManager()
