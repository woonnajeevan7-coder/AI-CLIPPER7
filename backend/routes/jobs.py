"""
Jobs API & Real-Time SSE Progress Stream (/api/v1/jobs)
Provides streaming server-sent events to monitor multi-agent pipeline progress live.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Job, User
from ..auth import get_current_user, get_current_user_sse
from ..sse import job_progress_sse_stream

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/{job_id}/stream")
async def stream_job_telemetry(
    job_id: str,
    current_user: User = Depends(get_current_user_sse),
    db: Session = Depends(get_db)
):
    """
    Server-Sent Events endpoint streaming real-time stage progress to the client.
    Guarded by auth and project ownership.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if not job.project or job.project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this job stream.")

    return StreamingResponse(
        job_progress_sse_stream(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/{job_id}")
def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if not job.project or job.project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this job.")

    return {
        "id": job.id,
        "project_id": job.project_id,
        "stage": job.stage,
        "status": job.status,
        "progress": job.progress,
        "error": job.error,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None
    }
