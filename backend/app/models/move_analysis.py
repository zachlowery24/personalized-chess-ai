from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


class MoveAnalysis(Base):
    __tablename__ = "move_analyses"

    __table_args__ = (
        UniqueConstraint(
            "game_analysis_id",
            "ply",
            name="uq_move_analyses_run_ply",
        ),
        CheckConstraint("ply >= 1", name="positive_ply"),
        CheckConstraint(
            "color IN ('white', 'black')",
            name="valid_color",
        ),
        CheckConstraint(
            "centipawn_loss IS NULL OR centipawn_loss >= 0",
            name="nonnegative_centipawn_loss",
        ),
        CheckConstraint(
            "(before_score_cp IS NOT NULL) != (before_mate_in IS NOT NULL)",
            name="one_before_score",
        ),
        CheckConstraint(
            "(after_score_cp IS NOT NULL) != (after_mate_in IS NOT NULL)",
            name="one_after_score",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    game_analysis_id: Mapped[int] = mapped_column(
        ForeignKey("game_analyses.id"),
    )

    ply: Mapped[int]
    color: Mapped[str] = mapped_column(String(5))
    uci: Mapped[str] = mapped_column(String(5))
    san: Mapped[str] = mapped_column(String(32))

    fen_before: Mapped[str] = mapped_column(Text)
    fen_after: Mapped[str] = mapped_column(Text)

    before_best_move: Mapped[str | None] = mapped_column(String(5))
    before_score_cp: Mapped[int | None]
    before_mate_in: Mapped[int | None]
    before_depth: Mapped[int | None]

    after_best_move: Mapped[str | None] = mapped_column(String(5))
    after_score_cp: Mapped[int | None]
    after_mate_in: Mapped[int | None]
    after_depth: Mapped[int | None]

    centipawn_loss: Mapped[int | None]