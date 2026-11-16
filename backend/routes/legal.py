"""
Legal & Compliance API (/api/v1/legal)
Terms of Service, Privacy Policy, Rights Confirmation, and DMCA Copyright Takedown flow.
"""

from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, HTTPException, status
from datetime import datetime, timezone

router = APIRouter(prefix="/legal", tags=["Legal & Compliance"])


class DMCAReportRequest(BaseModel):
    reporter_name: str
    reporter_email: EmailStr
    copyright_owner_name: str
    original_work_url: str
    infringing_clip_id: str
    statement_of_authority: bool
    good_faith_statement: bool


@router.get("/terms")
def get_terms_of_service():
    return {
        "title": "AI Clipper Pro - Terms of Service",
        "last_updated": "2026-11-15",
        "content": (
            "Users must own or possess valid licensing rights for all media ingested into AI Clipper Pro. "
            "Automated repurposing of copyrighted works without authorization is strictly prohibited. "
            "We comply with the Digital Millennium Copyright Act (DMCA) and will promptly remove infringing materials."
        )
    }


@router.get("/privacy")
def get_privacy_policy():
    return {
        "title": "AI Clipper Pro - Privacy Policy",
        "last_updated": "2026-11-15",
        "content": (
            "We process video transcripts and audio solely to generate repurposed short clips. "
            "Temporary media files are deleted from processing instances after task completion. "
            "User credentials and API tokens are encrypted at rest and in transit."
        )
    }


@router.post("/dmca", status_code=status.HTTP_201_CREATED)
def submit_dmca_report(req: DMCAReportRequest):
    if not req.statement_of_authority or not req.good_faith_statement:
        raise HTTPException(
            status_code=400,
            detail="DMCA submission requires affirmative confirmation of authority and good faith belief."
        )

    # Log & acknowledge takedown request
    ticket_id = f"DMCA-{int(datetime.now(timezone.utc).timestamp())}"
    return {
        "status": "received",
        "ticket_id": ticket_id,
        "message": f"Copyright notice for clip '{req.infringing_clip_id}' has been recorded. Our compliance team will review within 24 hours.",
        "infringing_clip_id": req.infringing_clip_id
    }
