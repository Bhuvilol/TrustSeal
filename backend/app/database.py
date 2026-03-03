from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .core.config import settings

database_url = settings.DATABASE_URL
engine_kwargs = {}
if database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    connect_args = {}
    if database_url.startswith("postgresql"):
        connect_args["connect_timeout"] = max(1, settings.POSTGRES_CONNECT_TIMEOUT_SECONDS)

    engine_kwargs.update(
        {
            "pool_size": max(1, settings.SQLALCHEMY_POOL_SIZE),
            "max_overflow": max(0, settings.SQLALCHEMY_MAX_OVERFLOW),
            "pool_timeout": max(1, settings.SQLALCHEMY_POOL_TIMEOUT_SECONDS),
            "pool_recycle": max(1, settings.SQLALCHEMY_POOL_RECYCLE_SECONDS),
            "pool_pre_ping": settings.SQLALCHEMY_POOL_PRE_PING,
            "pool_use_lifo": True,
            "connect_args": connect_args,
        }
    )

engine = create_engine(database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
