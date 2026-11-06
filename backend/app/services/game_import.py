from backend.app.services.chesscom import get_recent_games
from backend.app.services.game_processing import process_game

class GameRetrievalError(ValueError):
    """Game retrieval returned invalid data."""


class GameProcessingError(ValueError):
    """An imported game could not be processed."""





def import_recent_games(username: str, count: int) -> dict:
    try:
        games = get_recent_games(username, count)
    except ValueError as error:
        raise GameRetrievalError(str(error)) from error

    processed_games = []

    try:
        for game in games:
            processed = process_game(game, username)

            if processed is not None:
                processed_games.append(processed)
    except ValueError as error:
        raise GameProcessingError(str(error)) from error

    return {
        "imported_count": len(games),
        "processed_count": len(processed_games),
        "skipped_count": len(games) - len(processed_games),
        "games": processed_games,
    }