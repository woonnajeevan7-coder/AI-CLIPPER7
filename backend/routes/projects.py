"""
Project Ingestion & Lifecycle API (/api/v1/projects)
Enforces SSRF URL validation, checks tiered usage quotas, and triggers pipeline jobs.
"""

from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Project, Job, Usage
from ..auth import get_current_user
from ..security import SSRFGuard, SSRFValidationError
from ..config import settings
from ..tasks import process_pipeline_task

router = APIRouter(prefix="/projects", tags=["Projects"])


class CreateProjectRequest(BaseModel):
    title: str
    source_type: str = "youtube"  # 'youtube' or 'upload'
    source_url: Optional[str] = None
    num_clips: int = 3
    caption_style: str = "hormozi"
    framing_mode: Optional[str] = None


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_project(
    req: CreateProjectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Enforce usage limits for current billing period
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    usage = db.query(Usage).filter(
        Usage.user_id == current_user.id,
        Usage.period_month == current_month
    ).first()

    plan_limit = settings.PLAN_LIMITS.get(current_user.plan, settings.PLAN_LIMITS["free"])["monthly_clip_limit"]
    current_clips_count = usage.clips_created if usage else 0

    if current_clips_count >= plan_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Monthly limit of {plan_limit} clips reached for plan '{current_user.plan}'. Upgrade to Pro for more."
        )

    if current_clips_count + req.num_clips > plan_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requested {req.num_clips} clips would exceed monthly limit of {plan_limit} (currently used: {current_clips_count}) for plan '{current_user.plan}'. Upgrade to Pro for more."
        )

    # 2. SSRF Protection on URL Ingestion
    validated_url = req.source_url
    if req.source_type == "youtube" and req.source_url:
        try:
            validated_url = SSRFGuard.validate_ingest_url(req.source_url, enforce_domain_allowlist=True)
        except SSRFValidationError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"SSRF Security Violation: {str(e)}")

    # 3. Create Project & Job records
    project = Project(
        user_id=current_user.id,
        title=req.title,
        source_type=req.source_type,
        source_url=validated_url,
        status="pending"
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    job = Job(
        project_id=project.id,
        stage="queued",
        status="queued",
        progress=0
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 4. Trigger Celery Task non-blocking in background thread
    import threading
    def dispatch_celery():
        try:
            process_pipeline_task.apply_async(args=[project.id], retry=False)
        except Exception:
            pass

    threading.Thread(target=dispatch_celery, daemon=True).start()

    return {
        "project_id": project.id,
        "job_id": job.id,
        "title": project.title,
        "status": project.status,
        "created_at": project.created_at.isoformat()
    }


@router.get("/")
def list_projects(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = db.query(Project).filter(Project.user_id == current_user.id).order_by(Project.created_at.desc()).all()
    return [
        {
            "id": p.id,
            "title": p.title,
            "source_type": p.source_type,
            "source_url": p.source_url,
            "status": p.status,
            "created_at": p.created_at.isoformat(),
            "clip_count": len(p.clips)
        }
        for p in projects
    ]


@router.get("/{project_id}")
def get_project(project_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    return {
        "id": project.id,
        "title": project.title,
        "source_type": project.source_type,
        "source_url": project.source_url,
        "status": project.status,
        "created_at": project.created_at.isoformat(),
        "clips": [
            {
                "id": c.id,
                "title": c.title,
                "headline": c.headline,
                "duration": c.duration,
                "viral_score": c.viral_score,
                "video_url": c.video_url,
                "layout": c.layout
            }
            for c in project.clips
        ]
    }
