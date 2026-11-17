"""
Server-Sent Events (SSE) Live Pipeline Telemetry
Streams real-time agent status, progress percentage, and output events to client browsers.
"""

import asyncio
import json
from typing import AsyncGenerator, Dict, Set, Any
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Job


class LiveEventBroadcaster:
    """In-memory pub/sub event broadcaster for live session SSE connections."""

    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}

    def subscribe(self, session_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        if session_id not in self._subscribers:
            self._subscribers[session_id] = set()
        self._subscribers[session_id].add(q)
        return q

    def unsubscribe(self, session_id: str, q: asyncio.Queue):
        if session_id in self._subscribers:
            self._subscribers[session_id].discard(q)
            if not self._subscribers[session_id]:
                del self._subscribers[session_id]

    async def broadcast(self, session_id: str, event_name: str, data: Dict[str, Any]):
        """Broadcasts an event to all connected clients for session_id."""
        if session_id in self._subscribers:
            for q in list(self._subscribers[session_id]):
                await q.put((event_name, data))


live_broadcaster = LiveEventBroadcaster()


async def live_session_event_stream(session_id: str) -> AsyncGenerator[str, None]:
    """
    Yields SSE formatted events for a live session:
    - segment_recorded
    - clip_created
    - clip_ready
    - error
    """
    queue = live_broadcaster.subscribe(session_id)
    try:
        # Initial connection acknowledgment
        yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'session_id': session_id})}\n\n"
        while True:
            try:
                event_name, data = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
            except asyncio.TimeoutError:
                # Keep-alive comment to prevent browser timeout
                yield ": keep-alive\n\n"
    finally:
        live_broadcaster.unsubscribe(session_id, queue)


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
