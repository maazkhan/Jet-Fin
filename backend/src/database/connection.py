import os
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import logging

logger = logging.getLogger(__name__)


class DatabaseConnection:
    _engine = None
    _session_factory = None

    @classmethod
    def initialize(cls, database_url: str = None):
        if database_url is None:
            database_url = os.getenv("DATABASE_URL", "postgresql://finops:finops_password@localhost:5432/finops_db")

        cls._engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )

        cls._session_factory = sessionmaker(bind=cls._engine, expire_on_commit=False)

        @event.listens_for(cls._engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            pass

        logger.info("Database connection initialized")

    @classmethod
    def get_session(cls) -> Session:
        if cls._session_factory is None:
            cls.initialize()
        return cls._session_factory()

    @classmethod
    def health_check(cls) -> bool:
        try:
            with cls.get_session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    @classmethod
    def close(cls):
        if cls._engine:
            cls._engine.dispose()


# Global session dependency for FastAPI
def get_db():
    db = DatabaseConnection.get_session()
    try:
        yield db
    finally:
        db.close()
