from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models.database import Base
from utils.settings import settings

DATABASE_URL = settings.DATABASE_URL

_engine = None

def get_engine():
    """
    Returns the SQLAlchemy engine singleton.

    create_engine() is expensive (allocates the connection pool, parses the
    URL, etc.) and must only be called once per process.  Subsequent calls
    return the same engine instance so all sessions share the same pool.
    """
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, echo=False)
    return _engine

def init_db():
    """
    Creates all tables in the database.
    
    Call this once at startup. If tables already exist, it does nothing.
    This is safe to call multiple times.
    """
    engine = get_engine()
    Base.metadata.create_all(engine)

def get_session() -> Session:
    """
    Returns a database session (like a "conversation" with the database).
    
    Usage:
        session = get_session()
        session.add(some_invoice)
        session.commit()
    
    Why sessions?
    - They track changes before committing (transaction management)
    - If something fails, you can rollback — no partial data saved
    - This is the Unit of Work pattern
    """
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()
