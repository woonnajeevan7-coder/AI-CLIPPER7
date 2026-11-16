"""
Celery Task Worker Engine
Wraps TranscriberAgent, CuratorAgent, JudgeAgent, and EditorAgent as idempotent tasks
with exponential-backoff retries and dead-letter failure handling.
"""

from pathlib import Path
from celery import Celery
from datetime import datetime, timezone

from .config import settings
from .database import SessionLocal
from .models import Job, Project, Transcript, Clip, User, Usage
from .storage import storage
from agents import ClipperOrchestratorAgent

celery_app = Celery(
    "ai_clipper_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True
)
def process_pipeline_task(self, project_id: str):
    """
    Idempotent end-to-end multi-agent pipeline task with automatic retries and dead-letter state.
    """
    db = SessionLocal()
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        db.close()
        return {"error": "Project not found"}

    job = db.query(Job).filter(Job.project_id == project_id).first()
    if not job:
        job = Job(project_id=project_id, stage="ingestion", status="running", progress=10)
        db.add(job)
        db.commit()
    else:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

    project_root = Path(__file__).parent.parent
    orchestrator = ClipperOrchestratorAgent(
        project_root=project_root,
        api_key=settings.GROQ_API_KEY,
        provider="groq"
    )

    try:
        # Check if project was already completed (idempotency check)
        existing_clips = db.query(Clip).filter(Clip.project_id == project_id).all()
        if existing_clips and project.status == "completed":
            job.status = "completed"
            job.progress = 100
            db.commit()
            db.close()
            return {"status": "already_completed", "clip_count": len(existing_clips)}

        is_url = (project.source_type == "youtube")
        source = project.source_url
        if not source:
            raise ValueError(f"Project '{project.id}' has no valid source_url or file path.")

        generator = orchestrator.run_pipeline(
            source=source,
            is_url=is_url,
            num_clips=3
        )

        rendered_results = []
        for event in generator:
            agent = event.get("agent", "")
            status_text = event.get("status", "")
            progress = event.get("progress", 0)

            # Update job state
            job.stage = agent
            job.progress = progress
            db.commit()

            if "result" in event:
                rendered_results = event["result"]

        # Persist rendered clips into PostgreSQL
        for item in rendered_results:
            c_data = item["data"]
            c_path = Path(item["path"])
            
            # Upload to Cloudflare R2 / S3 storage
            r2_key = f"clips/{project_id}/{c_path.name}"
            access_url = storage.upload_file(c_path, r2_key)

            db_clip = Clip(
                project_id=project_id,
                title=c_data.get("title", "Clip"),
                headline=c_data.get("headline", ""),
                start_seconds=float(c_data.get("start_seconds", 0.0)),
                end_seconds=float(c_data.get("end_seconds", 30.0)),
                duration=float(c_data.get("duration", 30.0)),
                viral_score=int(c_data.get("viral_score", 90)),
                hook=c_data.get("hook", ""),
                reason=c_data.get("reason", ""),
                layout=item.get("layout", "single_face"),
                rubric_json=c_data.get("rubric"),
                headline_variants_json=c_data.get("headline_variants"),
                video_url=access_url,
                r2_key=r2_key
            )
            db.add(db_clip)

        # Update Project and Job status
        project.status = "completed"
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "success", "rendered_count": len(rendered_results)}

    except Exception as exc:
        db.rollback()
        # Check if exhausted retries -> Dead-letter failure state
        if self.request.retries >= self.max_retries:
            job.status = "failed"
            job.error = f"Dead-letter failure after {self.max_retries} retries: {str(exc)}"
            project.status = "failed"
            db.commit()
        raise exc
    finally:
        db.close()
