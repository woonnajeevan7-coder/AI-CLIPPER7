"""
Database Engine & Session Management
Initializes SQLAlchemy engine and session dependency.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from .config import settings
from .models import Base

# Create engine (supports PostgreSQL in prod, SQLite in dev/testing)
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Creates database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)

    # Safe SQLite column migration for development/testing environments
    if settings.DATABASE_URL.startswith("sqlite"):
        try:
            with engine.connect() as conn:
                # Migrate clips
                cursor = conn.execute(text("PRAGMA table_info(clips)"))
                raw_cols = cursor.fetchall()
                existing_cols = {row[1] for row in raw_cols}
                col_map = {row[1]: row for row in raw_cols}
                if col_map.get("project_id") and col_map["project_id"][3] == 1:
                    conn.execute(text("""
                        CREATE TABLE clips_new (
                            id VARCHAR(36) PRIMARY KEY,
                            project_id VARCHAR(36) REFERENCES projects(id) ON DELETE CASCADE,
                            live_session_id VARCHAR(36) REFERENCES live_sessions(id) ON DELETE CASCADE,
                            clip_index INTEGER,
                            source VARCHAR(50) DEFAULT 'fixed' NOT NULL,
                            status VARCHAR(50) DEFAULT 'completed' NOT NULL,
                            title VARCHAR(255) NOT NULL,
                            headline VARCHAR(255) NOT NULL,
                            start_seconds FLOAT NOT NULL,
                            end_seconds FLOAT NOT NULL,
                            duration FLOAT NOT NULL,
                            viral_score INTEGER DEFAULT 90,
                            hook TEXT,
                            reason TEXT,
                            layout VARCHAR(50) DEFAULT 'single_face',
                            rubric_json JSON,
                            headline_variants_json JSON,
                            video_url TEXT,
                            r2_key VARCHAR(255),
                            created_at DATETIME NOT NULL
                        )
                    """))
                    conn.execute(text("INSERT INTO clips_new SELECT id, project_id, live_session_id, clip_index, source, status, title, headline, start_seconds, end_seconds, duration, viral_score, hook, reason, layout, rubric_json, headline_variants_json, video_url, r2_key, created_at FROM clips"))
                    conn.execute(text("DROP TABLE clips"))
                    conn.execute(text("ALTER TABLE clips_new RENAME TO clips"))
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_clips_session_clip_index ON clips (live_session_id, clip_index)"))
                    existing_cols = {"id", "project_id", "live_session_id", "clip_index", "source", "status", "title", "headline", "start_seconds", "end_seconds", "duration", "viral_score", "hook", "reason", "layout", "rubric_json", "headline_variants_json", "video_url", "r2_key", "created_at"}

                if "live_session_id" not in existing_cols:
                    conn.execute(text("ALTER TABLE clips ADD COLUMN live_session_id VARCHAR(36)"))
                if "source" not in existing_cols:
                    conn.execute(text("ALTER TABLE clips ADD COLUMN source VARCHAR(50) DEFAULT 'fixed'"))
                if "status" not in existing_cols:
                    conn.execute(text("ALTER TABLE clips ADD COLUMN status VARCHAR(50) DEFAULT 'completed'"))
                if "clip_index" not in existing_cols:
                    conn.execute(text("ALTER TABLE clips ADD COLUMN clip_index INTEGER"))
                if "error" not in existing_cols:
                    conn.execute(text("ALTER TABLE clips ADD COLUMN error TEXT"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_clips_session_clip_index ON clips (live_session_id, clip_index)"))

                # Migrate live_sessions
                cursor_ls = conn.execute(text("PRAGMA table_info(live_sessions)"))
                ls_cols = {row[1] for row in cursor_ls.fetchall()}
                if "stream_key" not in ls_cols:
                    conn.execute(text("ALTER TABLE live_sessions ADD COLUMN stream_key VARCHAR(100)"))
                if "source_type" not in ls_cols:
                    conn.execute(text("ALTER TABLE live_sessions ADD COLUMN source_type VARCHAR(50) DEFAULT 'rtmp'"))
                if "rolling_buffer_minutes" not in ls_cols:
                    conn.execute(text("ALTER TABLE live_sessions ADD COLUMN rolling_buffer_minutes INTEGER DEFAULT 15"))
                if "total_segments_recorded" not in ls_cols:
                    conn.execute(text("ALTER TABLE live_sessions ADD COLUMN total_segments_recorded INTEGER DEFAULT 0"))
                if "error" not in ls_cols:
                    conn.execute(text("ALTER TABLE live_sessions ADD COLUMN error TEXT"))

                conn.commit()
        except Exception:
            pass


def get_db():
    """FastAPI database session dependency."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def increment_user_usage(
    db: Session,
    user_id: str,
    clips_delta: int = 0,
    minutes_delta: float = 0.0
):
    """
    Increments or initializes the monthly Usage record for a user.
    """
    from datetime import datetime, timezone
    from .models import Usage
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    usage = db.query(Usage).filter(
        Usage.user_id == user_id,
        Usage.period_month == current_month
    ).first()
    if not usage:
        usage = Usage(
            user_id=user_id,
            period_month=current_month,
            clips_created=0,
            minutes_transcribed=0.0
        )
        db.add(usage)
    usage.clips_created += clips_delta
    usage.minutes_transcribed = round(usage.minutes_transcribed + minutes_delta, 2)
    db.commit()
    db.refresh(usage)
    return usage

