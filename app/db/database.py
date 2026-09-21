from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

if settings.ENVIRONMENT == "test":
    if not settings.DATABASE_URL.startswith("sqlite:///:memory:"):
        raise RuntimeError("SAFETY BLOCK: Tests cannot run against the production database.")

engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()