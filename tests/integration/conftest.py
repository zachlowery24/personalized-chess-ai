import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.config import Settings


@pytest.fixture(scope="session")
def db_engine():
    if os.environ.get("RUN_DB_TESTS") != "1":
        pytest.skip("Set RUN_DB_TESTS=1 to run PostgreSQL integration tests")

    settings = Settings()
    test_url = settings.database_url.set(
        database="personalized_chess_test"
    )

    engine = create_engine(
        test_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()

        try:
            with Session(
                bind=connection,
                join_transaction_mode="create_savepoint",
            ) as session:
                yield session
        finally:
            transaction.rollback()