from logging.config import fileConfig

from alembic import context

from backend.app.config import Settings
from backend.app.database import get_engine
from backend.app.models.base import Base
from backend.app.models.player import PlayerProfile  # Registers the table.
from backend.app.models.game import Game
from backend.app.models.game_analysis import GameAnalysis
from backend.app.models.move_analysis import MoveAnalysis

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=Settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = get_engine()

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()