"""
Database Engine & Session Management
Initializes SQLAlchemy engine and session dependency.
"""

from sqlalchemy import create_engine
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


def get_db():
    """FastAPI database session dependency."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
