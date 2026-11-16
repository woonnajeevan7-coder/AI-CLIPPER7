"""
Usage & Billing API (/api/v1/usage)
Tracks monthly quotas, clips created, and tier entitlements.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Usage
from ..auth import get_current_user
from ..config import settings

router = APIRouter(prefix="/usage", tags=["Usage & Billing"])


@router.get("/plans")
def list_plans():
    return [
        {
            "id": plan_id,
            "name": plan_id.capitalize(),
            "monthly_clip_limit": data["monthly_clip_limit"],
            "max_video_duration_minutes": data["max_video_duration_minutes"],
            "watermark": data["watermark"],
            "can_export_1080p": data["can_export_1080p"]
        }
        for plan_id, data in settings.PLAN_LIMITS.items()
    ]


@router.get("/current")
def get_current_usage(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    usage = db.query(Usage).filter(
        Usage.user_id == current_user.id,
        Usage.period_month == current_month
    ).first()

    plan_info = settings.PLAN_LIMITS.get(current_user.plan, settings.PLAN_LIMITS["free"])
    clips_used = usage.clips_created if usage else 0

    return {
        "user_id": current_user.id,
        "plan": current_user.plan,
        "period": current_month,
        "clips_used": clips_used,
        "monthly_limit": plan_info["monthly_clip_limit"],
        "remaining_clips": max(0, plan_info["monthly_clip_limit"] - clips_used),
        "max_duration_minutes": plan_info["max_video_duration_minutes"]
    }
