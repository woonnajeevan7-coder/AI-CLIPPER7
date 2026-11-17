"""
SQLAlchemy PostgreSQL / Database Models
Defines complete enterprise schema for users, projects, jobs, transcripts, clips, plans, usage, and metrics.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    google_id = Column(String(255), unique=True, nullable=True)
    plan = Column(String(50), default="free", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    usage_records = relationship("Usage", back_populates="user", cascade="all, delete-orphan")
    publish_targets = relationship("PublishTarget", back_populates="user", cascade="all, delete-orphan")
    social_accounts = relationship("SocialAccount", back_populates="user", cascade="all, delete-orphan")
    twitch_channels = relationship("TwitchChannel", back_populates="user", cascade="all, delete-orphan")
    live_sessions = relationship("LiveSession", back_populates="user", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    source_type = Column(String(50), default="youtube")  # 'youtube' or 'upload'
    source_url = Column(Text, nullable=True)
    video_id = Column(String(100), index=True, nullable=True)
    status = Column(String(50), default="pending")        # 'pending', 'processing', 'completed', 'failed'
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User", back_populates="projects")
    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")
    transcripts = relationship("Transcript", back_populates="project", cascade="all, delete-orphan")
    clips = relationship("Clip", back_populates="project", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(String(100), default="queued")  # 'transcribing', 'curating', 'framing', 'rendering'
    status = Column(String(50), default="queued")  # 'queued', 'running', 'completed', 'failed'
    progress = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="jobs")


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(100), index=True, nullable=True)
    raw_text = Column(Text, nullable=False)
    words_json = Column(JSON, nullable=False)  # List of WordTimestamp dicts
    language = Column(String(20), default="en")
    created_at = Column(DateTime, default=utc_now, nullable=False)

    project = relationship("Project", back_populates="transcripts")


class Clip(Base):
    __tablename__ = "clips"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    live_session_id = Column(String(36), ForeignKey("live_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    source = Column(String(50), default="fixed", nullable=False)  # 'fixed' | 'highlight'
    title = Column(String(255), nullable=False)
    headline = Column(String(255), nullable=False)
    start_seconds = Column(Float, nullable=False)
    end_seconds = Column(Float, nullable=False)
    duration = Column(Float, nullable=False)
    viral_score = Column(Integer, default=90)
    hook = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    layout = Column(String(50), default="single_face")  # 'single_face', 'split_screen', 'blur_fallback'
    rubric_json = Column(JSON, nullable=True)
    headline_variants_json = Column(JSON, nullable=True)
    video_url = Column(Text, nullable=True)
    r2_key = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    project = relationship("Project", back_populates="clips")
    live_session = relationship("LiveSession", back_populates="clips")
    metrics = relationship("ClipMetric", back_populates="clip", cascade="all, delete-orphan")


class Plan(Base):
    __tablename__ = "plans"

    id = Column(String(50), primary_key=True)  # 'free', 'pro', 'agency'
    name = Column(String(100), nullable=False)
    monthly_clip_limit = Column(Integer, nullable=False)
    max_duration_minutes = Column(Integer, nullable=False)
    price_cents = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)


class Usage(Base):
    __tablename__ = "usage"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    period_month = Column(String(7), nullable=False)  # 'YYYY-MM'
    clips_created = Column(Integer, default=0)
    minutes_transcribed = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="usage_records")


class PublishTarget(Base):
    __tablename__ = "publish_targets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(String(50), nullable=False)  # 'youtube', 'tiktok', 'instagram'
    account_name = Column(String(255), nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User", back_populates="publish_targets")
    metrics = relationship("ClipMetric", back_populates="publish_target")


class ClipMetric(Base):
    __tablename__ = "clip_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    clip_id = Column(String(36), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True)
    publish_target_id = Column(String(36), ForeignKey("publish_targets.id", ondelete="SET NULL"), nullable=True)
    external_post_id = Column(String(255), nullable=True)
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    retention_rate = Column(Float, default=0.0)
    last_synced_at = Column(DateTime, default=utc_now)

    clip = relationship("Clip", back_populates="metrics")
    publish_target = relationship("PublishTarget", back_populates="metrics")


class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)  # 'twitch', 'youtube', etc.
    provider_user_id = Column(String(100), nullable=False, index=True)
    encrypted_access_token = Column(Text, nullable=False)
    encrypted_refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    scope = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="social_accounts")


class TwitchChannel(Base):
    __tablename__ = "twitch_channels"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    broadcaster_id = Column(String(100), nullable=False, index=True)
    login = Column(String(100), nullable=False)
    display_name = Column(String(100), nullable=True)
    rights_confirmed = Column(Boolean, default=False, nullable=False)
    eventsub_subscription_id_online = Column(String(100), nullable=True)
    eventsub_subscription_id_offline = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="twitch_channels")


class LiveSession(Base):
    __tablename__ = "live_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    broadcaster_id = Column(String(100), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    stream_url = Column(Text, nullable=False)
    platform = Column(String(50), default="twitch", nullable=False)
    status = Column(String(50), default="starting", nullable=False)  # 'starting', 'live', 'stopping', 'stopped', 'failed'
    rights_confirmed = Column(Boolean, default=False, nullable=False)
    target_framing = Column(String(50), default="sports_gaming")
    caption_style = Column(String(50), default="sports_gaming")
    started_at = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User", back_populates="live_sessions")
    clips = relationship("Clip", back_populates="live_session", cascade="all, delete-orphan")
