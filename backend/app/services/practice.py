from sqlalchemy.orm import Session

from backend.app.repositories.practice import (
    list_latest_player_analyses,
    list_practice_candidates,
)
from backend.app.schemas.practice import (
    PracticePositionResponse,
    PracticeQueueResponse,
)


def build_practice_queue(
    session: Session,
    player_id: int,
    *,
    limit: int = 3,
) -> PracticeQueueResponse:
    if (
        not isinstance(player_id, int)
        or isinstance(player_id, bool)
        or player_id < 1
    ):
        raise ValueError("player_id must be a positive integer")

    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= 10
    ):
        raise ValueError("limit must be an integer between 1 and 10")

    analyses = list_latest_player_analyses(session, player_id)
    analyses_by_id = {analysis.id: analysis for analysis in analyses}

    candidates = list_practice_candidates(
        session,
        player_id,
        list(analyses_by_id),
    )

    positions = []
    selected_game_ids: set[int] = set()

    for move in candidates:
        analysis = analyses_by_id[move.game_analysis_id]

        if analysis.game_id in selected_game_ids:
            continue

        positions.append(
            PracticePositionResponse(
                game_id=analysis.game_id,
                analysis_id=analysis.id,
                ply=move.ply,
                color=move.color,
                fen=move.fen_before,
                engine_name=analysis.engine_name,
                requested_depth=analysis.requested_depth,
            )
        )
        selected_game_ids.add(analysis.game_id)

        if len(positions) == limit:
            break

    return PracticeQueueResponse(
        player_id=player_id,
        positions=positions,
        analyzed_game_count=len(analyses),
    )