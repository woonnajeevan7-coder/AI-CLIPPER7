"""
Server-Sent Events (SSE) Live Pipeline Telemetry
Streams real-time agent status, progress percentage, and output events to client browsers.
"""

import asyncio
import json
from typing import AsyncGenerator
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Job


async def job_progress_sse_stream(job_id: str) -> AsyncGenerator[str, None]:
    """
    Polls the Job record asynchronously and yields SSE formatted event payloads.
    """
    last_progress = -1
    last_stage = ""

    while True:
        db: Session = SessionLocal()
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            db.close()
            yield f"data: {json.dumps({'error': 'Job not found', 'status': 'failed'})}\n\n"
            break

        stage = job.stage
        progress = job.progress
        status = job.status
        error = job.error
        db.close()

        if progress != last_progress or stage != last_stage:
            payload = {
                "job_id": job_id,
                "stage": stage,
                "progress": progress,
                "status": status,
                "error": error
            }
            yield f"data: {json.dumps(payload)}\n\n"
            last_progress = progress
            last_stage = stage

        if status in ("completed", "failed"):
            break

        await asyncio.sleep(0.5)
