"""
Live Streams API (/api/v1/live)
Provides SSE event streaming (/api/v1/live/{id}/events) and live session controls.
Enforces authentication and multi-tenant resource ownership on all endpoints.
"""

from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import LiveSession, LiveSegment, Clip, User
from ..auth import get_current_user
from ..sse import live_session_event_stream
from live.supervisor import supervisor, RightsNotConfirmedError, LowDiskSpaceError, PlanLimitExceededError, LiveDisabledError

router = APIRouter(prefix="/live", tags=["Live"])


class CreateLiveSessionRequest(BaseModel):
    title: str
    platform: str = "rtmp"
    source_type: str = "rtmp"
    stream_url: Optional[str] = None
    rights_confirmed: bool = False
    target_framing: str = "sports_gaming"
    caption_style: str = "sports_gaming"
    interval_seconds: int = 60
    rolling_buffer_minutes: int = 15


@router.get("/{session_id}/events")
async def live_session_events(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Server-Sent Events (SSE) telemetry stream for a live session.
    Yields:
    - segment_recorded
    - clip_created
    - clip_ready
    - error
    """
    session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Live session not found.")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access telemetry for this live session.")

    return StreamingResponse(
        live_session_event_stream(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/sessions")
def list_live_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all live sessions belonging to the authenticated user."""
    sessions = (
        db.query(LiveSession)
        .filter(LiveSession.user_id == current_user.id)
        .order_by(LiveSession.created_at.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "title": s.title,
            "platform": s.platform,
            "status": s.status,
            "source_type": s.source_type,
            "stream_key": s.stream_key,
            "rights_confirmed": s.rights_confirmed,
            "started_at": s.started_at,
            "stopped_at": s.stopped_at,
            "created_at": s.created_at,
        }
        for s in sessions
    ]


@router.get("/{session_id}")
def get_live_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns details, recorded segments count, and generated clips for a live session."""
    session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Live session not found.")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this live session.")

    clips = (
        db.query(Clip)
        .filter(Clip.live_session_id == session_id)
        .order_by(Clip.clip_index.asc())
        .all()
    )

    return {
        "id": session.id,
        "title": session.title,
        "platform": session.platform,
        "status": session.status,
        "source_type": session.source_type,
        "stream_key": session.stream_key,
        "rights_confirmed": session.rights_confirmed,
        "started_at": session.started_at,
        "stopped_at": session.stopped_at,
        "clips": [
            {
                "id": c.id,
                "clip_index": c.clip_index,
                "title": c.title,
                "headline": c.headline,
                "source": c.source,
                "status": c.status,
                "start_seconds": c.start_seconds,
                "end_seconds": c.end_seconds,
                "duration": c.duration,
                "video_url": c.video_url
            }
            for c in clips
        ]
    }


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_and_start_live_session(
    req: CreateLiveSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Creates a new live session and launches the supervised recorder."""
    import secrets
    import uuid

    is_external = (req.platform != "rtmp" and req.source_type != "rtmp")
    if is_external and not req.rights_confirmed:
        raise HTTPException(
            status_code=403,
            detail="Authorized streams only: require rights_confirmed=true when starting external capture."
        )

    stream_key = secrets.token_urlsafe(24) if req.source_type == "rtmp" else None
    session_id = str(uuid.uuid4())

    session = LiveSession(
        id=session_id,
        user_id=current_user.id,
        title=req.title,
        platform=req.platform,
        source_type=req.source_type,
        stream_key=stream_key,
        stream_url=req.stream_url or "",
        rights_confirmed=req.rights_confirmed,
        target_framing=req.target_framing,
        caption_style=req.caption_style,
        rolling_buffer_minutes=req.rolling_buffer_minutes,
        status="starting"
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    try:
        await supervisor.start_session(session_id)
    except (RightsNotConfirmedError, PlanLimitExceededError) as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except (LowDiskSpaceError, LiveDisabledError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start live supervisor: {exc}")

    return {
        "id": session.id,
        "title": session.title,
        "status": session.status,
        "stream_key": session.stream_key,
        "rtmp_ingest_url": f"rtmp://localhost/live/{session.stream_key}" if session.stream_key else None
    }


@router.post("/{session_id}/stop")
async def stop_live_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stops the active live session recorder and supervisor."""
    session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Live session not found.")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to stop this live session.")

    await supervisor.stop_session(session_id)
    db.refresh(session)
    return {
        "status": "stopped",
        "session_id": session_id,
        "stopped_at": session.stopped_at
    }
