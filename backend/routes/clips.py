"""
Clips API (/api/v1/clips)
Allows retrieval, transcript-based trimming, and presigned download generation.
"""

from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Clip, User
from ..auth import get_current_user
from ..storage import storage

router = APIRouter(prefix="/clips", tags=["Clips"])


class TrimClipRequest(BaseModel):
    new_start_seconds: float
    new_end_seconds: float


class ProcessClipRequest(BaseModel):
    framing_mode: Optional[str] = None  # 'gaming', 'sports_gaming', 'action_crop', 'single_face', 'split_screen', 'blur_fallback', 'auto'


@router.get("/{clip_id}")
def get_clip(
    clip_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        if clip_id.startswith("clip_"):
            return {
                "id": clip_id,
                "project_id": "proj_demo",
                "title": "Connecting the Dots Intro",
                "headline": "THREE STORIES THAT CHANGED EVERYTHING",
                "start_seconds": 27.0,
                "end_seconds": 54.3,
                "duration": 27.3,
                "viral_score": 95,
                "hook": "You cannot connect the dots looking forward.",
                "layout": "single_face",
                "video_url": "/sample_short.mp4",
                "download_url": "/sample_short.mp4"
            }
        raise HTTPException(status_code=404, detail="Clip not found.")

    owner_id = clip.project.user_id if clip.project else (clip.live_session.user_id if clip.live_session else None)
    if owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this clip.")

    download_url = storage.generate_presigned_download_url(clip.r2_key or f"clips/{clip.id}.mp4")

    return {
        "id": clip.id,
        "project_id": clip.project_id,
        "live_session_id": clip.live_session_id,
        "clip_index": clip.clip_index,
        "source": clip.source,
        "status": clip.status,
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


@router.post("/{clip_id}/process")
def process_clip(
    clip_id: str,
    background_tasks: BackgroundTasks,
    req: Optional[ProcessClipRequest] = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lazy enhancement endpoint: triggers the full 9:16 vertical motion framing
    and dynamic captions rendering when the user approves or opens a raw cut.
    Allows explicit framing_mode from the UI.
    """
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found.")

    owner_id = clip.project.user_id if clip.project else (clip.live_session.user_id if clip.live_session else None)
    if owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to process this clip.")

    if clip.status == "completed":
        return {
            "status": "completed",
            "clip_id": clip.id,
            "message": "Clip is already enhanced and ready.",
            "video_url": clip.video_url
        }

    explicit_mode = req.framing_mode if req and req.framing_mode else None
    if explicit_mode:
        clip.layout = explicit_mode

    clip.status = "processing"
    db.commit()

    # Try Celery task first, fallback to background_tasks
    try:
        from ..tasks import enhance_live_clip_task
        enhance_live_clip_task.apply_async(args=[clip.id, explicit_mode], retry=False)
    except Exception:
        from live.enhancer import enhance_clip_sync
        background_tasks.add_task(enhance_clip_sync, clip.id, explicit_mode)

    return {
        "status": "processing",
        "clip_id": clip.id,
        "message": "Enhancement job queued: rendering 9:16 vertical motion canvas and captions."
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
        if clip_id.startswith("clip_"):
            if req.new_end_seconds <= req.new_start_seconds:
                raise HTTPException(status_code=400, detail="Invalid trim bounds: end must be greater than start.")
            return {
                "status": "trimmed",
                "clip_id": clip_id,
                "start_seconds": round(req.new_start_seconds, 2),
                "end_seconds": round(req.new_end_seconds, 2),
                "duration": round(req.new_end_seconds - req.new_start_seconds, 2)
            }
        raise HTTPException(status_code=404, detail="Clip not found.")

    owner_id = clip.project.user_id if clip.project else (clip.live_session.user_id if clip.live_session else None)
    if owner_id != current_user.id:
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
