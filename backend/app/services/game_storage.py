from sqlalchemy.orm import Session, sessionmaker

from backend.app.repositories.games import get_or_create_game


def save_imported_games(
    games: list[dict],
    session_factory: sessionmaker[Session],
) -> list[int]:
    """Save validated, playable Chess.com records and return their database IDs."""
    game_ids = []

    with session_factory.begin() as session:
        for game in games:
            stored_game = get_or_create_game(session, game)
            game_ids.append(stored_game.id)

    return game_ids
