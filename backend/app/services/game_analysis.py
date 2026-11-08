from sqlalchemy.orm import Session, sessionmaker

from backend.app.repositories.analyses import create_game_analysis
from backend.app.repositories.games import get_game_by_id
from backend.app.services.engine_analysis import analyze_game


class GameNotFoundError(Exception):
    """The requested saved game does not exist."""


def analyze_saved_game(
    game_id: int,
    *,
    session_factory: sessionmaker[Session],
    engine_path: str,
    depth: int = 12,
) -> int:
    if (
        not isinstance(game_id, int)
        or isinstance(game_id, bool)
        or game_id < 1
    ):
        raise ValueError("game_id must be a positive integer")

    if (
        not isinstance(depth, int)
        or isinstance(depth, bool)
        or depth < 1
    ):
        raise ValueError("depth must be a positive integer")

    with session_factory() as session:
        game = get_game_by_id(session, game_id)

        if game is None:
            raise GameNotFoundError(f"Game {game_id} was not found")

        pgn_text = game.pgn

    analysis = analyze_game(
        pgn_text,
        engine_path=engine_path,
        depth=depth,
    )

    with session_factory.begin() as session:
        stored_analysis = create_game_analysis(
            session,
            game_id,
            analysis,
        )
        analysis_id = stored_analysis.id

    return analysis_id