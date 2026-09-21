import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base
from app.db.dependencies import get_db

@pytest.fixture(scope="session")
def global_test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="session")
def GlobalTestingSessionLocal(global_test_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=global_test_engine)

@pytest.fixture(scope="function", autouse=True)
def fallback_db_override(GlobalTestingSessionLocal):
    """
    Global safety fixture.
    Automatically intercepts any FastAPI routes that call get_db,
    preventing them from using the real production database if a test
    forgets to declare its own dependency_overrides.
    """
    db = GlobalTestingSessionLocal()
    
    def override_get_db():
        try:
            yield db
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    
    yield db
    
    # Clean up the fallback database
    db.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    db.close()
    
    # Only clear the override if it still points to our fallback override.
    # Other tests might have overwritten app.dependency_overrides[get_db] 
    # in their setUp(). We don't want to clear their overrides prematurely,
    # though it usually doesn't matter since tearDown will clear them anyway.
    if app.dependency_overrides.get(get_db) == override_get_db:
        del app.dependency_overrides[get_db]
