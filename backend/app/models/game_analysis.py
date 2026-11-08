from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


class GameAnalysis(Base):
    __tablename__ = "game_analyses"

    __table_args__ = (
        CheckConstraint(
            "requested_depth >= 1",
            name="positive_requested_depth",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id"),
        index=True,
    )

    engine_name: Mapped[str] = mapped_column(String(255))
    requested_depth: Mapped[int]

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )