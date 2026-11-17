from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from backend.app.models.game import Game
from backend.app.models.game_analysis import GameAnalysis
from backend.app.models.move_analysis import MoveAnalysis


def list_latest_player_analyses(
    session: Session,
    player_id: int,
) -> list[GameAnalysis]:
    ranked = (
        select(
            GameAnalysis.id.label("analysis_id"),
            func.row_number()
            .over(
                partition_by=GameAnalysis.game_id,
                order_by=(
                    GameAnalysis.created_at.desc(),
                    GameAnalysis.id.desc(),
                ),
            )
            .label("rank"),
        )
        .join(Game, Game.id == GameAnalysis.game_id)
        .where(
            or_(
                Game.white_player_id == player_id,
                Game.black_player_id == player_id,
            )
        )
        .subquery()
    )

    statement = (
        select(GameAnalysis)
        .join(ranked, ranked.c.analysis_id == GameAnalysis.id)
        .where(ranked.c.rank == 1)
        .order_by(GameAnalysis.game_id)
    )

    return list(session.scalars(statement).all())


def list_practice_candidates(
    session: Session,
    player_id: int,
    analysis_ids: list[int],
) -> list[MoveAnalysis]:
    if not analysis_ids:
        return []

    statement = (
        select(MoveAnalysis)
        .join(
            GameAnalysis,
            GameAnalysis.id == MoveAnalysis.game_analysis_id,
        )
        .join(Game, Game.id == GameAnalysis.game_id)
        .where(
            MoveAnalysis.game_analysis_id.in_(analysis_ids),
            or_(
                and_(
                    Game.white_player_id == player_id,
                    MoveAnalysis.color == "white",
                ),
                and_(
                    Game.black_player_id == player_id,
                    MoveAnalysis.color == "black",
                ),
            ),
            MoveAnalysis.centipawn_loss > 0,
            MoveAnalysis.before_best_move.is_not(None),
            MoveAnalysis.before_best_move != MoveAnalysis.uci,
        )
        .order_by(
            MoveAnalysis.centipawn_loss.desc(),
            MoveAnalysis.game_analysis_id.desc(),
            MoveAnalysis.ply,
        )
    )

    return list(session.scalars(statement).all())

def get_practice_candidate(
    session: Session,
    player_id: int,
    analysis_id: int,
    ply: int,
) -> MoveAnalysis | None:
    statement = (
        select(MoveAnalysis)
        .join(
            GameAnalysis,
            GameAnalysis.id == MoveAnalysis.game_analysis_id,
        )
        .join(Game, Game.id == GameAnalysis.game_id)
        .where(
            MoveAnalysis.game_analysis_id == analysis_id,
            MoveAnalysis.ply == ply,
            or_(
                and_(
                    Game.white_player_id == player_id,
                    MoveAnalysis.color == "white",
                ),
                and_(
                    Game.black_player_id == player_id,
                    MoveAnalysis.color == "black",
                ),
            ),
            MoveAnalysis.centipawn_loss > 0,
            MoveAnalysis.before_best_move.is_not(None),
            MoveAnalysis.before_best_move != MoveAnalysis.uci,
        )
    )

    return session.scalars(statement).one_or_none()


