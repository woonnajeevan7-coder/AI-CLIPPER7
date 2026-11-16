"""
Clips API (/api/v1/clips)
Allows retrieval, transcript-based trimming, and presigned download generation.
"""

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Clip, User
from ..auth import get_current_user
from ..storage import storage

router = APIRouter(prefix="/clips", tags=["Clips"])


class TrimClipRequest(BaseModel):
    new_start_seconds: float
    new_end_seconds: float


@router.get("/{clip_id}")
def get_clip(
    clip_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found.")

    if not clip.project or clip.project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this clip.")

    download_url = storage.generate_presigned_download_url(clip.r2_key or f"clips/{clip.id}.mp4")

    return {
        "id": clip.id,
        "project_id": clip.project_id,
        "title": clip.title,
        "headline": clip.headline,
        "start_seconds": clip.start_seconds,
        "end_seconds": clip.end_seconds,
        "duration": clip.duration,
        "viral_score": clip.viral_score,
        "hook": clip.hook,
        "reason": clip.reason,
        "layout": clip.layout,
        "rubric": clip.rubric_json,
        "headline_variants": clip.headline_variants_json,
        "video_url": clip.video_url,
        "download_url": download_url
    }


@router.post("/{clip_id}/trim")
def trim_clip(
    clip_id: str,
    req: TrimClipRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found.")

    if not clip.project or clip.project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this clip.")

    if req.new_end_seconds <= req.new_start_seconds:
        raise HTTPException(status_code=400, detail="Invalid trim bounds: end must be greater than start.")

    clip.start_seconds = round(req.new_start_seconds, 2)
    clip.end_seconds = round(req.new_end_seconds, 2)
    clip.duration = round(req.new_end_seconds - req.new_start_seconds, 2)
    db.commit()

    return {
        "status": "trimmed",
        "clip_id": clip.id,
        "start_seconds": clip.start_seconds,
        "end_seconds": clip.end_seconds,
        "duration": clip.duration
    }
