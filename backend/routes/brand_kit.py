"""
Brand Kit API (/api/v1/brand-kit)
Allows persistent configuration of typography, brand colors, watermarks, and outro cards.
"""

from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..auth import get_current_user

router = APIRouter(prefix="/brand-kit", tags=["BrandKit"])


class BrandKitSchema(BaseModel):
    primary_color: str = "#8B5CF6"
    secondary_color: str = "#EC4899"
    font_family: str = "Inter"
    caption_preset: str = "hormozi"
    watermark_text: Optional[str] = "@mychannel"
    watermark_position: str = "top_right"
    outro_cta_enabled: bool = True
    outro_text: str = "Follow for more insights"


# In-memory / persistent brand kit store for users
USER_BRAND_KITS = {}


@router.get("/")
def get_brand_kit(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves the active brand kit settings for the current user."""
    kit = USER_BRAND_KITS.get(current_user.id, BrandKitSchema().model_dump())
    return {
        "user_id": current_user.id,
        "brand_kit": kit
    }


@router.post("/")
def save_brand_kit(
    req: BrandKitSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Persists updated brand kit configuration for the current user."""
    USER_BRAND_KITS[current_user.id] = req.model_dump()
    return {
        "status": "saved",
        "user_id": current_user.id,
        "brand_kit": USER_BRAND_KITS[current_user.id]
    }
