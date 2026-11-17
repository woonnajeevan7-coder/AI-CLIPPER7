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
                cursor = conn.execute(text("PRAGMA table_info(clips)"))
                existing_cols = {row[1] for row in cursor.fetchall()}
                if "live_session_id" not in existing_cols:
                    conn.execute(text("ALTER TABLE clips ADD COLUMN live_session_id VARCHAR(36)"))
                if "source" not in existing_cols:
                    conn.execute(text("ALTER TABLE clips ADD COLUMN source VARCHAR(50) DEFAULT 'fixed'"))
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

