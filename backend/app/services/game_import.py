from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.services.chesscom import get_recent_games
from backend.app.services.game_processing import process_game
from backend.app.services.game_storage import save_imported_games

class GameRetrievalError(ValueError):
    """Game retrieval returned invalid data."""


class GameProcessingError(ValueError):
    """An imported game could not be processed."""


class GameStorageError(RuntimeError):
    """The import could not be saved to the database."""





def import_recent_games(
    username: str,
    count: int,
    *,
    session_factory: sessionmaker[Session] | None = None,
) -> dict:
    """Fetch and process games, optionally persisting the complete playable batch."""
    try:
        games = get_recent_games(username, count)
    except ValueError as error:
        raise GameRetrievalError(str(error)) from error

    processed_games = []
    playable_records = []

    try:
        for game in games:
            processed = process_game(game, username)

            if processed is not None:
                processed_games.append(processed)
                playable_records.append(game)
    except ValueError as error:
        raise GameProcessingError(str(error)) from error

    # No database transaction is opened until every record has been processed.
    if session_factory is not None and playable_records:
        try:
            save_imported_games(playable_records, session_factory)
        except SQLAlchemyError as error:
            raise GameStorageError("Could not save imported games.") from error

    return {
        "imported_count": len(games),
        "processed_count": len(processed_games),
        "skipped_count": len(games) - len(processed_games),
        "games": processed_games,
    }
    
