from functools import lru_cache

from sqlalchemy import Engine, create_engine

from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import Settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = Settings()

    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )

@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine())


