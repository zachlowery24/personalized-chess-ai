from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.models.game_analysis import GameAnalysis as GameAnalysisModel
from backend.app.models.move_analysis import MoveAnalysis as MoveAnalysisModel
from backend.app.services.engine_analysis import GameAnalysis as GameAnalysisResult


def create_game_analysis(
    session: Session,
    game_id: int,
    analysis: GameAnalysisResult,
) -> GameAnalysisModel:
    if not analysis.moves:
        raise ValueError("Analysis must contain at least one move")

    stored_analysis = GameAnalysisModel(
        game_id=game_id,
        engine_name=analysis.engine_name,
        requested_depth=analysis.requested_depth,
    )

    session.add(stored_analysis)
    session.flush()

    move_rows = [
        MoveAnalysisModel(
            game_analysis_id=stored_analysis.id,
            ply=move.ply,
            color=move.color,
            uci=move.uci,
            san=move.san,
            fen_before=move.fen_before,
            fen_after=move.fen_after,
            before_best_move=move.before.best_move,
            before_score_cp=move.before.score_cp,
            before_mate_in=move.before.mate_in,
            before_depth=move.before.depth,
            after_best_move=move.after.best_move,
            after_score_cp=move.after.score_cp,
            after_mate_in=move.after.mate_in,
            after_depth=move.after.depth,
            centipawn_loss=move.centipawn_loss,
        )
        for move in analysis.moves
    ]

    session.add_all(move_rows)
    session.flush()

    return stored_analysis


def get_game_analysis_by_id(
    session: Session,
    analysis_id: int,
) -> GameAnalysisModel | None:
    return session.get(GameAnalysisModel, analysis_id)


def list_analysis_moves(
    session: Session,
    analysis_id: int,
) -> list[MoveAnalysisModel]:
    statement = (
        select(MoveAnalysisModel)
        .where(MoveAnalysisModel.game_analysis_id == analysis_id)
        .order_by(MoveAnalysisModel.ply)
    )

    return list(session.scalars(statement).all())


def list_game_analyses(
    session: Session,
    game_id: int,
    *,
    limit: int = 20,
    offset: int = 0,
) -> list[GameAnalysisModel]:
    statement = (
        select(GameAnalysisModel)
        .where(GameAnalysisModel.game_id == game_id)
        .order_by(
            GameAnalysisModel.created_at.desc(),
            GameAnalysisModel.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return list(session.scalars(statement).all())




