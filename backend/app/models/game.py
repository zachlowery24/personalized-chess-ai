from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


class Game(Base):
    __tablename__ = "games"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_url",
            name="uq_games_source_source_url",
        ),
        CheckConstraint(
            "white_player_id != black_player_id",
            name="different_players",
        ),
        CheckConstraint(
            "rules = 'chess'",
            name="standard_chess",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    source: Mapped[str] = mapped_column(String(32))
    source_url: Mapped[str] = mapped_column(Text)

    white_player_id: Mapped[int] = mapped_column(
        ForeignKey("player_profiles.id"),
        index=True,
    )
    black_player_id: Mapped[int] = mapped_column(
        ForeignKey("player_profiles.id"),
        index=True,
    )

    white_result: Mapped[str] = mapped_column(String(32))
    black_result: Mapped[str] = mapped_column(String(32))

    time_class: Mapped[str] = mapped_column(String(32))
    rules: Mapped[str] = mapped_column(String(32))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pgn: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )